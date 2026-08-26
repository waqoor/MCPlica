import json
from pathlib import Path

from mcp_contracts import ApiInventory, MCPManifest


def _write(path: Path, schema: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    contract_root = Path(__file__).resolve().parents[1]
    repository_root = contract_root.parents[1]
    _write(
        contract_root / "schemas" / "mcp-manifest-v1.schema.json",
        MCPManifest.model_json_schema(by_alias=True),
    )
    _write(
        repository_root
        / "backend"
        / "app"
        / "parsers"
        / "api_inventory"
        / "schema"
        / "api-inventory-v1.schema.json",
        ApiInventory.model_json_schema(by_alias=True),
    )


if __name__ == "__main__":
    main()
