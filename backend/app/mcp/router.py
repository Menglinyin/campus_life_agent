from app.skills.policies import ALLOWED_TOOLS
def server_for(settings,name):
    if name not in ALLOWED_TOOLS: raise ValueError("Tool is not allowlisted")
    return settings.mcp_servers.get(name)
