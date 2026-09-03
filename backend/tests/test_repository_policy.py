import hashlib
import json
import subprocess
import sys
import tomllib
from pathlib import Path


def test_cla_workflow_consumes_configured_external_status_without_pr_checkout() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/cla.yml").read_text(encoding="utf-8")

    assert "CLA_STATUS_CONTEXT" in workflow
    assert "commits/${HEAD_SHA}/status" in workflow
    assert "commits/${HEAD_SHA}/check-runs" in workflow
    assert '== "success"' in workflow
    assert "service status could not be queried" in workflow
    assert "actions/checkout" not in workflow
    assert "pull-requests: read" in workflow
    assert "statuses: read" in workflow
    assert "checks: read" in workflow


def test_cla_workflow_recognizes_trusted_repository_actors() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/cla.yml").read_text(encoding="utf-8")

    assert "AUTHOR_ASSOCIATION" in workflow
    assert "AUTHOR_LOGIN" in workflow
    assert "dependabot[bot]" in workflow
    assert "OWNER|MEMBER|COLLABORATOR" in workflow
    assert "External contributor CLA verification is unavailable" in workflow


def test_dependency_review_has_an_executable_private_repository_fallback() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "github.event.repository.private == false" in workflow
    assert "ghcr.io/google/osv-scanner:v2.4.0@sha256:" in workflow
    assert "5116601dedc01c1c580eb92371883ec052fc4c13c3fbc109d621a63ac416d475" in workflow
    assert "--lockfile /src/frontend/pnpm-lock.yaml" in workflow
    assert "uv export --frozen --all-packages --all-extras --no-emit-workspace" in workflow
    assert "uvx pip-audit" in workflow


def test_python_advisory_audits_include_optional_development_dependencies() -> None:
    root = Path(__file__).resolve().parents[2]

    for path in (".github/workflows/ci.yml", ".github/workflows/security.yml"):
        workflow = (root / path).read_text(encoding="utf-8")
        assert "uv export --frozen --all-packages --all-extras --no-emit-workspace" in workflow
        assert "--no-dev" not in workflow


def test_frontend_package_manager_uses_current_security_configuration() -> None:
    root = Path(__file__).resolve().parents[2]
    package = json.loads((root / "frontend/package.json").read_text(encoding="utf-8"))
    workspace = (root / "frontend/pnpm-workspace.yaml").read_text(encoding="utf-8")
    dockerfile = (root / "infra/docker/frontend.Dockerfile").read_text(encoding="utf-8")

    assert package["packageManager"] == "pnpm@11.25.0"
    assert "pnpm" not in package
    assert workspace == "allowBuilds:\n  esbuild: true\n"
    assert "frontend/pnpm-workspace.yaml" in dockerfile


def test_playwright_retries_cannot_mask_flaky_ci_results() -> None:
    root = Path(__file__).resolve().parents[2]
    config = (root / "frontend/playwright.config.ts").read_text(encoding="utf-8")

    assert "failOnFlakyTests: Boolean(process.env.CI)" in config
    assert "retries: process.env.CI ? 2 : 0" in config


def test_source_snapshot_checksum_manifest_is_complete_and_current() -> None:
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, "scripts/checksum_manifest.py", "--check"],
        cwd=root,
        check=True,
    )


def test_source_snapshot_checksum_manifest_uses_canonical_git_blob_bytes() -> None:
    root = Path(__file__).resolve().parents[2]
    path = "README.md"
    blob = subprocess.run(
        ["git", "cat-file", "blob", f":{path}"],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    expected = f"{hashlib.sha256(blob).hexdigest()}  ./{path}"

    assert expected in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()


def test_documentation_validator_only_reads_tracked_markdown() -> None:
    root = Path(__file__).resolve().parents[2]
    tracked = (
        subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .split("\0")
    )
    result = subprocess.run(
        [sys.executable, "scripts/validate_docs.py"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert f"({len([path for path in tracked if path])} Markdown files;" in result.stdout


def test_authoritative_documentation_is_not_ignored() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "check-ignore", "docs/operations/new-authoritative-runbook.md"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1


def test_custom_runtime_roots_are_ignored() -> None:
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", ".runtime-release-candidate/secrets.json"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_runtime_build_uses_the_compose_selected_image() -> None:
    root = Path(__file__).resolve().parents[2]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    runtime_target = makefile.split("runtime-build:", 1)[1].split("\n\n", 1)[0]
    assert "$(COMPOSE) build runtime-validator" in runtime_target
    assert "docker build -t" not in runtime_target


def test_make_backend_tests_use_backend_pytest_configuration() -> None:
    root = Path(__file__).resolve().parents[2]
    makefile = (root / "Makefile").read_text(encoding="utf-8")
    test_target = makefile.split("test:", 1)[1].split("\n\n", 1)[0]

    assert "pytest -c pyproject.toml" in test_target


def test_ruff_classifies_repository_scripts_as_first_party_consistently() -> None:
    root = Path(__file__).resolve().parents[2]

    for config_path in (root / "pyproject.toml", root / "backend/pyproject.toml"):
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        known_first_party = config["tool"]["ruff"]["lint"]["isort"]["known-first-party"]
        assert "scripts" in known_first_party


def test_gitleaks_fixture_allowlist_is_rule_path_and_shape_scoped() -> None:
    root = Path(__file__).resolve().parents[2]
    config = tomllib.loads((root / ".gitleaks.toml").read_text(encoding="utf-8"))

    assert config["extend"] == {"useDefault": True}
    assert len(config["rules"]) == 1
    rule = config["rules"][0]
    assert rule["id"] == "generic-api-key"
    assert len(rule["allowlists"]) == 1
    allowlist = rule["allowlists"][0]
    assert allowlist["condition"] == "AND"
    assert allowlist["regexTarget"] == "line"
    assert allowlist["regexes"] == [
        r"""[[:space:]]*"(key|operation_key)": "op_[0-9a-f]{24}",?[[:space:]]*"""
    ]
    assert allowlist["paths"] == [r"tests/fixtures/(canonical|manifests)/[^/]+\.json$"]


def test_gitleaks_history_scan_is_digest_pinned_and_org_license_independent() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/security.yml").read_text(encoding="utf-8")

    assert "gitleaks/gitleaks-action@" not in workflow
    assert "fetch-depth: 0" in workflow
    assert "docker run --rm --network none" in workflow
    assert (
        "ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:"
        "c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f" in workflow
    )
    assert "git /repo" in workflow
    assert "--config /repo/.gitleaks.toml" in workflow
    assert "--redact" in workflow


def test_release_assets_are_attached_before_an_immutable_release_is_published() -> None:
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert 'gh release create "${GITHUB_REF_NAME}" release-assets/*' in workflow
    assert 'gh release upload "${GITHUB_REF_NAME}"' not in workflow
    assert "--verify-tag" in workflow
    assert 'if [[ "${GITHUB_REF_NAME}" == *-* ]]' in workflow
    assert "prerelease+=(--prerelease)" in workflow
