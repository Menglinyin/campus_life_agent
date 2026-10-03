from pathlib import Path
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAMPUS_", env_file=".env", extra="ignore")
    demo: bool = True
    database_url: str = "sqlite:///./campus.db"
    user_tokens: dict[str,str] = {"demo-token": "demo-student"}
    redis_url: str = ""
    session_ttl: int = Field(259200, ge=60)
    history_turns: int = Field(10, ge=1, le=30)
    embedding_backend: str = "demo"
    embedding_model: str = "BAAI/bge-m3"
    embedding_fp16: bool = False
    embedding_max_tokens: int = Field(1024, ge=128, le=8192)
    chunk_tokens: int = Field(512, ge=32)
    chunk_overlap: int = Field(64, ge=0)
    chroma_path: str = ""
    retrieval_k: int = Field(4, ge=1, le=20)
    reranker_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = "local"
    llm_model: str = "Qwen3-32B-AWQ"
    max_tool_steps: int = Field(4, ge=1, le=8)
    model_timeout: float = 60
    tool_timeout: float = 15
    mcp_servers: dict[str,str] = {}
    mcp_token: str = ""
    skill_root: Path = Path(__file__).resolve().parents[1] / "skill_packages"
    asr_url: str = ""
    tts_url: str = ""
    @model_validator(mode="after")
    def validate_settings(self):
        if self.chunk_overlap >= self.chunk_tokens or self.chunk_tokens > self.embedding_max_tokens - 2:
            raise ValueError("chunk_overlap < chunk_tokens <= embedding_max_tokens - 2")
        if self.embedding_backend not in {"demo", "bge"}:
            raise ValueError("embedding_backend must be demo or bge")
        if not self.demo and ("demo-token" in self.user_tokens or not self.llm_base_url or self.embedding_backend != "bge"):
            raise ValueError("Production requires new user tokens, vLLM and BGE")
        return self
