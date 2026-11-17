"""Shared conversion of Malay ordinal numbers."""
import re
from typing import Optional


def malay_ordinal_to_number(ordinal_text: str) -> Optional[int]:
    """
    Convert Malay ordinal words to numbers.
    Handles simple ordinals (pertama-kesepuluh), teens (belas), and tens (puluh).
    """
    ordinal_lower = ordinal_text.lower().strip()
    normalized = " ".join(ordinal_lower.split())

    # Base numbers (1-10)
    base_numbers = {
        "khas":0,"pertama": 1, "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5,
        "keenam": 6, "ketujuh": 7, "kelapan": 8, "kesembilan": 9, "kesepuluh": 10
    }
    
    if normalized in base_numbers:
        return base_numbers[normalized]
    
    # Teens (11-19) - ends with "belas"
    if "belas" in normalized:
        if normalized == "kesebelas":
            return 11
        
        belas_match = re.match(r"^ke(\w+)\s+belas$", normalized)
        if belas_match:
            stem = belas_match.group(1)
            cardinal_map = {
                "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
                "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9,
            }
            digit = cardinal_map.get(stem)
            if digit is not None:
                return 10 + digit
    
    # Tens (20-90+) - contains "puluh"
    if "puluh" in normalized:
        parts = normalized.split("puluh")
        tens_part = parts[0].strip()
        ones_part = parts[1].strip() if len(parts) > 1 else ""
        
        base_to_tens = {
            "kedua": 2, "ketiga": 3, "keempat": 4, "kelima": 5,
            "keenam": 6, "ketujuh": 7, "kelapan": 8, "kesembilan": 9
        }
        
        tens_digit = base_to_tens.get(tens_part, 0)
        ones_digit = 0
        
        if ones_part:
            ones_map = {
                "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
                "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9
            }
            ones_digit = ones_map.get(ones_part, 0)
        
        return tens_digit * 10 + ones_digit
    
    return None
