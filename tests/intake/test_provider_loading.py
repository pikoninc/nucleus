import os
import unittest

from nucleus.core.errors import ValidationError
from nucleus.intake.provider_loading import load_triage_provider


class TestProviderLoading(unittest.TestCase):
    def test_load_anthropic_provider_and_missing_key_error(self) -> None:
        old = os.environ.get("ANTHROPIC_API_KEY")
        os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            loaded = load_triage_provider(provider="anthropic.messages", model="claude-3-5-sonnet-latest")
            self.assertEqual(loaded.provider_id, "anthropic.messages")
            self.assertEqual(loaded.model, "claude-3-5-sonnet-latest")
            with self.assertRaises(ValidationError) as ctx:
                loaded.provider.triage(input_text="hi", system_prompt="sys", intent_schema={})
            self.assertEqual(ctx.exception.code, "intake.missing_api_key")
            self.assertIn("ANTHROPIC_API_KEY", str(ctx.exception))
        finally:
            if old is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old

    def test_load_gemini_provider_and_missing_key_error(self) -> None:
        old = os.environ.get("GEMINI_API_KEY")
        os.environ.pop("GEMINI_API_KEY", None)
        try:
            loaded = load_triage_provider(provider="google.gemini", model="gemini-2.0-flash")
            self.assertEqual(loaded.provider_id, "google.gemini")
            self.assertEqual(loaded.model, "gemini-2.0-flash")
            with self.assertRaises(ValidationError) as ctx:
                loaded.provider.triage(input_text="hi", system_prompt="sys", intent_schema={})
            self.assertEqual(ctx.exception.code, "intake.missing_api_key")
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        finally:
            if old is None:
                os.environ.pop("GEMINI_API_KEY", None)
            else:
                os.environ["GEMINI_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()

