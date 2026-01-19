from dagster import define_asset_job
from . import assets

parliamentary_cycle_job = define_asset_job(
    "parliamentary_cycle_job",
    selection=[assets.scrape_parliamentary_cycle],
)

scrape_job = define_asset_job(
    "scrape_website_job",
    selection=[assets.scrape_website, assets.move_and_rename_all_hansards],
)

sittings_job = define_asset_job(
    "sittings_job",
    selection=[
        assets.dg_parse_hansard,
        assets.dg_get_categories,
        assets.dg_post_parsing_edits,
        assets.dg_pre_tabulate,
        assets.dg_edit_hansards,
        assets.dg_tabulate,
        assets.remove_parsed_hansards,
        assets.prepare_db_payload,
        assets.insert_to_dev_db,
        # assets.insert_to_prod_db,
    ],
)
