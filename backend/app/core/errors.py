class ServiceError(Exception):
    """External dependency failed; details are logged, never sent to users."""
