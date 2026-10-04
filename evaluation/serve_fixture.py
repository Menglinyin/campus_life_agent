"""HTTP fixture server on loopback, with optional real vLLM calls."""
import argparse
from tempfile import TemporaryDirectory
from evaluation.fixtures import isolated_settings, fixture_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--with-model", action="store_true")
    parser.add_argument("--with-voice", action="store_true")
    parser.add_argument("--embedding", choices=["demo", "bge"], default="demo")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Invalid port")
    import uvicorn
    with TemporaryDirectory(prefix="campus-http-eval-") as directory:
        settings = isolated_settings(directory, args.with_model, args.embedding, with_voice=args.with_voice)
        print("Isolated synthetic fixture server; data removed after shutdown.")
        uvicorn.run(fixture_app(settings), host="127.0.0.1", port=args.port, workers=1)


if __name__ == "__main__":
    main()
