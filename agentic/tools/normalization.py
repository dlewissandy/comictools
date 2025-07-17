def normalize_name(name: str) -> str:
    """
    Normalize a name by converting it to a string, and then 
    replacing the spaces with dashes.
    
    Args:
        name: The name to normalize.
    
    Returns:
        The normalized name.
    """
    return str(name).replace("-", " ").title()

def normalize_id(id: str) -> str:
    """
    Normalize an identifier by converting it to a string, and then 
    replacing the spaces with dashes.
    
    Args:
        series_id: The identifier to normalize.
    
    Returns:
        The normalized identifier.
    """
    return str(id).replace(" ", "-").lower()
