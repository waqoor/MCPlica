"""Verify private paths are excluded by Docker itself using a temporary synthetic context."""

import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    private = [
        ".env",
        ".env.production",
        ".runtime/deployment/secrets.json",
        "backend/.env",
        "frontend/.env.local",
        "secrets/material.json",
        "runtime-secrets/token.json",
        "backend/private.key",
        "mcp_runtime/client.pem",
        "nested/.runtime/manifest.json",
    ]
    public = [".env.example", "backend/.env.example", "backend/app/main.py", "README.md"]
    with TemporaryDirectory(prefix="mcplica-context-check-") as directory:
        root = Path(directory)
        context = root / "context"
        context.mkdir()
        shutil.copyfile(ROOT / ".dockerignore", context / ".dockerignore")
        for name in [*private, *public]:
            path = context / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("synthetic fixture, not a secret\n")
        (context / "Dockerfile").write_text("FROM scratch\nCOPY . /context/\n")
        result = subprocess.run(
            [
                "docker", "build", "--quiet", "--output",
                f"type=local,dest={root / 'result'}", str(context),
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if result.returncode:
            raise RuntimeError("Docker build-context validation failed: " + result.stderr[-2000:])
        copied = root / "result" / "context"
        for name in private:
            assert not (copied / name).exists(), f"Private build input was included: {name}"
        for name in public:
            assert (copied / name).is_file(), f"Required example/source was excluded: {name}"
    print("Docker build-context privacy and retained source/example checks passed.")


if __name__ == "__main__":
    main()
