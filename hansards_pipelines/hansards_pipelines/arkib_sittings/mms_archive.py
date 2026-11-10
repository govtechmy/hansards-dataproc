"""MMS-only archive preparation for manual sitting runs; database house remains DN."""
from datetime import datetime
import json
import re

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
    for item in items:
        filename = item['filename']
        if (item.get('house_folder') != 'dewannegara'
                or not re.fullmatch(r'MMS-\d{8}\.pdf', filename, re.I)):
            raise ValueError(f'Non-MMS item in MMS archive manifest: {filename}')
        sitting = get_sitting_object(filename)
        if sitting['house'] != 'MMS' or sitting['house_folder'] != 'dewannegara':
            raise ValueError('MMS archive item did not resolve to Dewan Negara')
        day = datetime.strptime(sitting['date_str'], '%d%m%Y')
        selected[f'MMS-{day:%d%m%Y}'] = (filename, sitting)

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
    return dict(parliament=parliament, partitions=partitions)
