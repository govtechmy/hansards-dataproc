from dagster import (
    run_status_sensor,
    sensor,
    DagsterRunStatus,
    RunStatusSensorContext,
    SensorEvaluationContext,
    AssetMaterialization,
    asset_sensor,
    RunRequest,
    SkipReason,
    RunsFilter,
    SensorResult,
    AssetKey,
    define_asset_job,
    EventRecordsFilter,
    DagsterEventType,
)
import requests
import datetime
import json
from hansards_pipelines.utils.text_utils import get_sitting_object
from hansards_pipelines.utils.discord_utils import send_discord_message
from hansards_pipelines.assets import (
    sitting_partitions_def,
    S3_DATAPROC_BUCKET,
    s3_client,
)
from hansards_pipelines.jobs import sittings_job, parliamentary_cycle_job
from hansards_pipelines.assets import FRONTEND_URL

# revalidate_frontend_job = define_asset_job(
#     "revalidate_frontend_job", [revalidate_frontend]
# )


@sensor(job=sittings_job, minimum_interval_seconds=900)
def sittings_sensor(context: SensorEvaluationContext):
    """Set up partitions
    One partition is one dewan, one sitting (date)
    One partition is one file still in new/
    TODO: implement actual moving of parsed PDFs from new folder
    """
    # get new pdfs

    # get all partitions in s3
    response = s3_client.list_objects_v2(Bucket=S3_DATAPROC_BUCKET, Prefix="new/")
    new_pdfs = []
    for obj in response.get("Contents", []):
        # key new/dewannegara/DN-03122024.pdf
        if obj["Key"].lower().endswith(".pdf"):
            # take filename only without extension: DN-03122024
            pdf_name = obj["Key"].split("/")[-1].split(".")[0]
            context.log.info(f"New PDF: {pdf_name}")

            # TODO: ensure date portion is 8 digits DDMMYYYY
            date = pdf_name.split("-")[1]
            if len(date) != 8:
                context.log.warning(
                    f"WARNING: Date portion is not 8 digits: {date}. Skipping"
                )
            new_pdfs.append(pdf_name)

    # TODO: REMOVE THIS FOR TESTING ONLY
    # new_pdfs = new_pdfs[:5]
    context.log.info(f"New PDFs: {new_pdfs}")

    ## Only Create New Runs if Partition has no active runs
    # Get runs for each partition
    run_requests = []
    dynamic_partition_additions = []

    for pdf_name in new_pdfs:
        # Get latest run for this partition using Dagster's RunsFilter
        runs = context.instance.get_runs(
            filters=RunsFilter(
                tags={"dagster/partition": pdf_name},
                statuses=[
                    DagsterRunStatus.STARTED,
                    DagsterRunStatus.STARTING,
                    DagsterRunStatus.QUEUED,
                    DagsterRunStatus.SUCCESS,
                    DagsterRunStatus.FAILURE,
                ],
            )
        )

        # Check if there are any active runs
        has_active_run = any(runs)

        if not has_active_run:
            run_requests.append(RunRequest(partition_key=pdf_name))
            dynamic_partition_additions.append(pdf_name)
            context.log.info(f"Creating new run for partition: {pdf_name}")
        else:
            context.log.info(f"Skipping partition {pdf_name} - has active run")

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=(
            [sitting_partitions_def.build_add_request(dynamic_partition_additions)]
            if dynamic_partition_additions
            else []
        ),
    )


@run_status_sensor(run_status=DagsterRunStatus.SUCCESS, job_selection=[sittings_job])
def my_discord_on_run_frontend_success(context: RunStatusSensorContext):
    """
    Send a notification to Discord when a Dagster run succeeds.

    This sensor uses a Discord webhook to post messages about successful pipeline runs.
    Configure the DISCORD_WEBHOOK_URL environment variable to use this sensor.

    This sensor is triggered when the revalidate_frontend job succeeds. However, tagging to the revalidate_frontend job
    does not capture the Materialized Result metadata from the asset.
    """

    # Get information about the run
    context.log.info(f"Event: {context.dagster_event}")
    run = context.dagster_run
    context.log.info(f"Run : {run}")
    run_id = run.run_id
    job_name = run.job_name
    if context.partition_key:
        partition_key = context.partition_key
        sitting_object = get_sitting_object(partition_key)
        hansard_route = f"/hansard/{sitting_object['house_display']}/{sitting_object['proper_date_str']}"
        fe_url = f"{FRONTEND_URL}{hansard_route}"
    else:
        partition_key = "unknown"
        fe_url = "unknown"
    if run.asset_selection:
        asset_key = next(iter(run.asset_selection))
        asset_name = asset_key.path[-1] if asset_key and asset_key.path else job_name
    else:
        asset_name = (
            run.step_keys_to_execute[0] if run.step_keys_to_execute else job_name
        )

    # Format completion time
    completion_time = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # run config: run_config={'ops': {'revalidate_frontend': {'config': {'partition': 'DN-10032025'}}}}
    # run_config = run.run_config
    # if (
    #     run_config
    #     and "ops" in run_config
    #     and "revalidate_frontend" in run_config["ops"]
    #     and "config" in run_config["ops"]["revalidate_frontend"]
    #     and "partition" in run_config["ops"]["revalidate_frontend"]["config"]
    # ):
    #     partition = run_config["ops"]["revalidate_frontend"]["config"]["partition"]
    #     sitting_object = get_sitting_object(partition)
    #     hansard_route = f"/hansard/{sitting_object['house_display']}/{sitting_object['proper_date_str']}"
    #     fe_url = f"{FRONTEND_URL}{hansard_route}"
    # else:
    #     raise ValueError("No partition found in run config")

    # metadata not available after tagging to the revalidate_frontend job
    # if (
    #     "metadata" in context.dagster_event
    #     and context.dagster_event.metadata
    #     and "hansard_route" in context.dagster_event.metadata
    # ):
    #     fe_url = f"{FRONTEND_URL}{context.dagster_event.metadata['hansard_route']}"
    # else:
    #     raise ValueError("No hansard route found in metadata")

    message_fields = [
        # {"name": "Partition", "value": partition_key, "inline": True},
        {"name": "FE Link", "value": f"[View in FE]({fe_url})", "inline": True},
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

    # Format completion time
    failure_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Create message content
    message_fields = [
        {"name": "Partition", "value": partition_key, "inline": True},
        {"name": "Run ID", "value": run_id, "inline": True},
        {"name": "Failed At", "value": failure_time, "inline": True},
    ]
    footer = {"text": "Hansards Data Pipeline"}
    # Stack trace in description
    stack_trace, failure_node_handle = extract_stack_trace(context.dagster_event)
    description = f"Stack trace:\n```\n{stack_trace}```"
    # Send the message to Discord
    try:
        send_discord_message(
            run_id,
            f"❌ {failure_node_handle} Failed",
            15158332,
            message_fields,
            footer,
            context,
            description=description,
        )
        context.log.info(
            f"Successfully sent Discord notification for failed run {run_id}"
        )
    except Exception as e:
        context.log.error(f"Failed to send Discord notification: {str(e)}")


# @asset_sensor(
#     asset_key=AssetKey("insert_to_prod_db"),
#     job=revalidate_frontend_job,
#     minimum_interval_seconds=60,
# )
# def ingest_success_sensor(context: SensorEvaluationContext, asset_event):

#     materialization: AssetMaterialization = (
#         asset_event.dagster_event.event_specific_data.materialization
#     )

#     if materialization.metadata["revalidate_frontend"]:
#         yield RunRequest(
#             run_key=context.cursor,
#             run_config={
#                 "ops": {
#                     "revalidate_frontend": {
#                         "config": {"partition": materialization.partition}
#                     }
#                 }
#             },
#         )
#     else:
#         yield SkipReason("Asset materialization skipped for backfills")


def extract_stack_trace(dagster_event):
    """Extract stack trace from a DagsterEvent, preserving newlines.

    Handles both main error stack trace and cause stack trace if available.
    """
    full_trace = []
    failure_node_handle = None
    # Try to get the main stack trace
    if (
        hasattr(dagster_event, "event_specific_data")
        and dagster_event.event_specific_data
    ):
        if (
            hasattr(dagster_event.event_specific_data, "error")
            and dagster_event.event_specific_data.error
        ):
            # Direct error on the event
            error_info = dagster_event.event_specific_data.error
            if hasattr(error_info, "stack") and error_info.stack:
                full_trace.append("Main error:")
                full_trace.append("".join(error_info.stack))

            # Check for cause
            if hasattr(error_info, "cause") and error_info.cause:
                full_trace.append("\nCaused by:")
                full_trace.append("".join(error_info.cause.stack))

        # Check for step failure event
        elif hasattr(dagster_event.event_specific_data, "first_step_failure_event"):
            step_event = dagster_event.event_specific_data.first_step_failure_event
            if (
                hasattr(step_event, "event_specific_data")
                and step_event.event_specific_data
            ):
                if (
                    hasattr(step_event.event_specific_data, "error")
                    and step_event.event_specific_data.error
                ):
                    error_info = step_event.event_specific_data.error
                    # if hasattr(error_info, "stack") and error_info.stack:
                    #     full_trace.append("Main error:")
                    #     full_trace.append("".join(error_info.stack))

                    # Check for cause
                    if hasattr(error_info, "cause") and error_info.cause:
                        full_trace.append("\nCaused by:")
                        full_trace.append("".join(error_info.cause.stack))
            if hasattr(step_event, "step_handle") and step_event.step_handle:
                step_handle = step_event.step_handle
                if hasattr(step_handle, "node_handle") and step_handle.node_handle:
                    failure_node_handle = step_handle.node_handle.name

    return (
        "\n".join(full_trace) if full_trace else "No stack trace available",
        failure_node_handle,
    )


@sensor(
    job=parliamentary_cycle_job,
    minimum_interval_seconds=3600,  # Run once per hour
    description="Automatically scrape parliamentary cycle data hourly from Portal Rasmi Parlimen"
)
def parliamentary_cycle_sensor(context: SensorEvaluationContext):
    """
    Sensor that triggers scrape_parliamentary_cycle hourly to keep parliamentary cycle data up-to-date.
    
    This ensures new Parliament terms, sessions (Penggal), and meetings (Mesyuarat) are automatically
    detected and inserted into the database without manual intervention.
    """
    return RunRequest(
        run_key=f"parliamentary_cycle_{context.cursor or '0'}",
        tags={
            "source": "parliamentary_cycle_sensor",
            "triggered_at": context.evaluation_time.isoformat() if context.evaluation_time else "unknown"
        }
    )
