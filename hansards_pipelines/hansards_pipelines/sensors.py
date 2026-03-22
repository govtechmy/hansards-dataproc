from dagster import (
    sensor,
    DagsterRunStatus,
    SensorEvaluationContext,
    RunRequest,
    RunsFilter,
    SensorResult,
)
import json
from hansards_pipelines.assets import (
    sitting_partitions_def,
    sitting_legacy_partitions_def,
    s3_client,
)
from hansards_pipelines.jobs import sittings_job, move_arkib_pdfs_job, sittings_legacy_job, register_sitting_legacy_partition_job
from hansards_pipelines.settings import PENDING_QUEUE_KEY, READY_QUEUE_KEY, S3_DATAPROC_BUCKET


@sensor(job=sittings_job, minimum_interval_seconds=900)
def sittings_sensor(context: SensorEvaluationContext):
    """Set up partitions
    One partition is one dewan, one sitting (date)
    One partition is one file still in new/
    TODO: implement actual moving of parsed PDFs from new folder
    """
    # get new pdfs
    source = "active"
    # get all partitions in s3
    response = s3_client.list_objects_v2(
        Bucket=S3_DATAPROC_BUCKET,
        Prefix="new/",
    )
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
            run_requests.append(RunRequest(partition_key=pdf_name,  tags={"pdf_source": source}))
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

@sensor(job=move_arkib_pdfs_job, minimum_interval_seconds=300)
def trigger_arkib_pdf_move_sensor(context):
    """
    Trigger move_arkib_pdfs_job when there is a pending arkib_partitions.pending.json file in S3_PUBLIC_BUCKET
    """
    try:
        obj = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=PENDING_QUEUE_KEY,
        )
    except s3_client.exceptions.ClientError:
        return SensorResult()

    payload = json.loads(obj["Body"].read())

    partitions = payload.get("partitions", [])

    if not partitions:
        context.log.info("Arkib queue json exists but no partitions found. Skipping trigger.")
        return SensorResult()

    return SensorResult(
        run_requests=[
            RunRequest(
                run_key=f"arkib_move_{PENDING_QUEUE_KEY}",
            )
        ]
    )


@sensor(job=sittings_job, minimum_interval_seconds=300)
def trigger_sittings_job_arkib_sensor(context):
    """
    Trigger sittings_job runs for partitions listed in arkib_partitions.ready.json in S3_DATAPROC_BUCKET
    """

    try:
        obj = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=READY_QUEUE_KEY,
        )
    except s3_client.exceptions.ClientError:
        return SensorResult()

    payload = json.loads(obj["Body"].read())

    partitions = payload.get("partitions", [])

    run_requests = [
        RunRequest(
            partition_key=p,
            run_key=f"arkib_{payload['generated_at']}_{p}",
            tags={
                "pdf_source": "arkib",
                "reason": "arkib_refresh",
            },
        )
        for p in partitions
    ]

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=
        [sitting_partitions_def.build_add_request(partitions)] if partitions else [],
    )



@sensor(job=sittings_legacy_job, minimum_interval_seconds=300)
def trigger_sittings_legacy_job(context):
    """
    Trigger sittings_legacy_job for partitions listed in legacy_sittings.ready.json.
    """

    LEGACY_READY_QUEUE_KEY = "legacy/queue/legacy_partitions.ready.json"
    try:
        obj = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=LEGACY_READY_QUEUE_KEY,
        )
    except s3_client.exceptions.ClientError:
        return SensorResult()

    payload = json.loads(obj["Body"].read())
    partitions = payload.get("partitions", [])

    if not partitions:
        return SensorResult()

    run_requests = [
        RunRequest(
            partition_key=p,
            run_key=f"legacy-{p}",
            tags={
                "pdf_source": "legacy",
                "range": "1959_2007",
            },
        )
        for p in partitions
    ]

    return SensorResult(
        run_requests=run_requests,
        dynamic_partitions_requests=[
            sitting_legacy_partitions_def.build_add_request(partitions)
        ],
    )


@sensor(
    job=register_sitting_legacy_partition_job,
    minimum_interval_seconds=300,
)
def trigger_register_sitting_legacy_partition_sensor(context):
    """
    This sensor checks for the presence of a legacy_partitions.ready.json file in S3.
    If found, it reads the partitions listed in the file and registers them
    as dynamic partitions for the 'sitting_legacy_partitions_def' partitioned asset.
    It also triggers runs of the 'register_sitting_legacy_partition_job' for each partition.
    """

    LEGACY_READY_QUEUE_KEY = "legacy/queue/legacy_partitions.ready.json"

    try:
        obj = s3_client.get_object(
            Bucket=S3_DATAPROC_BUCKET,
            Key=LEGACY_READY_QUEUE_KEY,
        )
    except s3_client.exceptions.ClientError:
        return SensorResult()

    payload = json.loads(obj["Body"].read())
    partitions = payload.get("partitions", [])

    if not partitions:
        return SensorResult()

    return SensorResult(
        dynamic_partitions_requests=[
            sitting_legacy_partitions_def.build_add_request(partitions)
        ],
        run_requests=[
            RunRequest(run_key=f"register-{p}", partition_key=None)
            for p in partitions
        ],
    )
