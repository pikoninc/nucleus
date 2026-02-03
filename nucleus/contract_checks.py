from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import jsonschema
import yaml


@dataclass(frozen=True)
class PluginExampleFailure:
    plugin_id: str
    schema_path: str
    example_path: str
    error: str


def _read_instance(path: Path) -> Any:
    if path.suffix.lower() in (".yml", ".yaml"):
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported example extension: {path.name}")


def _candidate_example_paths(examples_dir: Path, base: str) -> List[Path]:
    return [
        examples_dir / f"{base}.example.yml",
        examples_dir / f"{base}.example.yaml",
        examples_dir / f"{base}.example.json",
    ]


def discover_plugin_contract_pairs(contracts_plugins_dir: Path) -> List[Tuple[str, Path, Path]]:
    """
    Discover (plugin_id, schema_path, example_path) pairs under:
      contracts/plugins/<plugin_id>/{schemas,examples}/

    Conventions:
    - schema filename ends with ".schema.json"
    - example filename is "<base>.example.(yml|yaml|json)" where base matches schema base
      e.g. desktop_rules.schema.json -> desktop_rules.example.yml
    """
    pairs: List[Tuple[str, Path, Path]] = []
    if not contracts_plugins_dir.exists():
        return pairs

    for plugin_dir in sorted([p for p in contracts_plugins_dir.iterdir() if p.is_dir()], key=lambda p: p.name):
        plugin_id = plugin_dir.name
        schemas_dir = plugin_dir / "schemas"
        examples_dir = plugin_dir / "examples"
        if not schemas_dir.exists() or not examples_dir.exists():
            continue

        for schema_path in sorted(schemas_dir.glob("*.json"), key=lambda p: p.name):
            name = schema_path.name
            if not name.endswith(".schema.json"):
                continue
            base = name[: -len(".schema.json")]
            example_path: Optional[Path] = None
            for cand in _candidate_example_paths(examples_dir, base):
                if cand.exists():
                    example_path = cand
                    break
            if example_path is None:
                continue
            pairs.append((plugin_id, schema_path, example_path))

    return pairs


def validate_plugin_contract_examples(contracts_plugins_dir: Path) -> List[PluginExampleFailure]:
    """
    Validate discovered plugin contract examples. Returns failures (empty == OK).
    """
    failures: List[PluginExampleFailure] = []
    for plugin_id, schema_path, example_path in discover_plugin_contract_pairs(contracts_plugins_dir):
        try:
            schema: Dict[str, Any] = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            instance = _read_instance(example_path)
            jsonschema.Draft202012Validator(schema).validate(instance)
        except Exception as e:  # noqa: BLE001
            failures.append(
                PluginExampleFailure(
                    plugin_id=plugin_id,
                    schema_path=str(schema_path),
                    example_path=str(example_path),
                    error=repr(e),
                )
            )
    return failures

