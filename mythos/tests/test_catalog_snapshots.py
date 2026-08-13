import json

import pytest

from mythos.registry.catalog_snapshots import (
    TemplateSnapshot,
    TemplateSnapshotEntry,
    fingerprint,
    template_snapshot,
    template_snapshot_changed_keys,
)
from mythos.services.artifacts.snapshot import (
    ArtifactTemplateSnapshotError,
    ArtifactTemplateSnapshotStore,
)
from mythos.services.template_snapshots import TemplateSnapshotStore, TemplateSnapshotStoreError


def _snapshot(*entries: TemplateSnapshotEntry) -> TemplateSnapshot:
    return template_snapshot(entries)


def test_template_snapshot_preserves_schema_and_deterministic_version() -> None:
    snapshot = _snapshot(
        TemplateSnapshotEntry("node", "report", "node-v1", {"path": "/report.txt"}),
        TemplateSnapshotEntry("artifact", "report", "artifact-v1", {"media_type": "text/plain"}),
    )

    assert snapshot.as_dict() == {
        "schema_version": 1,
        "template_version": "tv1_82c5fc825e44b34f6a1ee49d51fbb3b71b2f66e08c24dc9926efda439b6d4b46",
        "entries": [
            {
                "kind": "artifact",
                "template_id": "report",
                "version": "artifact-v1",
                "definition": {"media_type": "text/plain"},
            },
            {
                "kind": "node",
                "template_id": "report",
                "version": "node-v1",
                "definition": {"path": "/report.txt"},
            },
        ],
    }
    assert TemplateSnapshot.from_dict(snapshot.as_dict()) == snapshot
    assert fingerprint("tv1_", snapshot.as_dict()["entries"]) == snapshot.template_version


def test_template_snapshot_changed_keys_includes_added_removed_and_updated_entries() -> None:
    previous = _snapshot(
        TemplateSnapshotEntry("artifact", "unchanged", "v1", {}),
        TemplateSnapshotEntry("artifact", "removed", "v1", {}),
        TemplateSnapshotEntry("node", "updated", "v1", {}),
    )
    current = _snapshot(
        TemplateSnapshotEntry("artifact", "added", "v1", {}),
        TemplateSnapshotEntry("artifact", "unchanged", "v1", {}),
        TemplateSnapshotEntry("node", "updated", "v2", {}),
    )

    assert template_snapshot_changed_keys(previous, current) == {
        ("artifact", "added"),
        ("artifact", "removed"),
        ("node", "updated"),
    }


@pytest.mark.anyio
async def test_template_snapshot_store_round_trips_atomic_json(tmp_path) -> None:
    path = tmp_path / "snapshots" / "templates.json"
    snapshot = _snapshot(TemplateSnapshotEntry("artifact", "report", "v1", {"name": "Report"}))
    store = TemplateSnapshotStore(path)

    await store.write(snapshot)

    assert await store.read() == snapshot
    assert json.loads(path.read_text(encoding="utf-8")) == snapshot.as_dict()
    assert not path.with_suffix(".json.tmp").exists()


@pytest.mark.anyio
async def test_template_snapshot_store_rejects_malformed_json(tmp_path) -> None:
    path = tmp_path / "templates.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(TemplateSnapshotStoreError, match="Template snapshot is unreadable"):
        await TemplateSnapshotStore(path).read()


@pytest.mark.anyio
async def test_artifact_snapshot_store_preserves_its_error_type(tmp_path) -> None:
    path = tmp_path / "artifact-templates.json"
    path.write_text("not-json", encoding="utf-8")

    with pytest.raises(
        ArtifactTemplateSnapshotError,
        match="Artifact template snapshot is unreadable",
    ):
        await ArtifactTemplateSnapshotStore(path).read()
