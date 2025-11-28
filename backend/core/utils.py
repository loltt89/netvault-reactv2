"""
Utility functions for NetVault
Centralized utilities to avoid code duplication
"""


def sanitize_csv_value(value):
    """
    Sanitize value to prevent CSV injection attacks
    Prevents formula injection by escaping dangerous characters
    """
    if not isinstance(value, str):
        value = str(value)

    dangerous_chars = ['=', '+', '-', '@', '\t', '\r']

    if value and value[0] in dangerous_chars:
        return "'" + value

    return value
