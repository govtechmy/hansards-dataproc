from dagster import Definitions, ScheduleDefinition, load_assets_from_modules, define_asset_job
from hansards_pipelines import assets, jobs
from .sensors import (
    sittings_sensor,
    my_discord_on_run_frontend_success,
    my_discord_on_run_failure,
)

all_assets = load_assets_from_modules([assets])

scrape_schedule = ScheduleDefinition(
    job=jobs.scrape_job,
    cron_schedule="0 * * * *",  # every hour
)

parliamentary_cycle_schedule = ScheduleDefinition(
    job=jobs.parliamentary_cycle_job,
    cron_schedule="0 16 * * 5",  # Sat 00:00 MY
)

scrape_arkib_schedule = ScheduleDefinition(
    job=jobs.scrape_arkib_job,
    cron_schedule="0 16 * * 5",  # Sat 00:00 MY
)

defs = Definitions(
    assets=all_assets,
    jobs=[
        jobs.parliamentary_cycle_job,
        jobs.sittings_job,
        jobs.scrape_job,
        jobs.scrape_arkib_job,
    ],
    sensors=[
        sittings_sensor,
        my_discord_on_run_frontend_success,
        my_discord_on_run_failure,
    ],
    schedules=[
        scrape_schedule,
        parliamentary_cycle_schedule,
        scrape_arkib_schedule,
    ],
)
