def refresh_projection(services):
    """Rebuild in-process knowledge snapshot after offline ingestion; restart server afterwards."""
    services.rag.refresh()
