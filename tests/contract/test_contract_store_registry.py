import unittest
import warnings
from pathlib import Path

from nucleus.contract_store import ContractStore


class TestContractStoreRegistry(unittest.TestCase):
    def test_validate_does_not_use_refresolver(self) -> None:
        """
        jsonschema.RefResolver is deprecated; ContractStore should validate without emitting it.
        """
        root = Path(__file__).resolve().parents[2]
        schemas_dir = root / "contracts" / "core" / "schemas"
        store = ContractStore(schemas_dir)
        store.load()

        # Minimal valid intent example shape (avoid depending on example files here).
        instance = {"intent_id": "test", "params": {}, "scope": {"fs_roots": []}, "context": {}}

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = store.validate("intent.schema.json", instance)

        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        # If RefResolver is used internally, jsonschema emits a DeprecationWarning.
        self.assertEqual(dep_warnings, [])


if __name__ == "__main__":
    unittest.main()

