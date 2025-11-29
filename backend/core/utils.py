"""
Utility functions for NetVault
Centralized utilities to avoid code duplication
"""


def validate_csv_safe(value: str, field_name: str = 'Field') -> str:
    """
    Validate that value is safe for CSV export (no formula injection)

    Args:
        value: Value to validate
        field_name: Field name for error message

    Returns:
        The original value if safe

    Raises:
        ValueError: If value starts with dangerous CSV formula characters
    """
    if not isinstance(value, str):
        value = str(value)

    dangerous_chars = ['=', '+', '-', '@', '\t', '\r']

    if value and value[0] in dangerous_chars:
        raise ValueError(
            f'{field_name} cannot start with "{value[0]}" character (CSV formula injection risk). '
            f'Please remove or escape this character.'
        )

    return value


def sanitize_csv_value(value):
    """
    Sanitize value for CSV export to prevent formula injection

    This should be used ONLY when exporting to CSV, NOT when storing in database.
    Database should store raw values without escaping.

    Args:
        value: Value to sanitize for CSV export

    Returns:
        Sanitized value with single quote prefix if starts with dangerous char
    """
    if not isinstance(value, str):
        value = str(value)

    dangerous_chars = ['=', '+', '-', '@', '\t', '\r']

    if value and value[0] in dangerous_chars:
        return "'" + value

    return value
