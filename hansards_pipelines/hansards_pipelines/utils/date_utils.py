"""
Date utility functions for normalizing dates to DD/MM/YYYY format.
"""
import pandas as pd


def normalize_date(date_str):
    """
    Normalize date to DD/MM/YYYY format.
    
    Handles multiple input formats:
    - DD/MM/YYYY or DD/MM/YY (with slashes)
    - YYYY-MM-DD or YYYY-MM (with hyphens)
    - YYYY (year only)
    """
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    if not date_str or date_str.lower() == "current":
        return None
    
    # Already in DD/MM/YYYY or similar format with slashes
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            day, month, year = parts[0], parts[1], parts[2]
            # Handle 2-digit years
            if len(year) == 2:
                year = f"19{year}" if int(year) > 50 else f"20{year}"
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    
    # Date with hyphens
    elif "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            # YYYY-MM-DD format
            return f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
        elif len(parts) == 2:
            # YYYY-MM format - use 01 as day for start dates
            return f"01/{parts[1].zfill(2)}/{parts[0]}"
    
    # Just a year (YYYY)
    else:
        if date_str.isdigit() and len(date_str) == 4:
            # Default to 01/01 when only year is known
            return f"01/01/{date_str}"
    
    return date_str  # Return as-is if format not recognized


def normalize_end_date_with_month_last_day(date_str):
    """
    Normalize end date to DD/MM/YYYY format, using last day of month for YYYY-MM format.
    
    Similar to normalize_date() but for end dates where YYYY-MM format should use
    the last day of the month instead of the 1st.
    """
    if pd.isna(date_str) or not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    if not date_str or date_str.lower() == "current":
        return None
    
    # Already in DD/MM/YYYY or similar format with slashes
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            day, month, year = parts[0], parts[1], parts[2]
            # Handle 2-digit years
            if len(year) == 2:
                year = f"19{year}" if int(year) > 50 else f"20{year}"
            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
    
    # Date with hyphens
    elif "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 3:
            # YYYY-MM-DD format
            return f"{parts[2].zfill(2)}/{parts[1].zfill(2)}/{parts[0]}"
        elif len(parts) == 2:
            # YYYY-MM format - use last day of month for end dates
            year = int(parts[0])
            month = parts[1].zfill(2)
            
            # Calculate last day of month, accounting for leap years
            month_days = {
                "01": 31, "02": 29 if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0) else 28,
                "03": 31, "04": 30, "05": 31, "06": 30,
                "07": 31, "08": 31, "09": 30, "10": 31,
                "11": 30, "12": 31
            }
            day = month_days.get(month, 31)
            return f"{str(day).zfill(2)}/{month}/{parts[0]}"
    
    # Just a year (YYYY) - use 01/01/YYYY (we don't know the actual date)
    else:
        if date_str.isdigit() and len(date_str) == 4:
            return f"01/01/{date_str}"
    
    return date_str  # Return as-is if format not recognized
