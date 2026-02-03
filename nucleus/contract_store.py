from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import jsonschema


@dataclass(frozen=True)
class SchemaRef:
    name: str
    path: Path
    file_uri: str
    schema: Dict[str, Any]


class ContractStore:
    """
    Loads `contracts/core/schemas/*.json` and provides validation helpers.

    Notes:
    - Uses file:// URIs to resolve relative $ref such as "intent.schema.json".
    - Stores schemas under both file URI and $id when present.
    """

    def __init__(self, schemas_dir: Path):
        self._schemas_dir = schemas_dir
        self._schemas: Dict[str, SchemaRef] = {}
        self._store: Dict[str, Dict[str, Any]] = {}

    @property
    def schemas_dir(self) -> Path:
        return self._schemas_dir

    def load(self) -> None:
        if not self._schemas_dir.exists():
            raise FileNotFoundError(str(self._schemas_dir))

        for p in sorted(self._schemas_dir.glob("*.json")):
            schema = json.loads(p.read_text(encoding="utf-8"))
            file_uri = p.resolve().as_uri()
            ref = SchemaRef(name=p.name, path=p, file_uri=file_uri, schema=schema)
            self._schemas[p.name] = ref

            # Map resolver keys
            self._store[file_uri] = schema
            schema_id = schema.get("$id")
            if isinstance(schema_id, str) and schema_id:
                self._store[schema_id] = schema

        # Sanity: ensure defs exists when referenced
        if "defs.schema.json" not in self._schemas:
            raise FileNotFoundError("defs.schema.json is required in contracts/core/schemas/")

    def list_schema_names(self) -> List[str]:
        return sorted(self._schemas.keys())

    def _get(self, schema_name: str) -> SchemaRef:
        ref = self._schemas.get(schema_name)
        if ref is None:
            raise KeyError(schema_name)
        return ref

    def check_schemas(self) -> List[Tuple[str, str]]:
        """
        Returns a list of (schema_name, error_message) for invalid schemas.
        """
        errors: List[Tuple[str, str]] = []
        for name in self.list_schema_names():
            ref = self._get(name)
            try:
                jsonschema.Draft202012Validator.check_schema(ref.schema)
            except Exception as e:  # noqa: BLE001
                errors.append((name, repr(e)))
        return errors

    def validate(self, schema_name: str, instance: Any) -> List[str]:
        """
        Validates an instance and returns a list of error strings (empty means valid).
        """
        ref = self._get(schema_name)
        resolver = jsonschema.RefResolver(base_uri=ref.file_uri, referrer=ref.schema, store=self._store)
        validator = jsonschema.Draft202012Validator(ref.schema, resolver=resolver)
        return [e.message for e in sorted(validator.iter_errors(instance), key=str)]

    def validate_json_file(self, schema_name: str, path: Path) -> List[str]:
        instance = json.loads(path.read_text(encoding="utf-8"))
        return self.validate(schema_name, instance)

    def validate_jsonl_file(self, schema_name: str, path: Path) -> List[str]:
        errors: List[str] = []
        with path.open("r", encoding="utf-8") as f:
            for i, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception as e:  # noqa: BLE001
                    errors.append("line {}: invalid json: {}".format(i, repr(e)))
                    continue
                line_errors = self.validate(schema_name, obj)
                for msg in line_errors:
                    errors.append("line {}: {}".format(i, msg))
        return errors

