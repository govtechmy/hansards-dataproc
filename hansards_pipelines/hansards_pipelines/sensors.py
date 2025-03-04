from dagster import (
    run_status_sensor,
    DagsterRunStatus,
    RunStatusSensorContext,
    SensorEvaluationContext,
    AssetMaterialization,
    asset_sensor,
    RunRequest,
    SkipReason,
    AssetKey,
    define_asset_job,
)
import requests
import datetime
import json
from hansards_pipelines.utils.discord_utils import send_discord_message
from hansards_pipelines.assets import revalidate_frontend


@run_status_sensor(run_status=DagsterRunStatus.SUCCESS)
def my_discord_on_run_success(context: RunStatusSensorContext):
    """
    Send a notification to Discord when a Dagster run succeeds.

    This sensor uses a Discord webhook to post messages about successful pipeline runs.
    Configure the DISCORD_WEBHOOK_URL environment variable to use this sensor.
    """

    # Get information about the run
    context.log.info(f"Event: {context.dagster_event}")
    run = context.dagster_run
    context.log.info(f"Run : {run}")
    run_id = run.run_id
    job_name = run.job_name
    if context.partition_key:
        partition_key = context.partition_key
    else:
        partition_key = "unknown"
    if run.asset_selection:
        asset_key = next(iter(run.asset_selection))
        asset_name = asset_key.path[-1] if asset_key and asset_key.path else job_name
    else:
        asset_name = (
            run.step_keys_to_execute[0] if run.step_keys_to_execute else job_name
        )

    # Format completion time
    completion_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    message_fields = [
        {"name": "Partition", "value": partition_key, "inline": True},
        {"name": "Run ID", "value": run_id, "inline": True},
        {"name": "Completed At", "value": completion_time, "inline": True},
    ]
    footer = {"text": "Hansards Data Pipeline"}

    # Send the message to Discord
    try:
        send_discord_message(
            run_id,
            f"✅ {asset_name} Successful",
            3066993,
            message_fields,
            footer,
            context,
        )
        context.log.info(f"Successfully sent Discord notification for run {run_id}")
    except Exception as e:
        context.log.error(f"Failed to send Discord notification: {str(e)}")


@run_status_sensor(run_status=DagsterRunStatus.FAILURE)
def my_discord_on_run_failure(context: RunStatusSensorContext):
    """
    Send a notification to Discord when a Dagster run fails.

    This sensor uses a Discord webhook to post messages about failed pipeline runs.
    Configure the DISCORD_WEBHOOK_URL environment variable to use this sensor.
    """
    # Get information about the run
    context.log.info(f"Event: {context.dagster_event}")
    run = context.dagster_run
    context.log.info(f"Run : {run}")
    if context.partition_key:
        partition_key = context.partition_key
    else:
        partition_key = "unknown"

    run_id = run.run_id
    job_name = run.job_name
    if run.asset_selection:
        asset_key = next(iter(run.asset_selection))
        asset_name = asset_key.path[-1] if asset_key and asset_key.path else job_name
    else:
        asset_name = (
            run.step_keys_to_execute[0] if run.step_keys_to_execute else job_name
        )

    # Format completion time
    failure_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Create message content
    message_fields = [
        {"name": "Partition", "value": partition_key, "inline": True},
        {"name": "Run ID", "value": run_id, "inline": True},
        {"name": "Failed At", "value": failure_time, "inline": True},
    ]
    footer = {"text": "Hansards Data Pipeline"}
    # Send the message to Discord
    try:
        send_discord_message(
            run_id,
            f"❌ {asset_name} Failed",
            15158332,
            message_fields,
            footer,
            context,
        )
        context.log.info(
            f"Successfully sent Discord notification for failed run {run_id}"
        )
    except Exception as e:
        context.log.error(f"Failed to send Discord notification: {str(e)}")


revalidate_frontend_job = define_asset_job(
    "revalidate_frontend_job", [revalidate_frontend]
)


@asset_sensor(asset_key=AssetKey("insert_to_db"), job=revalidate_frontend_job)
def ingest_success_sensor(context: SensorEvaluationContext, asset_event):
    materialization: AssetMaterialization = (
        asset_event.dagster_event.event_specific_data.materialization
    )
    context.log.info(f"materialization: {materialization}")

    if materialization.metadata["revalidate_frontend"]:
        yield RunRequest(
            run_key=context.cursor,
            run_config={
                "ops": {
                    "revalidate_frontend": {
                        "config": {"partition": materialization.partition}
                    }
                }
            },
        )
    else:
        yield SkipReason("Asset materialization skipped for backfills")
