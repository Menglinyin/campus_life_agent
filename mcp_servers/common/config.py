from pathlib import Path
import re
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT = Path(__file__).resolve().parents[2]

class ServerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='CAMPUS_', env_file=PROJECT/'backend/.env', extra='ignore')
    database_url: str = 'sqlite:///./backend/campus.db'
    mcp_token: SecretStr = SecretStr('')
    mcp_allowed_users: list[str] = ['demo-student']
    mcp_allowed_hosts: list[str] = ['127.0.0.1', 'localhost', '::1']
    mcp_allowed_origins: list[str] = []
    mcp_max_body_bytes: int = Field(65536, ge=4096, le=1048576)
    embedding_backend: str = 'demo'
    embedding_model: str = 'BAAI/bge-m3'
    embedding_fp16: bool = False
    embedding_max_tokens: int = Field(1024, ge=128, le=8192)
    chroma_path: str = ''
    retrieval_k: int = Field(4, ge=1, le=20)
    reranker_model: str = ''

    @field_validator('mcp_token')
    @classmethod
    def valid_token(cls, value):
        token=value.get_secret_value()
        if len(token)<24 or not token.isascii() or any(c.isspace() for c in token) or 'CHANGE_ME' in token:
            raise ValueError('Configure a new service token of at least 24 ASCII characters')
        return value

    @field_validator('mcp_allowed_users')
    @classmethod
    def valid_users(cls, values):
        if not values or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:@-]{0,63}', x) or x=='public' for x in values):
            raise ValueError('Configure non-public campus user IDs')
        return list(dict.fromkeys(values))

    @field_validator('mcp_allowed_hosts')
    @classmethod
    def valid_hosts(cls, values):
        if not values or any(not value or '*' in value or '/' in value for value in values):
            raise ValueError('Allowed hosts must be explicit hostnames/IPs without ports')
        return values

    @field_validator('embedding_backend')
    @classmethod
    def valid_embedding(cls, value):
        if value not in {'demo','bge'}: raise ValueError('Unsupported embedding backend')
        return value

    def require_token(self):
        # Pydantic does not validate omitted defaults unless validate_default=True.
        self.valid_token(self.mcp_token)
        return self
