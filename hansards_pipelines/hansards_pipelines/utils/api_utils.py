"""Fetch reference records with explicit HTTP and response-shape checks."""

import requests


def fetch_reference_records(base_url, resource):
    if not base_url:
        raise ValueError("API base URL is not configured")
    url = f"{base_url.rstrip('/')}/api/{resource.strip('/')}"
    response = requests.get(url, timeout=(10, 60))
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, list) or not data or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"Expected a non-empty list of records from {url}; received {type(data).__name__}")
    return data
