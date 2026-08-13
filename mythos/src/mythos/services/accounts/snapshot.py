from mythos.services.template_snapshots import TemplateSnapshotStore, TemplateSnapshotStoreError


class VirtualAccountTemplateSnapshotError(TemplateSnapshotStoreError):
    pass


class VirtualAccountTemplateSnapshotStore(TemplateSnapshotStore):
    _error_type = VirtualAccountTemplateSnapshotError
    _snapshot_name = "Virtual account template"
