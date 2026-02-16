from dagster import Definitions, ScheduleDefinition, load_assets_from_modules, define_asset_job
from hansards_pipelines import assets, jobs
from .sensors import (
    sittings_sensor,
    trigger_arkib_pdf_move_sensor,
    trigger_sittings_job_arkib_sensor,
    trigger_sittings_legacy_job,
    trigger_register_sitting_legacy_partition_sensor,
)

all_assets = load_assets_from_modules([assets])

scrape_schedule = ScheduleDefinition(
    job=jobs.scrape_job,
    cron_schedule="0 * * * *",  # every hour
)

parliamentary_cycle_schedule = ScheduleDefinition(
    job=jobs.scrape_parliamentary_cycle_job,
    cron_schedule="0 16 * * 5",  # Sat 00:00 MY
)

scrape_arkib_schedule = ScheduleDefinition(
    job=jobs.scrape_arkib_job,
    cron_schedule="0 16 * * 5",  # Sat 00:00 MY
)

defs = Definitions(
    assets=all_assets,
    jobs=[
        jobs.scrape_parliamentary_cycle_job,
        jobs.sittings_job,
        jobs.scrape_job,
        jobs.scrape_arkib_job,
        jobs.author_load_job,
        jobs.move_arkib_pdfs_job,
        jobs.sittings_legacy_job,
        jobs.register_sitting_legacy_partition_job,
        jobs.report_sittings_integrity_job,
        jobs.report_overall_sittings_integrity_job
    ],
    sensors=[
        sittings_sensor,
        trigger_arkib_pdf_move_sensor,
        trigger_sittings_job_arkib_sensor,
        trigger_sittings_legacy_job,
        trigger_register_sitting_legacy_partition_sensor,
    ],
    schedules=[
        scrape_schedule,
        parliamentary_cycle_schedule,
        scrape_arkib_schedule,
    ],
)
