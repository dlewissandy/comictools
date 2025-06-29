

def extract_format_keys(fmt) -> set[str]:
    from string import Formatter
    """
    Extracts the field names from a format string.
    Args:
        fmt (str): The format string to parse.
    Returns:
        set: A set of field names found in the format string.
    """
    return {field_name for _, field_name, _, _ in Formatter().parse(fmt) if field_name}

if __name__ == "__main__":
    fmt = "{name} is {age} years old and lives in {city}."
    keys = extract_format_keys(fmt)
    print(f"Extracted keys: {keys}")  # Output: {'name', 'age', 'city'}
    
    fmt2 = "Hello, {user.name}! You have {user.notifications} new notifications."
    keys2 = extract_format_keys(fmt2)
    print(f"Extracted keys: {keys2}")  # Output: {'user.name', 'user.notifications'}