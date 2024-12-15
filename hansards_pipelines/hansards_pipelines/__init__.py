from dagster import (
    Definitions,
    ScheduleDefinition,
    load_assets_from_modules,
    define_asset_job,
)

from . import assets
from .assets import sitting_partitions_def, sittings_job, sittings_sensor

all_assets = load_assets_from_modules([assets])

# scrape_job = define_asset_job(
#     "scrape_website_job",
#     selection=[assets.scrape_website],
# )

# scrape_schedule = ScheduleDefinition(
#     job=scrape_job,
#     cron_schedule="0 * * * *",  # every hour
# )

defs = Definitions(
    assets=all_assets,
    jobs=[sittings_job],
    sensors=[sittings_sensor],
    # schedules=[scrape_schedule],
)
