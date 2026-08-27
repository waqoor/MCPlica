import argparse
from pathlib import Path

from app.openapi_artifact import render_openapi_artifact

DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the authoritative deterministic FastAPI OpenAPI artifact."
    )
    parser.add_argument("--check", action="store_true", help="fail if the artifact drifted")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    expected = render_openapi_artifact()
    output = args.output.resolve()
    if args.check:
        if not output.is_file() or output.read_bytes() != expected:
            parser.error(
                f"{output} is stale; run backend/generate_openapi.py and regenerate frontend types"
            )
        return 0
    output.write_bytes(expected)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
