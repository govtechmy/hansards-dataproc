"""MMS-only archive preparation for manual sitting runs; database house remains DN."""
from datetime import datetime
import json

from hansards_pipelines.arkib_sittings.promote_pdfs import promote_arkib_pdfs

MMS_SOURCE_PREFIX = 'arkib/dewannegara/mms/'
MMS_ARCHIVE_PREFIX = 'arkib/mms'


def prepare_mms_archive(*, s3, dataproc_bucket, public_bucket, parliament,
                        get_sitting_object, logger):
    """Consume one term's manifest and promote its PDFs for manual sitting runs.

    MMS source and staging prefixes are isolated from the ordinary DN mover.
    Raw sources are retained so retries can repeat promotion after a partial
    failure. Return partitions only after every selected PDF is promoted.
    """
    manifest_key = f'arkib/dewannegara/manifest/mms/manifest_term_{parliament}.json'
    manifest = json.loads(s3.get_object(Bucket=dataproc_bucket, Key=manifest_key)['Body'].read())
    if manifest.get('house') != 'dewannegara' or manifest.get('parliament') != parliament:
        raise ValueError('MMS archive manifest has an unexpected house or parliament')
    items = manifest['items']
    if not isinstance(items, list):
        raise ValueError('MMS archive manifest items must be a list')
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
            if not sitting or sitting['house'] != 'MMS' or sitting['house_folder'] != 'dewannegara':
                raise ValueError('Filename did not resolve to MMS under Dewan Negara')
            day = datetime.strptime(sitting['date_str'], '%d%m%Y')
        except ValueError as exc:
            skipped.append(dict(filename=filename, reason=str(exc)))
            logger.warning(f'Skipped MMS archive item {filename!r}: {exc}')
            continue
        partition = f'MMS-{day:%d%m%Y}'
        # Normalize metadata for public paths; retain the exact raw S3 filename.
        selected[partition] = (filename, get_sitting_object(partition))

    partitions = sorted(selected, key=lambda p: datetime.strptime(p[4:], '%d%m%Y'))
    for partition in partitions:
        filename, sitting = selected[partition]
        s3.copy_object(
            Bucket=public_bucket,
            Key=f"{MMS_ARCHIVE_PREFIX}/dewannegara/{sitting['renamed_filename']}.pdf",
            CopySource={'Bucket': dataproc_bucket, 'Key': MMS_SOURCE_PREFIX + filename},
            ContentType='application/pdf',
        )
    promote_arkib_pdfs(
        s3_client=s3, bucket=public_bucket, partitions=partitions,
        get_sitting_object=get_sitting_object, logger=logger,
        archive_prefix=MMS_ARCHIVE_PREFIX,
    )
    return dict(parliament=parliament, partitions=partitions, skipped=skipped)
