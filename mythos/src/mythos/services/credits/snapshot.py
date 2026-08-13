from mythos.services.template_snapshots import TemplateSnapshotStore, TemplateSnapshotStoreError


class CreditTemplateSnapshotError(TemplateSnapshotStoreError):
    pass


class CreditTemplateSnapshotStore(TemplateSnapshotStore):
    _error_type = CreditTemplateSnapshotError
    _snapshot_name = "Credit template"
