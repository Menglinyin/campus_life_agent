"""Tests catch false-positive scoring and unavailable/malformed service results."""
from io import BytesIO
import json
from pathlib import Path
import wave

import httpx
import pytest

from evaluation.common import ROOT, edit_distance, percentile, ranking_metrics, read_jsonl
from evaluation.fixtures import isolated_settings
from evaluation.agent.evaluate import assertions, run as run_agent
from evaluation.rag.evaluate import run as run_rag
from evaluation.voice.evaluate import normalize, score, wav_metadata, run as run_voice
from evaluation.load.collector import Collector, validate_report
from evaluation.load.scenarios import load_scenarios


def jsonl(path, rows):
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows), encoding="utf-8")
    return path


def wave_bytes():
    data = BytesIO()
    with wave.open(data, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(b"\0\0" * 1600)
    return data.getvalue()


def test_ranking_known_denominators():
    result = ranking_metrics(["wrong", "a", "b"], ["a", "missing"], 3)
    assert result["recall_at_k"] == .5
    assert result["precision_at_k"] == pytest.approx(1 / 3)
    assert result["mrr_at_k"] == .5
    assert result["hit_at_k"] == 1


def test_ranking_invalid_and_empty_truth():
    with pytest.raises(ValueError):
        ranking_metrics(["a", "a"], ["a"], 2)
    with pytest.raises(ValueError):
        ranking_metrics([], [], 4)


def test_latency_interpolation_and_no_samples():
    assert percentile([10, 30], .95) == 29
    assert percentile([], .5) is None
    with pytest.raises(ValueError):
        percentile([float("nan")], .5)


def test_duplicate_dataset_rejected(tmp_path):
    path = jsonl(tmp_path / "dataset.jsonl", [{"id": "a"}, {"id": "a"}])
    with pytest.raises(ValueError):
        read_jsonl(path)


def test_environment_cannot_select_real_database(tmp_path, monkeypatch):
    monkeypatch.setenv("CAMPUS_DATABASE_URL", "mysql+pymysql://real:private@host/prod")
    monkeypatch.setenv("CAMPUS_REDIS_URL", "redis://real-host/0")
    monkeypatch.setenv("CAMPUS_DEMO", "false")
    settings = isolated_settings(tmp_path)
    assert settings.database_url == f"sqlite:///{tmp_path / 'evaluation.db'}"
    assert settings.demo and not settings.redis_url and not settings.llm_base_url


def test_empty_rows_do_not_pass_budget_check():
    response = httpx.Response(200, json={"results": [{"tool": "recommend_dishes", "rows": []}]})
    checks = assertions(response, {"rows": {"recommend_dishes": {"count": 1, "max_price": 10}}})
    assert not all(checks.values())


def test_wrong_tool_or_price_is_failure():
    response = httpx.Response(200, json={"session_id": "bad", "message_id": "bad",
        "results": [{"tool": "recommend_dishes", "rows": [{"id": "a", "price": 20}]}]})
    checks = assertions(response, {"tools": ["query_classrooms"], "rows": {"recommend_dishes": {"count": 1, "max_price": 10}}})
    assert not checks["tools"] and not checks["rows:recommend_dishes:budget"]


def test_expected_ownership_failure_is_success():
    assert all(assertions(httpx.Response(404), {"status": 404}).values())
    assert not all(assertions(httpx.Response(200, json={}), {"status": 404}).values())


def test_all_agent_fixture_scenarios():
    report = run_agent(ROOT / "agent/dataset.jsonl")
    assert report["status"] == "passed"
    assert report["metrics"]["scenarios_total"] == 12
    assert report["observed_response_modes"] == ["demo"]


def test_rag_private_filter_and_no_answer_denominator():
    report = run_rag(ROOT / "rag/dataset.jsonl")
    assert report["metrics"]["unauthorized_returns"] == 0
    assert report["metrics"]["cases_total"] == 8
    assert report["metrics"]["scored_queries"] == 6
    cross_user = next(x for x in report["cases"] if x["id"] == "rag-cross-user")
    assert "eval-private-b" not in cross_user["retrieved_ids"]
    assert cross_user["metrics"] is None


def test_rag_errors_are_not_counted_as_success(monkeypatch):
    from evaluation.rag.evaluate import HybridRetriever
    def broken(*args, **kwargs):
        raise RuntimeError("service unavailable")
    monkeypatch.setattr(HybridRetriever, "search", broken)
    report = run_rag(ROOT / "rag/dataset.jsonl")
    assert report["status"] == "failed"
    assert report["metrics"]["errors"] == 8
    assert report["metrics"]["recall_at_k"] == 0
    assert report["metrics"]["latency_p50_ms"] is None


def test_text_normalization_and_edits():
    assert normalize("ＡＢＣ，  today！") == "abc today"
    assert edit_distance("abc", "axc") == 1
    assert edit_distance("", "ab") == 2
    assert score("推荐不辣的菜品", "推荐微辣的菜品")["character_edits"] == 1


def test_wav_validity_and_truncation():
    data = wave_bytes()
    assert wav_metadata(data)["duration_seconds"] == .1
    with pytest.raises(ValueError):
        wav_metadata(data[:-2])


def test_offline_missing_prediction_is_incomplete(tmp_path):
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": "abc"}, {"id": "b", "reference": "def"}])
    predictions = jsonl(tmp_path / "predictions.jsonl", [{"id": "a", "text": "abc"}])
    report = run_voice(dataset, predictions=predictions)
    assert report["status"] == "incomplete" and report["metrics"]["skipped"] == 1
    assert report["metrics"]["latency_p95_ms"] is None


def test_empty_reference_insertion_retained(tmp_path):
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": ""}])
    pred = jsonl(tmp_path / "pred.jsonl", [{"id": "a", "text": "abc"}])
    report = run_voice(dataset, predictions=pred)
    assert report["metrics"]["character_edits"] == 3
    assert report["metrics"]["cer"] is None


def mock_client(monkeypatch, handler):
    monkeypatch.setenv("EVAL_TOKEN_A", "private-test-token")
    constructor = httpx.Client
    monkeypatch.setattr("evaluation.voice.evaluate.httpx.Client",
                        lambda **kw: constructor(**kw, transport=httpx.MockTransport(handler)))


def test_asr_http_metrics_from_real_request_protocol(tmp_path, monkeypatch):
    (tmp_path / "sample.wav").write_bytes(wave_bytes())
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": "今天", "audio_path": "sample.wav"}])
    def handler(request):
        assert request.url.path == "/api/voice/transcribe"
        assert b'sample.wav' in request.content
        return httpx.Response(200, json={"text": "今天"})
    mock_client(monkeypatch, handler)
    report = run_voice(dataset, mode="http")
    assert report["metrics"]["cer"] == 0
    assert report["metrics"]["end_to_end_rtf_mean"] is not None
    assert "private-test-token" not in json.dumps(report)


def test_asr_http_unavailable_is_failure(tmp_path, monkeypatch):
    (tmp_path / "sample.wav").write_bytes(wave_bytes())
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": "今天", "audio_path": "sample.wav"}])
    mock_client(monkeypatch, lambda request: httpx.Response(503))
    report = run_voice(dataset, mode="http")
    assert report["status"] == "failed" and report["metrics"]["cer"] is None


def test_asr_missing_audio_is_not_success(tmp_path, monkeypatch):
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": "abc", "audio_path": None}])
    mock_client(monkeypatch, lambda request: pytest.fail("No audio should be uploaded"))
    report = run_voice(dataset, mode="http")
    assert report["status"] == "incomplete" and report["metrics"]["cases_scored"] == 0


def test_audio_path_escape_rejected(tmp_path, monkeypatch):
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": "abc", "audio_path": "../secret.wav"}])
    mock_client(monkeypatch, lambda request: pytest.fail("Escaping path must not be uploaded"))
    assert run_voice(dataset, mode="http")["status"] == "failed"


def test_tts_returns_valid_wav_without_cer_claim(tmp_path, monkeypatch):
    dataset = jsonl(tmp_path / "dataset.jsonl", [{"id": "a", "reference": ""}])
    def handler(request):
        if request.url.path == "/api/chat":
            return httpx.Response(200, json={"message_id": "example-id"})
        assert json.loads(request.content)["message_id"] == "example-id"
        return httpx.Response(200, content=wave_bytes())
    mock_client(monkeypatch, handler)
    report = run_voice(dataset, mode="http", task="tts")
    assert report["status"] == "completed" and report["metrics"]["cer"] is None
    assert report["cases"][0]["audio"]["sample_rate"] == 16000


def test_load_warmup_and_semantic_failure():
    collector = Collector(100, 10)
    collector.record(109, 1000, 200, False, "demo")
    collector.record(110, 10, 200, False, "demo")
    collector.record(111, 30, 200, True, "demo")
    report = collector.report(120, {})
    validate_report(report)
    assert report["metrics"]["requests_total"] == 2
    assert report["metrics"]["success_rate"] == .5
    assert report["metrics"]["completed_chat_rps"] == .1
    assert report["http_status_counts"] == {"200": 2}
    assert report["metrics"]["gpu_0_peak_gib"] is None


def test_load_empty_and_capped_latency():
    collector = Collector(100, 10, max_samples=1)
    report = collector.report(105, {})
    validate_report(report)
    assert report["status"] == "no_samples" and report["metrics"]["success_rate"] is None
    collector.record(111, 10, 200, False)
    collector.record(112, 20, 200, False)
    report = collector.report(120, {})
    assert report["latency_samples_dropped"] == 1
    assert report["metrics"]["e2e_p95_ms"] is None


def test_scenarios_reject_bad_weight(tmp_path):
    assert len(load_scenarios(ROOT / "load/scenarios.yaml")) == 5
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: 1\nscenarios:\n  - id: a\n    weight: -1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_scenarios(bad)


def test_load_cli_rejects_zero_exit_without_fresh_report(tmp_path, monkeypatch):
    from evaluation.load.run_load import main
    monkeypatch.setenv("EVAL_TOKEN_A", "fixture-token")
    monkeypatch.delenv("EVAL_LOAD_TOKENS", raising=False)
    monkeypatch.setattr("sys.argv", ["run_load", "--output", str(tmp_path / "missing.json")])
    monkeypatch.setattr("evaluation.load.run_load.subprocess.call", lambda *args, **kwargs: 0)
    assert main() == 2
