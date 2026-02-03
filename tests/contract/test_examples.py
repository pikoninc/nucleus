import unittest
from pathlib import Path

from nucleus.contract_store import ContractStore


class TestCoreContractExamples(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.core = root / "contracts" / "core"
        self.schemas_dir = self.core / "schemas"
        self.examples_dir = self.core / "examples"
        self.store = ContractStore(self.schemas_dir)
        self.store.load()

    def test_schemas_are_valid(self) -> None:
        errors = self.store.check_schemas()
        self.assertEqual(errors, [])

    def test_intent_example_validates(self) -> None:
        errs = self.store.validate_json_file("intent.schema.json", self.examples_dir / "intent.example.json")
        self.assertEqual(errs, [])

    def test_plan_example_validates(self) -> None:
        errs = self.store.validate_json_file("plan.schema.json", self.examples_dir / "plan.example.json")
        self.assertEqual(errs, [])

    def test_plugin_manifest_example_validates(self) -> None:
        errs = self.store.validate_json_file(
            "plugin_manifest.schema.json", self.examples_dir / "plugin_manifest.example.json"
        )
        self.assertEqual(errs, [])

    def test_trace_sample_validates(self) -> None:
        errs = self.store.validate_jsonl_file("trace_event.schema.json", self.examples_dir / "trace.sample.jsonl")
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()

