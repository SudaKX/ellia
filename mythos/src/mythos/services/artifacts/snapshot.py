from mythos.services.template_snapshots import TemplateSnapshotStore, TemplateSnapshotStoreError


class ArtifactTemplateSnapshotError(TemplateSnapshotStoreError):
    pass


class ArtifactTemplateSnapshotStore(TemplateSnapshotStore):
    _error_type = ArtifactTemplateSnapshotError
    _snapshot_name = "Artifact template"
