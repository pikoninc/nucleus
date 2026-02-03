import unittest
from pathlib import Path

from nucleus.contract_checks import validate_plugin_contract_examples


class TestPluginContractExamples(unittest.TestCase):
    def test_builtin_desktop_rules_example_validates(self) -> None:
        root = Path(__file__).resolve().parents[2]
        failures = validate_plugin_contract_examples(root / "contracts" / "plugins")
        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()

