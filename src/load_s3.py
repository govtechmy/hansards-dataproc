import os
import boto3
import json
import botocore
from datetime import datetime
from botocore.exceptions import ClientError
from urllib.parse import urljoin
from discord_webhook import DiscordWebhook, DiscordEmbed
from dotenv import load_dotenv
from config import INPUT_PIPELINE_DIR

load_dotenv()

s3_client = boto3.client("s3")

sqs = boto3.client("sqs")
QUEUE_URL = os.getenv("QUEUE_URL")


def rename_pdf(filename):
    """
    Renames the PDF file from <house_name>_<date>.pdf to <house_name>-<ddmmyyyy>.pdf
    """
    try:
        # Split the filename into house_name and date
        house_name, date_str = os.path.splitext(filename)[0].split("_")

        # Convert date string to datetime object
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")

        # Format the new date string
        new_date_str = date_obj.strftime("%d%m%Y")

        # Create the new filename
        new_filename = f"{house_name.upper()}-{new_date_str}.pdf"

        return new_filename
    except ValueError:
        print(f"Error: '{filename}' does not match the expected format.")
        return filename


def check_and_download():

    response = sqs.receive_message(
        QueueUrl=QUEUE_URL,
        MaxNumberOfMessages=10,
        VisibilityTimeout=30,
        WaitTimeSeconds=20,
    )

    # Check if any messages were received
    if "Messages" not in response:
        print("No messages in queue. Exiting.")
        return

    # Process each message
    for message in response["Messages"]:
        message_body = json.loads(message["Body"])
        s3_path = message_body.get("s3_path")

        if s3_path:
            try:
                # Extract bucket name and object key from S3 path
                bucket_name, object_key = s3_path.replace("s3://", "").split("/", 1)

                # Generate local file path
                original_filename = os.path.basename(object_key)
                new_filename = rename_pdf(original_filename)
                local_filename = os.path.join(INPUT_PIPELINE_DIR, new_filename)

                # Download the file from S3
                s3_client.download_file(bucket_name, object_key, local_filename)
                print(f"Downloaded {s3_path} to {local_filename}")

                # Delete the message from the queue
                sqs.delete_message(
                    QueueUrl=QUEUE_URL, ReceiptHandle=message["ReceiptHandle"]
                )
                print(f"Deleted message: {message['MessageId']}")

            except ClientError as e:
                print(f"Error processing message {message['MessageId']}: {e}")
        else:
            print(
                f"Message {message['MessageId']} does not contain 's3_path'. Skipping."
            )


if __name__ == "__main__":
    check_and_download()
