"""Merge YAML, dotenv and environment, validate against existing Backend Settings.
No backend source modification is needed; launch.py exports validated settings.
"""
from pathlib import Path
import json
import os
import re
import sys
import yaml
from dotenv import dotenv_values

CONFIG_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
FILES = ("app.yaml", "memory.yaml", "rag.yaml", "mcp.yaml", "skills.yaml", "inference.yaml", "voice.yaml", "observability.yaml")
SECTIONS = {"settings", "notes", "implementation_constants", "examples"}
PROFILES = {"demo", "production"}
PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-(.*?))?\}")

class ConfigError(ValueError):
    pass

class UniqueLoader(yaml.SafeLoader):
    """Reject YAML duplicate keys instead of silently dropping earlier settings."""

def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str): raise ConfigError("YAML keys must be strings")
        if key in result: raise ConfigError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result
UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def read_yaml(path):
    try:
        document = yaml.load(Path(path).read_text(encoding="utf-8"), Loader=UniqueLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"Cannot read configuration file: {Path(path).name}") from exc
    if not isinstance(document, dict) or not set(document) <= SECTIONS:
        raise ConfigError(f"Invalid top-level sections: {Path(path).name}")
    settings = document.get("settings", {})
    if not isinstance(settings, dict): raise ConfigError("settings must be a mapping")
    return settings

def expand(value, env):
    if isinstance(value, str):
        def replace(match):
            name, default = match.groups()
            supplied = env.get(name)
            if supplied is not None and str(supplied) != "": return str(supplied)
            if default is not None: return default
            raise ConfigError(f"Missing required environment variable: {name}")
        return PATTERN.sub(replace, value)
    if isinstance(value, dict): return {key:expand(item,env) for key,item in value.items()}
    if isinstance(value, list): return [expand(item,env) for item in value]
    return value

def settings_class():
    if not (BACKEND_ROOT / "app/settings.py").is_file():
        raise ConfigError("Place config/ beside the completed backend/ folder first")
    # Reuse the actual model, not a copied schema that could diverge.
    if str(BACKEND_ROOT) not in sys.path: sys.path.insert(0,str(BACKEND_ROOT))
    from app.settings import Settings
    return Settings

def load_settings(profile="demo", env_file=None, environ=None, config_root=None):
    if profile not in PROFILES: raise ConfigError("profile must be demo or production")
    root=Path(config_root) if config_root else CONFIG_ROOT
    chosen=Path(env_file) if env_file else BACKEND_ROOT / ".env"
    if env_file and not chosen.is_file(): raise ConfigError("Explicit env file does not exist")
    env={k:v for k,v in dotenv_values(chosen,interpolate=False).items() if v is not None} if chosen.is_file() else {}
    env.update(dict(os.environ if environ is None else environ))
    merged={}
    for name in FILES:
        values=read_yaml(root/name)
        repeated=set(merged)&set(values)
        if repeated: raise ConfigError("Duplicate setting across base files: "+", ".join(sorted(repeated)))
        merged.update(values)
    if profile=="production": merged.update(read_yaml(root/'profiles/production.yaml'))
    Model=settings_class()
    unknown=set(merged)-set(Model.model_fields)
    if unknown: raise ConfigError("Unsupported Backend Settings: "+", ".join(sorted(unknown)))
    # Environment values override YAML BEFORE expansion, so an override can satisfy a placeholder.
    for field in Model.model_fields:
        key="CAMPUS_"+field.upper()
        if key in env: merged[field]=env[key]
    merged=expand(merged,env)
    for field in ["user_tokens","mcp_servers"]:
        if isinstance(merged.get(field),str):
            try: merged[field]=json.loads(merged[field])
            except ValueError as exc: raise ConfigError(f"{field} must be valid JSON") from exc
    path=Path(merged.get('skill_root','backend/skill_packages'))
    merged['skill_root']=str(path.resolve() if path.is_absolute() else (PROJECT_ROOT/path).resolve())
    try:
        # Init arguments have highest priority; dotenv and env were already explicitly merged.
        result=Model(_env_file=None,**merged)
    except ValueError as exc:
        # Pydantic errors may include input passwords/tokens: return field names only.
        fields=sorted({str(e['loc'][0]) if e['loc'] else 'settings' for e in exc.errors()}) if hasattr(exc,'errors') else ['settings']
        raise ConfigError('Invalid configuration fields: '+', '.join(fields)) from None
    if profile=='production':
        if result.demo: raise ConfigError('Production profile cannot enable demo mode')
        if not result.database_url.startswith('mysql+pymysql://') or not result.redis_url or not result.chroma_path:
            raise ConfigError('Production profile requires MySQL, Redis and Chroma paths')
        if not result.user_tokens or any('CHANGE_ME' in token or not user for token,user in result.user_tokens.items()):
            raise ConfigError('Replace placeholder user tokens')
        if 'CHANGE_ME' in result.database_url: raise ConfigError('Replace placeholder database password')
        if result.mcp_servers and not result.mcp_token: raise ConfigError('Configured production MCP requires service token')
    if not result.skill_root.is_dir(): raise ConfigError('skill_root is not an existing directory')
    return result

def settings_environment(settings):
    """Values go only to the backend child process; never print this mapping."""
    result={}
    for name,value in settings.model_dump(mode='json').items():
        if isinstance(value,(dict,list,bool)): value=json.dumps(value,ensure_ascii=False)
        result['CAMPUS_'+name.upper()]=str(value)
    return result
