from app.memory.preference_extractor import extract_preferences
def refresh_explicit_preferences(repository,user,messages):
    changes={}
    for message in messages:
        if message['role']=='user': changes.update(extract_preferences(message['content']))
    if changes: repository.update(user,changes)
    return changes
