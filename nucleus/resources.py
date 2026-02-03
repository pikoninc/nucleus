from __future__ import annotations

from pathlib import Path


def _package_dir(package_name: str) -> Path:
    """
    Return the on-disk directory for an imported package.

    Note:
    This assumes the package is installed in a filesystem-backed environment
    (typical for pip/wheel installs and editable installs). If a zipimport-style
    environment is used, this may not be a real directory.
    """
    module = __import__(package_name, fromlist=["__file__"])
    p = getattr(module, "__file__", None)
    if not isinstance(p, str) or not p:
        raise RuntimeError(f"Cannot resolve package directory for: {package_name}")
    return Path(p).resolve().parent


def plugins_dir() -> Path:
    """
    Directory that contains built-in plugin packages (e.g. plugins/builtin_desktop).
    """
    return _package_dir("plugins")


def contracts_dir() -> Path:
    """
    Directory that contains shipped contract artifacts (JSON Schemas, examples).
    """
    return _package_dir("contracts")


def core_contracts_schemas_dir() -> Path:
    return contracts_dir() / "core" / "schemas"


def core_contracts_examples_dir() -> Path:
    return contracts_dir() / "core" / "examples"


def plugin_contract_schema_path(plugin_id: str, schema_filename: str) -> Path:
    """
    Resolve a plugin contract schema path under contracts/plugins/.

    Example:
      plugin_contract_schema_path("builtin.desktop", "desktop_rules.schema.json")
    """
    # On disk the directory is currently named like "builtin.desktop"
    return contracts_dir() / "plugins" / plugin_id / "schemas" / schema_filename

