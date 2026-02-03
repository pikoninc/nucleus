import json
import unittest
from pathlib import Path

import jsonschema
import yaml


class TestPluginContractExamples(unittest.TestCase):
    def test_builtin_desktop_rules_example_validates(self) -> None:
        root = Path(__file__).resolve().parents[2]
        schema_path = root / "contracts" / "plugins" / "builtin.desktop" / "schemas" / "desktop_rules.schema.json"
        example_path = root / "contracts" / "plugins" / "builtin.desktop" / "examples" / "desktop_rules.example.yml"

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        instance = yaml.safe_load(example_path.read_text(encoding="utf-8"))
        self.assertIsInstance(instance, dict)

        # Will raise jsonschema.ValidationError on mismatch (test failure).
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.Draft202012Validator(schema).validate(instance)


if __name__ == "__main__":
    unittest.main()

