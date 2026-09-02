import json
import re
import sys
from pathlib import Path

root = Path(__file__).parents[1]
required = [
    ".gitattributes",
    "VERSION",
    "CHANGELOG.md",
    "SUPPORT.md",
    "backend/app/main.py",
    "mcp_runtime/app/main.py",
    "packages/contracts/src/mcp_contracts/manifest.py",
    "frontend/package.json",
    "frontend/pnpm-lock.yaml",
    "frontend/playwright.config.ts",
    "uv.lock",
    "infra/compose.yaml",
    "infra/compose.production.yaml",
    ".github/workflows/ci.yml",
    ".github/workflows/security.yml",
    ".github/workflows/release.yml",
    ".github/workflows/labels.yml",
    ".github/CODEOWNERS",
    ".github/labels.json",
    "docs/architecture.md",
    "docs/design_document.md",
    "docs/product_requirements.md",
    "docs/implementation_plan.md",
    "docs/tech_stack.md",
    "docs/open_source_and_sponsorship_model.md",
    "docs/user-guide.md",
    "docs/api-inventory-v1.md",
    "docs/api.md",
    "docs/compatibility.md",
    "docs/mcp-client-connection.md",
    "docs/operations/installation.md",
    "docs/operations/configuration.md",
    "docs/operations/docker-compose.md",
    "docs/operations/backup-restore.md",
    "docs/operations/troubleshooting.md",
    "docs/operations/upgrade.md",
    "docs/security/threat-model.md",
    "docs/release/release-process.md",
    "docs/release/release-checklist.md",
    "docs/releases/v1.0.0.md",
    "scripts/release_version.py",
    "scripts/github_labels.py",
    "scripts/validate_docs.py",
    "CODE_OF_CONDUCT.md",
    "MAINTAINERS.md",
    "SECURITY.md",
    "TRADEMARKS.md",
    "SPONSORSHIP.md",
    "GENERATED_OUTPUTS.md",
]
missing = [item for item in required if not (root / item).exists()]
if missing:
    print("Missing required repository files:", *missing, sep="\n- ")
    sys.exit(1)
json.loads((root / "frontend/package.json").read_text())

raw_component_calls = [
    path.relative_to(root).as_posix()
    for path in (root / "frontend" / "src").rglob("*.tsx")
    if re.search(r"\bfetch\s*\(", path.read_text(encoding="utf-8"))
]
if raw_component_calls:
    print("Raw fetch calls must remain in typed API clients:", *raw_component_calls, sep="\n- ")
    sys.exit(1)

print(f"MCPlica repository validation passed ({len(required)} required files checked).")
