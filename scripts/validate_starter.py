from pathlib import Path
import json
import sys

root = Path(__file__).parents[1]
required = [
    "backend/app/main.py",
    "mcp_runtime/app/main.py",
    "packages/contracts/src/mcp_contracts/manifest.py",
    "frontend/package.json",
    "infra/compose.yaml",
    "docs/architecture.md",
    "docs/design_document.md",
    "docs/product_requirements.md",
    "docs/implementation_plan.md",
    "docs/tech_stack.md",
    "docs/open_source_and_sponsorship_model.md",
]
missing = [item for item in required if not (root / item).exists()]
if missing:
    print("Missing required starter files:", *missing, sep="\n- ")
    sys.exit(1)
json.loads((root / "frontend/package.json").read_text())
print(f"MCPlica starter validation passed ({len(required)} required files checked).")
