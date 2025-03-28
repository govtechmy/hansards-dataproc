import requests
import datetime
import json
from dagster import EnvVar

DAGIT_BASE_URL = EnvVar("DAGIT_BASE_URL").get_value()
WEBHOOK_URL = EnvVar("DISCORD_WEBHOOK_URL").get_value()


def send_discord_message(
    run_id: str,
    title: str,
    color: int,
    fields: list,
    footer: dict,
    context,
    description: str = None,
    deeplink=True,
):

    # Create message content
    message = {
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": fields,
                "footer": footer,
            }
        ]
    }
    # Add link to Dagster instance (if configured)
    if deeplink:
        run_url = f"{DAGIT_BASE_URL}runs/{run_id}"
        message["embeds"][0]["url"] = run_url
        message["embeds"][0]["fields"].append(
            {
                "name": "Details",
                "value": f"[View in Dagster]({run_url})",
                "inline": False,
            }
        )
    if description:
        message["embeds"][0]["description"] = description

    # Send the message to Discord
    response = requests.post(
        WEBHOOK_URL,
        data=json.dumps(message),
        headers={"Content-Type": "application/json"},
    )
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        context.log.error(f"Failed to send Discord message: {e}")
        context.log.error(f"Response content: {response.text}")
        raise
