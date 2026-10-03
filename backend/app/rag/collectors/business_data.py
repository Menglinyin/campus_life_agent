def export_business_rows(repository,kind,date):
    # Business truth is queried from SQL, never inferred from stale vectors.
    return repository.list(kind,date)
