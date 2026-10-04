"""Offline transcript metrics or real ASR/TTS HTTP evaluation; no generated speech claims."""
import argparse
from io import BytesIO
from pathlib import Path
from time import perf_counter
import unicodedata
import wave
import httpx
from evaluation.common import ROOT, read_jsonl, edit_distance, report_base, write_report, token_from_env, percentile


def normalize(text):
    if not isinstance(text, str) or len(text) > 10000:
        raise ValueError("Invalid transcript")
    text = unicodedata.normalize("NFKC", text).lower()
    return " ".join("".join(c for c in text if not unicodedata.category(c).startswith("P")).split())


def score(reference, hypothesis):
    ref, hyp = normalize(reference), normalize(hypothesis)
    chars_ref, chars_hyp = list(ref.replace(" ", "")), list(hyp.replace(" ", ""))
    words_ref, words_hyp = ref.split(), hyp.split()
    return {"character_edits": edit_distance(chars_ref, chars_hyp), "reference_characters": len(chars_ref),
            "word_edits": edit_distance(words_ref, words_hyp), "reference_words": len(words_ref)}


def wav_metadata(data):
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("WAV too large")
    with wave.open(BytesIO(data), "rb") as audio:
        rate, frames = audio.getframerate(), audio.getnframes()
        if rate <= 0 or frames <= 0:
            raise ValueError("Empty WAV")
        required = frames * audio.getnchannels() * audio.getsampwidth()
        if len(audio.readframes(frames)) != required:
            raise ValueError("Truncated WAV")
        return {"sample_rate": rate, "channels": audio.getnchannels(),
                "sample_width_bytes": audio.getsampwidth(), "duration_seconds": frames / rate}


def run(dataset, mode="offline", predictions=None, base_url="http://127.0.0.1:8010", task="asr", timeout=90):
    cases = read_jsonl(dataset, ("reference",))
    hypotheses = {}
    if mode == "offline":
        if task != "asr" or predictions is None:
            raise ValueError("Offline mode requires ASR predictions")
        hypotheses = {x["id"]: x["text"] for x in read_jsonl(predictions, ("text",))}
        if set(hypotheses) - {x["id"] for x in cases}:
            raise ValueError("Unknown prediction id")
    results, totals, latency, rtf = [], dict(character_edits=0, reference_characters=0, word_edits=0, reference_words=0), [], []
    headers = {"Authorization": "Bearer " + token_from_env("EVAL_TOKEN_A")} if mode == "http" else {}
    client = httpx.Client(base_url=base_url, timeout=timeout, trust_env=False) if mode == "http" else None
    try:
        for case in cases:
            identifier = case["id"]
            try:
                if mode == "offline":
                    if identifier not in hypotheses:
                        results.append({"id": identifier, "status": "skipped", "reason": "missing_prediction"})
                        continue
                    metrics = score(case["reference"], hypotheses[identifier])
                    results.append({"id": identifier, "status": "ok", **metrics})
                elif task == "asr":
                    if not case.get("audio_path"):
                        results.append({"id": identifier, "status": "skipped", "reason": "audio_not_supplied"})
                        continue
                    base = Path(dataset).resolve().parent
                    path = (base / case["audio_path"]).resolve()
                    if not path.is_relative_to(base) or not path.is_file():
                        raise ValueError("Audio must be a file beneath dataset directory")
                    if path.stat().st_size > 8 * 1024 * 1024:
                        raise ValueError("Audio exceeds upload limit")
                    data = path.read_bytes()
                    meta = wav_metadata(data)
                    start = perf_counter()
                    response = client.post("/api/voice/transcribe", files={"audio": ("sample.wav", data, "audio/wav")}, headers=headers)
                    elapsed = (perf_counter() - start) * 1000
                    if response.status_code != 200:
                        results.append({"id": identifier, "status": "error", "status_code": response.status_code})
                        continue
                    metrics = score(case["reference"], response.json()["text"])
                    latency.append(elapsed)
                    ratio = elapsed / 1000 / meta["duration_seconds"]
                    rtf.append(ratio)
                    results.append({"id": identifier, "status": "ok", **metrics, "audio": meta,
                                    "latency_ms": elapsed, "end_to_end_rtf": ratio})
                else:
                    chat = client.post("/api/chat", json={"message": case.get("chat_message", "2026-10-04 查询教室")}, headers=headers)
                    if chat.status_code != 200:
                        results.append({"id": identifier, "status": "error", "stage": "chat", "status_code": chat.status_code})
                        continue
                    start = perf_counter()
                    response = client.post("/api/voice/synthesize", json={"message_id": chat.json()["message_id"]}, headers=headers)
                    elapsed = (perf_counter() - start) * 1000
                    if response.status_code != 200:
                        results.append({"id": identifier, "status": "error", "stage": "tts", "status_code": response.status_code})
                        continue
                    meta = wav_metadata(response.content)
                    latency.append(elapsed)
                    ratio = elapsed / 1000 / meta["duration_seconds"]
                    rtf.append(ratio)
                    results.append({"id": identifier, "status": "ok", "audio": meta,
                                    "latency_ms": elapsed, "end_to_end_rtf": ratio})
                    continue
                for key in totals:
                    totals[key] += metrics[key]
            except Exception as exc:
                results.append({"id": identifier, "status": "error", "error_type": type(exc).__name__})
    finally:
        if client:
            client.close()
    count_ok = sum(x["status"] == "ok" for x in results)
    errors = sum(x["status"] == "error" for x in results)
    skipped = sum(x["status"] == "skipped" for x in results)
    report = report_base("voice", mode, dataset)
    report.update(task=task, status="failed" if errors else ("completed" if count_ok and not skipped else "incomplete"), cases=results,
                  metrics={"cases_total": len(cases), "cases_scored": count_ok, "errors": errors, "skipped": skipped,
                           **totals, "cer": totals["character_edits"] / totals["reference_characters"] if totals["reference_characters"] else None,
                           "wer_whitespace": totals["word_edits"] / totals["reference_words"] if totals["reference_words"] else None,
                           "latency_p95_ms": percentile(latency, .95), "end_to_end_rtf_mean": sum(rtf) / len(rtf) if rtf else None},
                  limitations=["Offline predictions are supplied text, not speech recognition measurements.",
                               "Normalize NFKC/lowercase/remove punctuation; CER removes spaces; WER uses whitespace words.",
                               "Whitespace WER is not Chinese segmented WER; CER is the primary Chinese metric.",
                               "Empty reference denominator yields null; insertions are retained in aggregate numerators.",
                               "TTS WAV validity/latency does not measure MOS, intelligibility or first audio latency.",
                               "End-to-end RTF includes HTTP and backend overhead, not model compute alone."])
    if predictions:
        from hashlib import sha256
        report["predictions_sha256"] = sha256(Path(predictions).read_bytes()).hexdigest()
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dataset", default=ROOT / "voice/dataset.jsonl")
    p.add_argument("--mode", choices=["offline", "http"], default="offline")
    p.add_argument("--predictions")
    p.add_argument("--base-url", default="http://127.0.0.1:8010")
    p.add_argument("--task", choices=["asr", "tts"], default="asr")
    p.add_argument("--timeout", type=float, default=90)
    p.add_argument("--output", default=ROOT / "reports/voice.json")
    a = p.parse_args()
    if a.timeout <= 0:
        p.error("timeout must be positive")
    predictions = a.predictions or (ROOT / "voice/synthetic_predictions.jsonl" if a.mode == "offline" else None)
    try:
        report = run(a.dataset, a.mode, predictions, a.base_url, a.task, a.timeout)
        write_report(a.output, report)
    except (ValueError, OSError) as exc:
        p.exit(2, f"Evaluation could not start: {type(exc).__name__}\n")
    print(f"Voice: {report['status']}; scored={report['metrics']['cases_scored']}; errors={report['metrics']['errors']}")
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
