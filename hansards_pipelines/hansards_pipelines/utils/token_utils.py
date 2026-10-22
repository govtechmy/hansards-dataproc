"""Shared token rules for ingestion and database maintenance."""

import unicodedata
from functools import lru_cache


@lru_cache(maxsize=131072)
def punctuation_only(token):
    """Flag empty tokens or tokens made entirely of punctuation/whitespace."""
    return isinstance(token, str) and all(
        char.isspace() or unicodedata.category(char).startswith("P") for char in token
    )


@lru_cache(maxsize=131072)
def punctuation_or_symbol_only(token):
    """Flag standalone punctuation/symbols; preserve tokens with letters/digits.

    Emoji variation selectors and joiners are formatting for a symbol sequence,
    so they must not cause a symbol-only token to survive.
    """
    return isinstance(token, str) and all(
        char.isspace()
        or unicodedata.category(char).startswith(("P", "S"))
        or char in ("\ufe0e", "\ufe0f", "\u200d")
        for char in token
    )
