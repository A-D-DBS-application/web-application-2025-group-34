"""
Utility functies en template filters voor de applicatie
Centrale plek voor herbruikbare helper functies
"""
from datetime import datetime
from typing import Optional, Any


def format_currency(value: Optional[float]) -> str:
    """
    Formats a float to a European currency string (e.g., 1.234,56)
    
    Args:
        value: Float value to format, or None
        
    Returns:
        Formatted currency string (e.g., "1.234,56")
    """
    if value is None:
        return "0,00"
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0,00"


def format_number(value: Optional[float], decimals: int = 2) -> str:
    """
    Format a number with European formatting (comma as decimal separator)
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted number string
    """
    if value is None:
        return "0" + ("," + "0" * decimals if decimals > 0 else "")
    try:
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "0" + ("," + "0" * decimals if decimals > 0 else "")


def format_percentage(value: Optional[float], decimals: int = 2, show_sign: bool = False) -> str:
    """
    Format a percentage value
    
    Args:
        value: Percentage value (e.g., 5.5 for 5.5%)
        decimals: Number of decimal places
        show_sign: Whether to show + sign for positive values
        
    Returns:
        Formatted percentage string (e.g., "5,50%")
    """
    if value is None:
        return "0,00%"
    try:
        sign = "+" if show_sign and float(value) >= 0 else ""
        return f"{sign}{format_number(value, decimals)}%"
    except (ValueError, TypeError):
        return "0,00%"


def format_date(date_obj: Optional[Any], format_str: str = "%d-%m-%Y", remove_leading_zeros: bool = False) -> str:
    """
    Format a date object to string
    
    Args:
        date_obj: Date object (datetime, date, or None)
        format_str: Format string (default: "%d-%m-%Y")
        remove_leading_zeros: Remove leading zeros from day/month
        
    Returns:
        Formatted date string
    """
    if date_obj is None:
        date_obj = datetime.now()
    
    if hasattr(date_obj, 'strftime'):
        date_str = date_obj.strftime(format_str)
        if remove_leading_zeros:
            # Remove leading zeros from day and month
            parts = date_str.split('-')
            if len(parts) >= 2:
                day = str(int(parts[0])) if parts[0].isdigit() else parts[0]
                month = str(int(parts[1])) if parts[1].isdigit() else parts[1]
                date_str = f"{day}-{month}-{parts[2]}" if len(parts) > 2 else f"{day}-{month}"
        return date_str
    return str(date_obj)


def format_transaction_date(date_obj: Optional[Any]) -> str:
    """
    Formats a date to 'd-m-Y' format without leading zeros (e.g., '1-9-2022')
    Supports datetime objects, date strings, and ISO format strings
    """
    if date_obj is None:
        return format_date(None, format_str="%d-%m-%Y", remove_leading_zeros=True)
    
    if isinstance(date_obj, str):
        # Probeer ISO format te parsen
        try:
            from datetime import datetime
            # Probeer verschillende formaten
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                try:
                    parsed_date = datetime.strptime(date_obj.split('+')[0].split('Z')[0], fmt)
                    return format_date(parsed_date, format_str="%d-%m-%Y", remove_leading_zeros=True)
                except ValueError:
                    continue
        except Exception:
            pass
    
    return format_date(date_obj, format_str="%d-%m-%Y", remove_leading_zeros=True)


def safe_get(data: dict, key: str, default: Any = 'N/A', format_func: Optional[callable] = None) -> Any:
    """
    Safely get a value from a dictionary with optional formatting
    
    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key not found or value is None/empty
        format_func: Optional function to format the value
        
    Returns:
        Value from dictionary or default
    """
    value = data.get(key)
    if value is None or value == '':
        return default
    if format_func:
        try:
            return format_func(value)
        except (ValueError, TypeError):
            return default
    return value

