import json

def promote_queue(
    *,
    s3_client,
    bucket: str,
    pending_key: str,
    ready_key: str,
):
    """
    Promote a queue JSON from pending → ready.
    - Reads pending_key
    - Writes ready_key (same payload)
    - Deletes pending_key
    """

    # read pending queue
    obj = s3_client.get_object(
        Bucket=bucket,
        Key=pending_key,
    )
    payload = json.loads(obj["Body"].read())

    # write ready queue
    s3_client.put_object(
        Bucket=bucket,
        Key=ready_key,
        Body=json.dumps(payload, indent=2).encode(),
        ContentType="application/json",
    )

    # delete pending queue
    s3_client.delete_object(
        Bucket=bucket,
        Key=pending_key,
    )
