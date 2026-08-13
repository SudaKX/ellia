import pytest

from mythos.registry.accounts import VirtualAccountRegistry, VirtualAccountTemplate
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError


def _template(
    account_id: str = "test.operator",
    *,
    display_name: str = "Test Operator",
    permission: int = 17,
    metadata: dict[str, object] | None = None,
) -> VirtualAccountTemplate:
    return VirtualAccountTemplate(
        account_id=account_id,
        display_name=display_name,
        permission=permission,
        metadata={} if metadata is None else metadata,
    )


def test_virtual_account_registry_builds_catalog_and_snapshot() -> None:
    registry = VirtualAccountRegistry()
    template = _template(metadata={"department": "testing"})
    registry.register_template(template)

    catalog = registry.freeze()

    assert catalog.template("test.operator") is template
    assert catalog.template_or_none("missing") is None
    assert catalog.template_ids == frozenset({"test.operator"})
    assert catalog.template_version.startswith("vac1_")
    assert catalog.snapshot().template_version == catalog.template_version

    entry = catalog.snapshot().entries[0]
    assert entry.kind == "virtual_account"
    assert entry.template_id == "test.operator"
    assert entry.version.startswith("vat1_")
    assert entry.definition == {
        "account_id": "test.operator",
        "display_name": "Test Operator",
        "permission": 17,
        "metadata": {"department": "testing"},
    }


def test_virtual_account_catalog_rejects_unknown_template() -> None:
    catalog = VirtualAccountRegistry().freeze()

    with pytest.raises(RegistryError, match="Virtual account template not found"):
        catalog.template("missing")


def test_virtual_account_registry_rejects_duplicate_template_id() -> None:
    registry = VirtualAccountRegistry()
    registry.register_template(_template())

    with pytest.raises(DuplicateStableIdError):
        registry.register_template(_template())


def test_virtual_account_registry_rejects_registration_after_freeze() -> None:
    registry = VirtualAccountRegistry()
    catalog = registry.freeze()

    assert registry.freeze() is catalog
    with pytest.raises(RegistryFrozenError):
        registry.register_template(_template())


def test_virtual_account_permissions_require_exact_int_type() -> None:
    with pytest.raises(ValueError, match="permissions must be integers"):
        _template(permission=True)
