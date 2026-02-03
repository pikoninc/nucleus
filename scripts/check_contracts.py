from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nucleus.contract_store import ContractStore  # noqa: E402
from nucleus.contract_checks import validate_plugin_contract_examples  # noqa: E402


def main() -> int:
    core = ROOT / "contracts" / "core"
    schemas_dir = core / "schemas"
    examples_dir = core / "examples"

    store = ContractStore(schemas_dir)
    store.load()

    schema_errors = store.check_schemas()
    if schema_errors:
        print("Schema validation failed:")
        for name, err in schema_errors:
            print("- {}: {}".format(name, err))
        return 1

    # Validate examples
    failures = []

    failures.extend([("intent.example.json", store.validate_json_file("intent.schema.json", examples_dir / "intent.example.json"))])
    failures.extend([("plan.example.json", store.validate_json_file("plan.schema.json", examples_dir / "plan.example.json"))])
    failures.extend(
        [
            (
                "plugin_manifest.example.json",
                store.validate_json_file("plugin_manifest.schema.json", examples_dir / "plugin_manifest.example.json"),
            )
        ]
    )
    failures.extend(
        [("trace.sample.jsonl", store.validate_jsonl_file("trace_event.schema.json", examples_dir / "trace.sample.jsonl"))]
    )

    ok = True
    for name, errs in failures:
        if errs:
            ok = False
            print("Example {} failed validation:".format(name))
            for e in errs:
                print("  - {}".format(e))

    if not ok:
        return 1

    plugin_failures = validate_plugin_contract_examples(ROOT / "contracts" / "plugins")
    if plugin_failures:
        print("Plugin contract examples failed validation:")
        for f in plugin_failures:
            name = f"{f.plugin_id}: {Path(f.example_path).name} vs {Path(f.schema_path).name}"
            print("- {}: {}".format(name, f.error))
        return 1

    print("Contracts OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

