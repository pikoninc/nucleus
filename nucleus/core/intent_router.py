from __future__ import annotations

from dataclasses import dataclass

from .errors import ValidationError


@dataclass(frozen=True)
class Route:
    plugin_id: str
    intent_id: str


class IntentRouter:
    """
    Minimal router that extracts a plugin_id prefix from intent_id.

    Notes:
    - Plugin behavior is out of framework scope.
    - This router does not load plugin implementations; it only resolves identifiers.
    """

    def route(self, intent: dict) -> Route:
        intent_id = intent.get("intent_id")
        if not isinstance(intent_id, str) or not intent_id:
            raise ValidationError(code="intent.invalid", message="Missing or invalid intent_id")

        # Convention: first segment is plugin namespace (e.g., 'desktop.tidy' -> 'desktop')
        plugin_id = intent_id.split(".", 1)[0] if "." in intent_id else intent_id
        return Route(plugin_id=plugin_id, intent_id=intent_id)

