import pytest

from mythos.registry.artifacts import (
    ArtifactNode,
    ArtifactNodeTemplate,
    ArtifactRegistry,
    ArtifactTemplate,
    RawArtifact,
    module_handler,
)
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files import NodeDisplayParams


def _display(label: str) -> NodeDisplayParams:
    return NodeDisplayParams(label=label, icon="document")


@module_handler("test")(1)
def _artifact_generator(_context):
    return RawArtifact(b"content")


@module_handler("test")(1)
async def _node_generator(_context, node):
    node.path = "/dynamic/result.txt"
    return node


def test_artifact_registry_registers_templates_and_nodes() -> None:
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="test.report",
            media_type="text/plain",
            download_name="report.txt",
            generator=_artifact_generator,
        )
    )
    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="test.report-node",
            path="/report.txt",
            artifact_locator="test.report",
            display=_display("Report"),
            node_generator=_node_generator,
        )
    )
    catalog = registry.freeze()
    assert catalog.template("test.report").artifact_id == "test.report"
    assert catalog.node_template("test.report-node").stable_id == "test.report-node"


def test_artifact_registry_rejects_duplicate_template_id() -> None:
    registry = ArtifactRegistry()
    template = ArtifactTemplate(
        artifact_id="test.report",
        media_type="text/plain",
        download_name="report.txt",
        generator=_artifact_generator,
    )
    registry.register_template(template)
    with pytest.raises(DuplicateStableIdError):
        registry.register_template(template)


def test_artifact_registry_rejects_duplicate_node_stable_id() -> None:
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="test.report",
            media_type="text/plain",
            download_name="report.txt",
            generator=_artifact_generator,
        )
    )
    node_template = ArtifactNodeTemplate(
        stable_id="test.report-node",
        path="/report.txt",
        artifact_locator="test.report",
        display=_display("Report"),
        node_generator=_node_generator,
    )
    registry.register_node(node_template)
    with pytest.raises(DuplicateStableIdError):
        registry.register_node(node_template)


def test_artifact_registry_rejects_node_without_artifact() -> None:
    registry = ArtifactRegistry()
    with pytest.raises(RegistryError, match="unknown artifact"):
        registry.register_node(
            ArtifactNodeTemplate(
                stable_id="test.report-node",
                path="/report.txt",
                artifact_locator="test.report",
                display=_display("Report"),
                node_generator=_node_generator,
            )
        )


def test_artifact_templates_require_marked_callbacks() -> None:
    async def unmarked_artifact_generator(_context):
        return RawArtifact(b"content")

    async def unmarked_node_generator(_context, node):
        return node

    with pytest.raises(ValueError, match="module_handler"):
        ArtifactTemplate(
            artifact_id="test.report",
            media_type="text/plain",
            download_name="report.txt",
            generator=unmarked_artifact_generator,
        )
    with pytest.raises(ValueError, match="module_handler"):
        ArtifactNodeTemplate(
            stable_id="test.report-node",
            path="/report.txt",
            artifact_locator="test.report",
            display=_display("Report"),
            node_generator=unmarked_node_generator,
        )


def test_artifact_registry_freezes() -> None:
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="test.report",
            media_type="text/plain",
            download_name="report.txt",
            generator=_artifact_generator,
        )
    )
    registry.freeze()
    with pytest.raises(RegistryFrozenError):
        registry.register_template(
            ArtifactTemplate(
                artifact_id="test.other",
                media_type="text/plain",
                download_name="other.txt",
                generator=_artifact_generator,
            )
        )


def test_artifact_node_template_produces_runtime_node() -> None:
    template = ArtifactNodeTemplate(
        stable_id="test.report-node",
        path="/report.txt",
        artifact_locator="test.report",
        display=_display("Report"),
        node_generator=_node_generator,
    )
    runtime = template.to_runtime_node()
    assert isinstance(runtime, ArtifactNode)
    assert runtime.stable_id == "test.report-node"
    assert runtime.artifact_locator == "test.report"
    assert runtime.is_file


def test_artifact_node_generator_can_mutate_runtime_node() -> None:
    template = ArtifactNodeTemplate(
        stable_id="test.report-node",
        path="/report.txt",
        artifact_locator="test.report",
        display=_display("Report"),
        node_generator=_node_generator,
    )
    runtime = template.to_runtime_node()
    assert runtime.path == "/report.txt"


    def generator(_context, node):
        node.path = "/dynamic/moved.txt"
        node.hidden = True
        return node

    modified = generator(None, runtime)
    assert modified.path == "/dynamic/moved.txt"
    assert modified.version == template.version
    assert modified.hidden is True


def test_artifact_node_stable_id_and_locator_are_immutable() -> None:
    template = ArtifactNodeTemplate(
        stable_id="test.report-node",
        path="/report.txt",
        artifact_locator="test.report",
        display=_display("Report"),
        node_generator=_node_generator,
    )
    runtime = template.to_runtime_node()
    with pytest.raises(AttributeError):
        runtime.stable_id = "other"
    with pytest.raises(AttributeError):
        runtime.artifact_locator = "other"
    with pytest.raises(AttributeError):
        runtime.version = "other"
