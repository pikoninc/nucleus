import unittest

from nucleus.core.errors import ValidationError
from nucleus.intake.triage import triage_text_to_intent


class StubProvider:
    def __init__(self, payload):
        self.payload = payload

    def triage(self, *, input_text: str, system_prompt: str, intent_schema: dict) -> dict:
        return self.payload


class TestIntakeTriage(unittest.TestCase):
    def test_network_denied_by_default(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            triage_text_to_intent(
                input_text="整理して",
                intents_catalog=[{"intent_id": "desktop.tidy.preview", "plugin_id": "builtin.desktop"}],
                scope={"fs_roots": ["~/Desktop"], "allow_network": False},
                provider=StubProvider({"intent_id": "desktop.tidy.preview", "params": {}, "scope": {"fs_roots": ["x"]}}),
                provider_id="stub",
                model="stub",
            )
        self.assertEqual(ctx.exception.code, "intake.network_denied")

    def test_unknown_intent_id_is_rejected(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            triage_text_to_intent(
                input_text="整理して",
                intents_catalog=[{"intent_id": "desktop.tidy.preview", "plugin_id": "builtin.desktop"}],
                scope={"fs_roots": ["~/Desktop"], "allow_network": False},
                provider=StubProvider({"intent_id": "desktop.tidy.run", "params": {}, "scope": {"fs_roots": ["x"]}}),
                provider_id="stub",
                model="stub",
                allow_network=True,
            )
        self.assertEqual(ctx.exception.code, "intake.invalid_intent_id")

    def test_scope_is_preserved_and_intent_validates(self) -> None:
        scope = {"fs_roots": ["~/Desktop"], "allow_network": False}
        res = triage_text_to_intent(
            input_text="デスクトップをプレビューで整理して",
            intents_catalog=[{"intent_id": "desktop.tidy.preview", "plugin_id": "builtin.desktop"}],
            scope=scope,
            context={"ui": "test"},
            provider=StubProvider({"intent_id": "desktop.tidy.preview", "params": {"foo": "bar"}, "scope": {"fs_roots": ["hacked"]}}),
            provider_id="stub",
            model="stub",
            allow_network=True,
        )
        self.assertEqual(res.intent["scope"], scope)
        self.assertEqual(res.intent["intent_id"], "desktop.tidy.preview")
        self.assertEqual(res.intent["context"], {"ui": "test"})


if __name__ == "__main__":
    unittest.main()

