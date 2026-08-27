from scripts.check_critical_coverage import CoverageReport, check_critical_coverage


def test_critical_coverage_gate_is_path_stable_and_fails_closed() -> None:
    report: CoverageReport = {
        "files": {
            r"backend\app\services\builds\service.py": {"summary": {"percent_covered": 72.5}},
            "app/compilers/mcp/compiler.py": {"summary": {"percent_covered": 84.9}},
        }
    }

    assert check_critical_coverage(
        report,
        {
            "app/services/builds/service.py": 70,
            "app/compilers/mcp/compiler.py": 85,
            "app/services/deployment/service.py": 50,
        },
    ) == [
        "app/compilers/mcp/compiler.py: 84.90% is below the 85.00% floor",
        "app/services/deployment/service.py: missing from coverage report",
    ]
