"""Collect bounded, redacted Compose diagnostics; optionally assert service readiness."""

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMAND = ["docker", "compose", "--env-file", ".env", "-f", "infra/compose.yaml"]
ONESHOT = {"migrate", "runtime-init"}


def _command(*args: str) -> str:
    result = subprocess.run(
        [*COMMAND, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Compose diagnostics failed for {args[0]}")
    return result.stdout


def _records(value: str) -> list[dict[str, object]]:
    if value.lstrip().startswith("["):
        records = json.loads(value)
    else:
        records = [json.loads(line) for line in value.splitlines() if line.strip()]
    if not isinstance(records, list) or any(not isinstance(item, dict) for item in records):
        raise ValueError("Compose ps returned invalid status records")
    return records


def _redact(value: str) -> str:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            name, sep, secret = line.partition("=")
            if sep and any(
                item in name
                for item in ("SECRET", "PASSWORD", "TOKEN", "KEY", "PEPPER", "DATABASE_URL")
            ):
                secret = secret.strip().strip("'\"")
                if secret:
                    value = value.replace(secret, "[REDACTED]")
    return re.sub(r"(?i)(bearer\s+)[a-z0-9._~+/-]+=*", r"\1[REDACTED]", value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "output/compose-validation")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    records = _records(_command("ps", "--all", "--format", "json"))
    statuses = [
        {key: row.get(key) for key in ("Service", "State", "Health", "ExitCode")}
        for row in records
    ]
    (args.output / "services.json").write_text(json.dumps(statuses, indent=2) + "\n")
    if args.check:
        expected = set(_command("config", "--services").splitlines())
        actual = {str(row["Service"]) for row in statuses}
        if expected != actual:
            raise RuntimeError(f"Missing or unexpected Compose services: {expected ^ actual}")
        for row in statuses:
            if row["Service"] in ONESHOT:
                if row["State"] != "exited" or row["ExitCode"] != 0:
                    raise RuntimeError(f"Initialization did not complete: {row}")
            elif row["State"] != "running" or row["Health"] != "healthy":
                raise RuntimeError(f"Service is not healthy: {row}")
        print(f"All {len(expected)} Compose services reached their required states.")
    else:
        logs = _redact(_command("logs", "--no-color", "--tail", "100"))
        (args.output / "compose.log").write_text(logs, encoding="utf-8")


if __name__ == "__main__":
    main()
