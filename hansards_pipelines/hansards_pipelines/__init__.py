from dagster import (
    Definitions,
    ScheduleDefinition,
    load_assets_from_modules,
    define_asset_job,
)

from . import assets
from .assets import sittings_job
from .sensors import (
    sittings_sensor,
    my_discord_on_run_frontend_success,
    my_discord_on_run_failure,
)

all_assets = load_assets_from_modules([assets])

scrape_job = define_asset_job(
    "scrape_website_job",
    selection=[assets.scrape_website, assets.move_and_rename_all_hansards],
)

scrape_schedule = ScheduleDefinition(
    job=scrape_job,
    cron_schedule="0 * * * *",  # every hour
)

defs = Definitions(
    assets=all_assets,
    jobs=[sittings_job],
    sensors=[
        sittings_sensor,
        my_discord_on_run_frontend_success,
        my_discord_on_run_failure,
    ],
    schedules=[scrape_schedule],
)
