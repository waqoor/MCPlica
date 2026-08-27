"""Enforce reviewable per-module coverage floors for risk-bearing boundaries."""

import argparse
import json
from pathlib import Path
from typing import TypedDict, cast


class CoverageSummary(TypedDict):
    percent_covered: float


class CoverageFile(TypedDict):
    summary: CoverageSummary


class CoverageReport(TypedDict):
    files: dict[str, CoverageFile]


def check_critical_coverage(
    report: CoverageReport,
    thresholds: dict[str, float],
) -> list[str]:
    measured = {
        _normalize_path(name): value["summary"]["percent_covered"]
        for name, value in report["files"].items()
    }
    failures: list[str] = []
    for configured_path, minimum in sorted(thresholds.items()):
        path = _normalize_path(configured_path)
        candidates = [
            percent
            for measured_path, percent in measured.items()
            if measured_path == path or measured_path.endswith(f"/{path}")
        ]
        if not candidates:
            failures.append(f"{configured_path}: missing from coverage report")
            continue
        actual = max(candidates)
        if actual + 1e-9 < minimum:
            failures.append(f"{configured_path}: {actual:.2f}% is below the {minimum:.2f}% floor")
    return failures


def _normalize_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "critical_coverage.json",
    )
    args = parser.parse_args()
    report = cast(CoverageReport, _read_json(args.report))
    raw_thresholds = cast(dict[str, object], _read_json(args.thresholds))
    thresholds: dict[str, float] = {}
    for name, value in raw_thresholds.items():
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise TypeError(f"Coverage floor for {name} must be numeric")
        thresholds[name] = float(value)
    failures = check_critical_coverage(report, thresholds)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        return 1
    for name, minimum in sorted(thresholds.items()):
        print(f"PASS {name} >= {minimum:.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
