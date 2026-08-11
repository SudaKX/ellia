## Why

Mythos currently has no persistent achievement system, so puzzle modules cannot declare player milestones and ordinary player operations cannot record or compensate achievement progress. The existing command boundary already provides the transaction and Request-ID primitives needed to add this capability without coupling achievements to Auth or Task execution.

## What Changes

- Add a frozen `AchievementRegistry` and runtime `AchievementCatalog` for puzzle-defined achievement declarations.
- Add HMAC-derived achievement `public_id` values using the existing file-ID signing key and an achievement-specific domain.
- Add persistent per-player achievement state containing only earned and claim timestamps.
- Add active achievement querying, explicit compensation checks, immediate effects, and explicit claim effects.
- Add startup-only fallbacks for historical achievements removed from the active catalog; removed achievements remain display-only and cannot be claimed.
- **BREAKING** Change the existing Achievement post-operation boundary from an in-Operation phase to independent Check and Effect transactions after Operation commit.
- Add non-fatal achievement failure warnings to completed cached command responses while preserving the original Operation result.
- Keep Auth and Task execution outside the achievement flow; `/tasks/process` remains a separate client-triggered command.

## Capabilities

### New Capabilities

- `achievement-system`: Registry, catalog, persistent player state, fallback display data, achievement query/check/claim behavior, and achievement effect execution.

### Modified Capabilities

- `command-execution-boundaries`: Achievement Check and Effect execute after Operation commit in independent transactions; their failures produce warnings and still complete RequestCache responses.

## Impact

- Affected backend areas include `registry`, `persistence`, `players/interfaces`, `services`, `commands`, `endpoints`, startup composition, migrations, and puzzle registration.
- New HTTP endpoints will be mounted under `/api/v1/achievement`.
- Existing file-ID HMAC configuration becomes the signing source for achievement public IDs.
- New database migration and tests are required.
- No new dependency, callback HTTP route, background worker, queue, or Outbox is planned.
