from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from nucleus.contract_store import ContractStore
from nucleus.core.errors import ValidationError
from nucleus.resources import core_contracts_schemas_dir


@dataclass(frozen=True)
class PluginManifest:
    raw: Dict[str, Any]

    @property
    def plugin_id(self) -> str:
        return str(self.raw.get("plugin_id"))

    @property
    def intents(self) -> List[Dict[str, Any]]:
        v = self.raw.get("intents")
        return v if isinstance(v, list) else []

    def declares_intent(self, intent_id: str) -> bool:
        for it in self.intents:
            if isinstance(it, dict) and it.get("intent_id") == intent_id:
                return True
        return False


def _core_contracts() -> ContractStore:
    store = ContractStore(core_contracts_schemas_dir())
    store.load()
    return store


class PluginRegistry:
    """
    Minimal registry:
    - loads and validates plugin manifests
    - resolves intent_id -> plugin_id based on declared intents
    """

    def __init__(self) -> None:
        self._manifests_by_plugin_id: Dict[str, PluginManifest] = {}
        self._plugin_id_by_intent_id: Dict[str, str] = {}

    def load_from_dir(self, plugins_dir: Path) -> None:
        if not plugins_dir.exists():
            raise FileNotFoundError(str(plugins_dir))

        store = _core_contracts()

        manifests: List[PluginManifest] = []
        for manifest_path in sorted(plugins_dir.glob("*/manifest.json")):
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            errors = store.validate("plugin_manifest.schema.json", raw)
            if errors:
                raise ValidationError(
                    code="plugin_manifest.invalid",
                    message="Plugin manifest validation failed: {}".format(manifest_path),
                    data={"errors": errors},
                )
            manifests.append(PluginManifest(raw=raw))

        for m in manifests:
            plugin_id = m.plugin_id
            if not plugin_id:
                raise ValidationError(code="plugin_manifest.invalid", message="plugin_id must be non-empty")
            if plugin_id in self._manifests_by_plugin_id:
                raise ValidationError(code="plugin_manifest.duplicate", message=f"Duplicate plugin_id: {plugin_id}")
            self._manifests_by_plugin_id[plugin_id] = m

        # Build intent index (deny duplicates).
        for m in manifests:
            for it in m.intents:
                if not isinstance(it, dict):
                    continue
                intent_id = it.get("intent_id")
                if not isinstance(intent_id, str) or not intent_id:
                    continue
                if intent_id in self._plugin_id_by_intent_id:
                    raise ValidationError(
                        code="intent.duplicate",
                        message="Duplicate intent_id across plugins: {}".format(intent_id),
                        data={"intent_id": intent_id},
                    )
                self._plugin_id_by_intent_id[intent_id] = m.plugin_id

    def list_manifests(self) -> List[Dict[str, Any]]:
        return [self._manifests_by_plugin_id[k].raw for k in sorted(self._manifests_by_plugin_id.keys())]

    def list_intents(self) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for intent_id in sorted(self._plugin_id_by_intent_id.keys()):
            out.append({"intent_id": intent_id, "plugin_id": self._plugin_id_by_intent_id[intent_id]})
        return out

    def resolve_plugin_id_for_intent(self, intent_id: str) -> Optional[str]:
        return self._plugin_id_by_intent_id.get(intent_id)

    def get_manifest(self, plugin_id: str) -> Optional[Dict[str, Any]]:
        m = self._manifests_by_plugin_id.get(plugin_id)
        return m.raw if m else None

    def require_plugin_id_for_intent(self, intent_id: str) -> str:
        pid = self.resolve_plugin_id_for_intent(intent_id)
        if not pid:
            raise ValidationError(code="intent.unknown", message=f"Unknown intent_id: {intent_id}")
        return pid

