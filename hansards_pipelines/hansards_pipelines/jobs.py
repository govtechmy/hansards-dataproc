from dagster import define_asset_job, AssetSelection
from . import assets

scrape_parliamentary_cycle_job = define_asset_job(
    "scrape_parliamentary_cycle_job",
    selection=[
        # assets.scrape_parliamentary_cycle_arkib,
        assets.scrape_parliamentary_cycle_active,
    ],
)

scrape_job = define_asset_job(
    "scrape_website_job",
    selection=[assets.scrape_website, assets.move_and_rename_all_hansards],
)

sittings_job = define_asset_job(
    "sittings_job",
    selection=AssetSelection.keys(
        "dg_parse_hansard",
        "dg_get_categories",
        "dg_post_parsing_edits",
        "dg_pre_tabulate",
        "dg_edit_hansards",
        "dg_tabulate",
        "remove_parsed_hansards",
        "prepare_db_payload",
        "direct_insert_to_db",
        # "insert_to_dev_db",
        # "insert_to_prod_db",
    ),
)

scrape_arkib_job = define_asset_job(
    "scrape_arkib_website_job",
    selection=[assets.scrape_website_arkib, assets.move_arkib_pdfs_to_public, assets.dg_build_arkib_partition_queue],
)


author_load_job = define_asset_job(
    "author_load_job",
    selection=[assets.load_author_data_to_db],
)

move_arkib_pdfs_job = define_asset_job(
    "move_arkib_pdfs_job",
    selection=[assets.dg_move_arkib_pdf_to_s3_root],
)