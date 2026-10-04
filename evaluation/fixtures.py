"""Fixture databases are always temporary; never import into the user's DB."""
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
import json
import os
import sys
from tempfile import TemporaryDirectory

from evaluation.common import ROOT, PROJECT
sys.path.insert(0, str(PROJECT / "backend"))
from app.settings import Settings
from app.main import create_app
from app.storage.models import Classroom, Course, Dish, SecondhandListing, KnowledgeChunk
from sqlalchemy import delete


def isolated_settings(directory, with_model=False, embedding_backend="demo", chroma=False, reranker="", with_voice=False):
    # Supply every field explicitly: neither CAMPUS_* nor backend/.env may select a DB.
    values = {name: field.get_default(call_default_factory=True)
              for name, field in Settings.model_fields.items()}
    values.update(demo=True, database_url=f"sqlite:///{Path(directory) / 'evaluation.db'}",
                  user_tokens={os.environ.get("EVAL_TOKEN_A", "eval-a-token"): "eval-a",
                               os.environ.get("EVAL_TOKEN_B", "eval-b-token"): "eval-b"},
                  embedding_backend=embedding_backend,
                  chroma_path=str(Path(directory) / "chroma") if chroma else "",
                  reranker_model=reranker)
    if len(values["user_tokens"]) != 2:
        raise ValueError("Evaluation identities must use different tokens")
    if with_model:
        values.update(llm_base_url=os.environ.get("CAMPUS_LLM_BASE_URL", ""),
                      llm_api_key=os.environ.get("CAMPUS_LLM_API_KEY", "local"),
                      llm_model=os.environ.get("CAMPUS_LLM_MODEL", "Qwen3-32B-AWQ"))
        if not values["llm_base_url"]:
            raise ValueError("CAMPUS_LLM_BASE_URL required for model fixture server")
    if with_voice:
        values.update(asr_url=os.environ.get("CAMPUS_ASR_URL", ""), tts_url=os.environ.get("CAMPUS_TTS_URL", ""))
        if not values["asr_url"] and not values["tts_url"]:
            raise ValueError("Set CAMPUS_ASR_URL or CAMPUS_TTS_URL")
    return Settings(**values, _env_file=None)


def knowledge_chunks():
    return json.loads((ROOT / "fixtures" / "knowledge.json").read_text(encoding="utf-8"))


def populate(services):
    with services.db.transaction() as db:
        # This function is used exclusively with isolated_settings() temporary SQLite.
        if not services.settings.database_url.startswith("sqlite:"):
            raise ValueError("Fixtures require isolated SQLite")
        for model in (Classroom, Course, Dish, SecondhandListing, KnowledgeChunk):
            db.execute(delete(model))
        day = "2026-10-04"
        business = [
            (Classroom, "eval-room-open", {"name": "合成开放教室", "date": day, "available": True, "seats": 40}),
            (Classroom, "eval-room-closed", {"name": "合成占用教室", "date": day, "available": False, "seats": 50}),
            (Course, "eval-course-open", {"name": "合成AI导论", "date": day, "room": "合成202", "time": "14:00", "auditing_allowed": True}),
            (Course, "eval-course-closed", {"name": "合成限制课程", "date": day, "room": "合成203", "time": "16:00", "auditing_allowed": False}),
            (Dish, "eval-dish-veg", {"name": "合成素菜", "date": day, "price": 10, "spice": 0, "vegetarian": True, "rating": 4.8, "available": True}),
            (Dish, "eval-dish-spicy", {"name": "合成微辣荤菜", "date": day, "price": 15, "spice": 1, "vegetarian": False, "rating": 4.6, "available": True}),
            (Dish, "eval-dish-soldout", {"name": "合成售罄菜", "date": day, "price": 8, "spice": 0, "vegetarian": True, "rating": 5, "available": False}),
            (SecondhandListing, "eval-item-active", {"name": "合成台灯", "price": 20, "status": "active"}),
            (SecondhandListing, "eval-item-sold", {"name": "合成已售台灯", "price": 18, "status": "sold"}),
        ]
        for model, identifier, payload in business:
            db.add(model(id=identifier, payload=payload))
        for chunk in knowledge_chunks():
            db.add(KnowledgeChunk(**chunk))
    services.rag.refresh()


def fixture_app(settings):
    app = create_app(settings)
    original = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(app):
        async with original(app):
            populate(app.state.services)
            yield
    app.router.lifespan_context = lifespan
    return app


@contextmanager
def demo_client():
    from fastapi.testclient import TestClient
    with TemporaryDirectory(prefix="campus-eval-") as directory:
        settings = isolated_settings(directory)
        with TestClient(fixture_app(settings)) as client:
            yield client, settings
