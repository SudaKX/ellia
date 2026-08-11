from importlib import import_module

import pytest


def test_content_versions_migration_is_irreversible() -> None:
    migration = import_module("migrations.versions.0010_content_versions")

    with pytest.raises(RuntimeError, match="irreversible"):
        migration.downgrade()
