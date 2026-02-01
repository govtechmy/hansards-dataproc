def promote_arkib_pdfs(
    *,
    s3_client,
    bucket: str,
    partitions: list[str],
    get_sitting_object,
    logger,
) -> int:
    moved_count = 0

    for partition in partitions:
        sitting = get_sitting_object(partition)

        # Build arkib key explicitly
        # Example: arkib/dewannegara/dn_2026-01-19.pdf
        house_folder = sitting["house_folder"]
        arkib_filename = f"{sitting['renamed_filename']}.pdf"
        arkib_key = f"arkib/{house_folder}/{arkib_filename}"
        root_key = sitting["renamed_filename_key"]

        logger.info(f"Promoting(moving) {arkib_key} -> {root_key}")

        pdf_obj = s3_client.get_object(Bucket=bucket, Key=arkib_key)

        s3_client.put_object(
            Bucket=bucket,
            Key=root_key,
            Body=pdf_obj["Body"].read(),
            ContentType="application/pdf",
        )

        s3_client.delete_object(Bucket=bucket, Key=arkib_key)

        moved_count += 1

    return moved_count

