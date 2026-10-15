"""Shared token rules for ingestion and database maintenance."""

import unicodedata
from functools import lru_cache


@lru_cache(maxsize=131072)
def punctuation_only(token):
    """Flag empty tokens or tokens made entirely of punctuation/whitespace."""
    return isinstance(token, str) and all(
        char.isspace() or unicodedata.category(char).startswith("P") for char in token
    )
