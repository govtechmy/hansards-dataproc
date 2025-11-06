from dagster import Definitions, ScheduleDefinition, load_assets_from_modules, define_asset_job
from hansards_pipelines import assets, jobs
from .sensors import (
    sittings_sensor,
    my_discord_on_run_frontend_success,
    my_discord_on_run_failure,
)
from hansards_pipelines import settings

all_assets = load_assets_from_modules([assets])

scrape_schedule = ScheduleDefinition(
    job=jobs.scrape_job,
    cron_schedule="0 * * * *",  # every hour
)

defs = Definitions(
    assets=all_assets,
    jobs=[
        jobs.sittings_job,
        jobs.scrape_job,
    ],
    sensors=[
        sittings_sensor,
        my_discord_on_run_frontend_success,
        my_discord_on_run_failure,
    ],
    schedules=[scrape_schedule],
)
