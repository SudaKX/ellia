# FileService V1

FileService provides player-authorized access to static virtual files stored in an S3-compatible object store such as RustFS. RustFS stores object bytes only; SQLite remains the authority for player identity, progress, and static-file publication records.

## 1. Identity And Storage

Each file has three distinct identifiers:

| Field | Purpose |
| --- | --- |
| `stable_id` | Internal, semantic module identifier. Never returned by the API. |
| `file_id` | Public opaque identifier returned to a player. It is `f1_` plus an HMAC-SHA256 value derived from `stable_id`. |
| `ObjectReference.key` | Internal RustFS object key. It is independent of `file_id`. |

The public file ID is an opaque locator, not an authorization credential. Every request resolves the ID, then evaluates the registered `access_rule(player)`.

## 2. Registration And Publication

Puzzle modules register static local-file sources separately from virtual Nodes:

```python
readme = registries.files.register_source(
    FileReference(
        module="intro",
        relative_path="assets/README.txt",
        media_type="text/plain; charset=utf-8",
    )
)
registries.files.register_node(
    VirtualNode.file(
        stable_id="intro.readme",
        path="/README.txt",
        revision="1",
        source_locator=readme,
        download_name="README.txt",
        access_rule=lambda player: player.progress.current_account == "PLAYER",
        display=DisplayParams(label="Read me", icon="document"),
    )
)
```

`FileReference.source_locator` is derived from `module` and `relative_path`, for example `intro:assets/README.txt`. At startup the publisher reads `puzzles/<module>/<relative_path>`, checks the SQLite static-file registration, uploads missing or mtime-changed files to RustFS, and produces an `ObjectReference`. `freeze()` then combines the resolved ObjectReference with the Node download name into runtime `FileContent`.

Every `VirtualNode` carries a required `DisplayParams(label, description, icon, sort_order)`. It is returned to the frontend for both files and directories. `icon` is a semantic frontend token, never an asset URL or SVG. A display-only change changes `tree_version` but does not change a file `content_token`.

Directory Nodes use `VirtualNode.directory(...)` and have no source. They can carry an `access_rule`, but have no public `file_id`, metadata or download URL. Empty explicit directories are valid and remain visible to players allowed to access them.

Registration rejects duplicate stable IDs, duplicate virtual paths, duplicate source locators, file/directory conflicts, file Nodes with child Nodes, non-canonical paths and unsafe download names. Every file Node must bind one registered source, and every source must bind at least one file Node. `FileRegistry.freeze()` creates an immutable `FileTree` with a private public-ID lookup map for file Nodes.

For declarative modules, `FileRegistry.register_json_tree(document, path_prefix="/", access_rules=...)` parses a schema-versioned JSON tree with the strict Pydantic `FileTreeManifest` model, resolves symbolic access-rule names from the supplied mapping, registers sources, then registers Nodes through the same single-item APIs. `FileTreeManifest.model_json_schema()` exposes the JSON Schema for editor and CI tooling. The JSON tree derives virtual paths from nested `name` fields; it cannot embed Python access-rule code. Parsing and registration are atomic.

`FileRegistry.register_json_tree_asset(module, relative_asset_path, ...)` reads a manifest from `Settings.puzzle_root / module / relative_asset_path`. The asset path must remain within that module directory, and the manifest `module` field must match the API argument. This keeps module registrations independent of `Path(__file__)` while preserving the existing source location convention.

## 3. Authorization

The access rule receives the concrete request-level `Player`. It must be a pure Read function:

- It may read Player and Interface state.
- It must not modify Player or Interface state.
- It must not mutate global state, query HTTP state or call external services.
- It must return `True` or `False`.

All file-content and directory routes load Player with `writable=False`. `GET /files/version` only verifies the caller identity because `tree_version` is a static Catalog value. File authorization checks every Node from the root to the requested target. A denied directory blocks its whole subtree without evaluating child rules. `ls` evaluates only direct children after this path check; `tree` evaluates one child rule at each recursive level.

## 4. API

```text
GET  /api/v1/files/ls?path=/
GET  /api/v1/files/tree?path=/
GET  /api/v1/files/{file_id}
GET  /api/v1/files/version
GET  /api/v1/files/{file_id}/{content_token}/content-url
GET  /api/v1/files/{file_id}/{content_token}/download-url
```

`FileTree` is built from virtual paths when the registry freezes. It exposes an opaque `tree_version` derived only from static Node definitions and resolved object versions. It does not include player progress. Every file summary and metadata response carries an opaque `content_token` derived from its stable ID, Node revision, RustFS key/VersionId/media type, and download name. A change to access-rule behavior must also increment the affected Node revision.

`GET /files/ls` returns only direct visible children. It verifies the requested path's full ancestor chain, then evaluates only each direct child's access rule; allowed empty directories and allowed directories with no visible descendants are returned. `GET /files/tree` returns the complete nested subtree using the same local rule at every level. Both responses include display parameters and omit denied Nodes. The versioned content URL endpoint validates that `content_token` still matches the current FileTree; stale tokens return `412`.

Metadata, content URL and download URL requests re-evaluate authorization. Missing public IDs return `404`; inaccessible existing files return `403`.

The URL-issuing endpoints return:

```json
{
  "url": "https://rustfs.example/...",
  "expires_at": "2026-07-23T12:00:00+00:00",
  "content_token": "ct1_..."
}
```

The content URL JSON response is cacheable only in the browser profile with `private, max-age, must-revalidate`; its max-age is shorter than its signature TTL. RustFS receives `private, must-revalidate` plus an absolute `Expires` value matching the signature expiry, so a delayed first object request cannot extend byte caching past the URL lifetime. A download URL signs an `attachment` disposition with the registered safe filename, and both its JSON response and RustFS response use `no-store`.

## 5. Object Store

`Boto3ObjectStore` uses `boto3.client("s3")` and S3 `get_object` pre-signing. It also uploads changed static local files during startup. It is created only when all object-store settings are present. An application with no registered static sources can still start without object storage; an application with sources fails startup when object storage is unavailable.

RustFS requirements:

- Keep the configured bucket private.
- Disable anonymous `GetObject` access.
- Create a dedicated backend access key with permission to sign reads for the Mythos bucket.
- Enable bucket versioning. The publisher requires a non-empty `VersionId` from each upload and records it in SQLite.
- The publisher overwrites the stable object key `static/<module>/<relative_path>` only after the local source mtime changes. The resulting VersionId pins each frozen FileTree to an exact object version.
- Do not expose object keys, bucket credentials or internal stable IDs through the API.

A signed URL remains usable until its TTL expires even if player access changes. Content URLs can last up to 12 hours; their browser cache lifetime must remain shorter than the signature TTL. Immediate revocation requires a future backend proxy download path.

## 6. Configuration

```text
MYTHOS_FILE_ID_SIGNING_KEY=<at least 32 bytes>
MYTHOS_OBJECT_STORE_ENDPOINT=https://rustfs.example
MYTHOS_OBJECT_STORE_REGION=us-east-1
MYTHOS_OBJECT_STORE_BUCKET=mythos
MYTHOS_OBJECT_STORE_ACCESS_KEY=<access key>
MYTHOS_OBJECT_STORE_SECRET_KEY=<secret key>
MYTHOS_OBJECT_STORE_USE_TLS=true
MYTHOS_FILE_CONTENT_URL_TTL_SECONDS=43200
MYTHOS_FILE_CONTENT_CACHE_MAX_AGE_SECONDS=42900
MYTHOS_FILE_DOWNLOAD_URL_TTL_SECONDS=900
MYTHOS_PUZZLE_ROOT=./src/mythos/puzzles
```

`MYTHOS_FILE_ID_SIGNING_KEY` must remain stable for a deployment. Rotating it changes public file IDs, FileTree versions, and content tokens; a future key-version migration is required before rotation in a live deployment.

`MYTHOS_OBJECT_STORE_ENDPOINT` must be an absolute HTTP URL without a path prefix, query or fragment. Its scheme must match `MYTHOS_OBJECT_STORE_USE_TLS`; production only accepts an HTTPS endpoint.

## 7. Deferred Work

- 在本地 RustFS 上运行 `MYTHOS_RUSTFS_INTEGRATION=1 pytest tests/test_rustfs_integration.py`，验证 bucket versioning、上传 VersionId、指定版本的预签名读取与响应缓存头。
- Dynamic player artifacts through `ArtifactInterface`.
- File access auditing.
- "Open file" command effects that modify progress.
- Range requests and backend streaming fallback.
