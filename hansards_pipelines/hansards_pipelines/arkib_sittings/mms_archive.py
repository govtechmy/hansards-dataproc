"""MMS-only archive preparation for manual sitting runs; database membership comes from the scraped hierarchy."""
from datetime import datetime
from io import BytesIO
import json
import re

import pdfplumber

from hansards_pipelines.scrape_mms_parlimen_penggal import MMS_ARCHIVE_ROOT, validate_assignment, save_assignment

from hansards_pipelines.arkib_sittings.promote_pdfs import promote_arkib_pdfs

MMS_SOURCE_PREFIX = f'{MMS_ARCHIVE_ROOT}/pdfs/'
MMS_ARCHIVE_PREFIX = MMS_ARCHIVE_ROOT


def verify_mms_pdf_cover(content):
    """Confirm a DN-labelled archive candidate is MMS from its physical cover."""
    try:
        with pdfplumber.open(BytesIO(content)) as pdf:
            cover = ''
            if pdf.pages:
                cover = pdf.pages[0].extract_text() or ''
    except Exception as exc:
        raise ValueError('Could not read PDF cover to verify MMS document type') from exc
    if not re.search(r'\bMAJLIS\s+MENGANGKAT\s+SUMPAH\b', cover, re.IGNORECASE):
        raise ValueError('PDF cover does not identify Majlis Mengangkat Sumpah')
    return dict(verified_document_type='MMS', document_type_source='pdf_cover',
                document_type_source_page=1)


def prepare_mms_archive(*, s3, dataproc_bucket, public_bucket, parliament,
                        get_sitting_object, logger):
    """Consume one term's manifest and promote its PDFs for manual sitting runs.

    MMS source and staging prefixes are isolated from the ordinary DN mover.
    Raw sources are retained so retries can repeat promotion after a partial
    failure. Return partitions only after every selected PDF is promoted.
    """
    manifest_key = f'{MMS_ARCHIVE_ROOT}/manifest/latest/manifest_term_{parliament}.json'
    manifest = json.loads(s3.get_object(Bucket=dataproc_bucket, Key=manifest_key)['Body'].read())
    if manifest.get('house') != 'dewannegara' or manifest.get('parliament') != parliament:
        raise ValueError('MMS archive manifest has an unexpected house or parliament')
    items = manifest['items']
    if not isinstance(items, list):
        raise ValueError('MMS archive manifest items must be a list')
    # Old manifests must be re-scraped; never infer a session from dates.
    for item in items:
        assignment = validate_assignment(item)
        if assignment["term"] != parliament:
            raise ValueError("MMS item Parlimen does not match manifest")
    selected = {}
    skipped = []
    for item in items:
        filename = item.get('filename') if isinstance(item, dict) else None
        try:
            if (not isinstance(filename, str) or not filename
                    or any(char in filename for char in ('/', '\\', '\x00'))):
                raise ValueError('Missing filename or filename contains a directory path')
            if item.get('house_folder') != 'dewannegara':
                raise ValueError('Item must belong to Dewan Negara')
            sitting = get_sitting_object(filename)
            if not sitting or sitting['house_folder'] != 'dewannegara':
                raise ValueError('Filename did not resolve under Dewan Negara')
            day = datetime.strptime(sitting['date_str'], '%d%m%Y')
            assignment = {**item, 'source_filename': filename}
            if sitting['house'] == 'DN':
                # This manifest is MMS-only. Verify the actual PDF rather than
                # trusting the DN prefix or applying a global filename override.
                raw_pdf = s3.get_object(Bucket=dataproc_bucket,
                                        Key=MMS_SOURCE_PREFIX + filename)['Body'].read()
                assignment.update(verify_mms_pdf_cover(raw_pdf))
                logger.info(f'PDF cover confirms MMS despite DN filename: {filename}')
            elif sitting['house'] != 'MMS':
                raise ValueError('Filename did not resolve to an MMS or DN candidate')
        except ValueError as exc:
            skipped.append(dict(filename=filename, reason=str(exc)))
            logger.warning(f'Skipped MMS archive item {filename!r}: {exc}')
            continue
        partition = f'MMS-{day:%d%m%Y}'
        # Normalize metadata for public paths; retain the exact raw S3 filename.
        if partition in selected and any(selected[partition][2][k] != item[k] for k in ("term", "session")):
            raise ValueError(f"Conflicting MMS assignments for {filename}")
        selected[partition] = (filename, get_sitting_object(partition), assignment)

    partitions = sorted(selected, key=lambda p: datetime.strptime(p[4:], '%d%m%Y'))
    for partition in partitions:
        filename, sitting, assignment = selected[partition]
        save_assignment(s3, dataproc_bucket, sitting["renamed_filename"], assignment)
        s3.copy_object(
            Bucket=public_bucket,
            Key=f"{MMS_ARCHIVE_PREFIX}/{sitting['public_house_folder']}/{sitting['renamed_filename']}.pdf",
            CopySource={'Bucket': dataproc_bucket, 'Key': MMS_SOURCE_PREFIX + filename},
            ContentType='application/pdf',
        )
    promote_arkib_pdfs(
        s3_client=s3, bucket=public_bucket, partitions=partitions,
        get_sitting_object=get_sitting_object, logger=logger,
        archive_prefix=MMS_ARCHIVE_PREFIX,
    )
    return dict(parliament=parliament, partitions=partitions, skipped=skipped)
