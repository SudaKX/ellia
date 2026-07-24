# FileService V1

FileService provides player-authorized access to static virtual files stored in an S3-compatible object store such as RustFS. RustFS stores object bytes only; SQLite remains the authority for player identity and progress.

## 1. Identity And Storage

Each file has three distinct identifiers:

| Field | Purpose |
| --- | --- |
| `stable_id` | Internal, semantic module identifier. Never returned by the API. |
| `file_id` | Public opaque identifier returned to a player. It is `f1_` plus an HMAC-SHA256 value derived from `stable_id`. |
| `ObjectReference.key` | Internal RustFS object key. It is independent of `file_id`. |

The public file ID is an opaque locator, not an authorization credential. Every request resolves the ID, then evaluates the registered `access_rule(player)`.

## 2. Registration

Puzzle modules register file and directory Nodes through `RegistryBundle.files`:

```python
registries.files.register(
    VirtualNode(
        stable_id="intro.readme",
        path="/README.txt",
        revision="1",
        content=FileContent(
            object_ref=ObjectReference(
                key="modules/intro/1/readme.txt",
                content_digest="sha256:<64 lowercase hex characters>",
                media_type="text/plain; charset=utf-8",
                size_bytes=128,
                version_id="<RustFS object version ID>",
            ),
            download_name="README.txt",
        ),
        access_rule=lambda player: player.progress.current_account == "PLAYER",
    )
)
```

Set `content=None` to register a directory Node. Directory Nodes can carry an `access_rule`, but have no public `file_id`, metadata or download URL. Empty explicit directories are rejected at freeze time.

Registration rejects duplicate stable IDs, duplicate virtual paths, file/directory conflicts, file Nodes with child Nodes, non-canonical paths, unsafe download names and invalid object metadata. `FileRegistry.freeze()` creates an immutable `FileTree` with a private public-ID lookup map for file Nodes.

## 3. Authorization

The access rule receives the concrete request-level `Player`. It must be a pure Read function:

- It may read Player and Interface state.
- It must not modify Player or Interface state.
- It must not mutate global state, query HTTP state or call external services.
- It must return `True` or `False`.

All FileService routes load Player with `writable=False`. File authorization checks every Node from the root to the target file. A denied directory blocks its whole subtree without evaluating child rules; after an allowed directory, unguarded children are visible and guarded children are checked recursively.

## 4. API

```text
GET  /api/v1/files?path=/
GET  /api/v1/files/{file_id}
POST /api/v1/files/{file_id}/content-url
POST /api/v1/files/{file_id}/download-url
```

`FileTree` is built from virtual paths when the registry freezes. The directory endpoint traverses the requested subtree, returning only visible files and directories with visible descendants. Invisible files and directories with no visible descendants are omitted.

Metadata, content URL and download URL requests re-evaluate authorization. Missing public IDs return `404`; inaccessible existing files return `403`.

The URL-issuing endpoints return:

```json
{
  "url": "https://rustfs.example/...",
  "expires_at": "2026-07-23T12:00:00+00:00"
}
```

They set `Cache-Control: no-store`. A content URL signs an `inline` disposition; a download URL signs `attachment` with the registered safe filename.

## 5. Object Store

`Boto3ObjectStore` uses `boto3.client("s3")` and S3 `get_object` pre-signing. It is created only when all object-store settings are present. Without configuration, file lists and metadata can still work, but URL issuing returns `503`.

RustFS requirements:

- Keep the configured bucket private.
- Disable anonymous `GetObject` access.
- Create a dedicated backend access key with permission to sign reads for the Mythos bucket.
- Enable bucket versioning and register the `VersionId` returned when each object is uploaded.
- Store immutable objects under versioned keys such as `modules/<module>/<revision>/<name>`.
- Do not expose object keys, bucket credentials or internal stable IDs through the API.

A signed URL remains usable until its TTL expires even if player access changes. V1 uses a maximum TTL of 300 seconds and defaults to 60 seconds. Immediate revocation requires a future backend proxy download path.

## 6. Configuration

```text
MYTHOS_FILE_ID_SIGNING_KEY=<at least 32 bytes>
MYTHOS_OBJECT_STORE_ENDPOINT=https://rustfs.example
MYTHOS_OBJECT_STORE_REGION=us-east-1
MYTHOS_OBJECT_STORE_BUCKET=mythos
MYTHOS_OBJECT_STORE_ACCESS_KEY=<access key>
MYTHOS_OBJECT_STORE_SECRET_KEY=<secret key>
MYTHOS_OBJECT_STORE_USE_TLS=true
MYTHOS_FILE_DOWNLOAD_URL_TTL_SECONDS=60
```

`MYTHOS_FILE_ID_SIGNING_KEY` must remain stable for a deployment. Rotating it changes public file IDs; a future key-version migration is required before rotation in a live deployment.

`MYTHOS_OBJECT_STORE_ENDPOINT` must be an absolute HTTP URL without a path prefix, query or fragment. Its scheme must match `MYTHOS_OBJECT_STORE_USE_TLS`; production only accepts an HTTPS endpoint.

## 7. Deferred Work

- RustFS integration tests and real presigned URL verification.
- Dynamic player artifacts through `ArtifactInterface`.
- File access auditing.
- "Open file" command effects that modify progress.
- Range requests and backend streaming fallback.
