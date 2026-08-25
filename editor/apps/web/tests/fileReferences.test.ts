import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  buildElliaFileUri,
  buildFileAccessUrl,
  buildMarkdownImageReference,
  parseElliaFileReference,
} from '../src/utils/fileReferences'

const fileId = '550e8400-e29b-41d4-a716-446655440000'

void describe('file references', () => {
  void it('parses a canonical Ellia file URI', () => {
    assert.deepEqual(parseElliaFileReference(`ellia://file/${fileId}`), { fileId })
    assert.deepEqual(parseElliaFileReference(`ELLIA://FILE/${fileId.toUpperCase()}`), {
      fileId: fileId.toUpperCase(),
    })
  })

  void it('rejects malformed Ellia file URIs', () => {
    const invalid = [
      'ellia://file/not-a-uuid',
      `ellia://file/${fileId}/extra`,
      `ellia://file/${fileId}?download=1`,
      `ellia://file/${fileId}#fragment`,
      `ellia://other/${fileId}`,
      `/api/files/${fileId}`,
    ]

    for (const value of invalid) {
      assert.equal(parseElliaFileReference(value), null, value)
    }
  })

  it('builds a same-origin file access URL with an encoded id', () => {
    assert.equal(
      buildFileAccessUrl(fileId, 'https://editor.example.test'),
      `https://editor.example.test/api/files/${fileId}`,
    )
    assert.equal(
      buildFileAccessUrl('file id', 'https://editor.example.test/'),
      'https://editor.example.test/api/files/file%20id',
    )
  })

  it('builds stable Ellia URIs and escaped Markdown image references', () => {
    assert.equal(buildElliaFileUri(fileId), `ellia://file/${fileId}`)
    assert.equal(
      buildMarkdownImageReference('cover[front]*_~.png', fileId),
      `![cover\\[front\\]\\*\\_\\~.png](ellia://file/${fileId})`,
    )
    assert.equal(
      buildMarkdownImageReference('cover\\back.png', fileId),
      `![cover\\\\back.png](ellia://file/${fileId})`,
    )
    assert.equal(
      buildMarkdownImageReference('cover\nback.png', fileId),
      `![cover back.png](ellia://file/${fileId})`,
    )
  })

  it('falls back to the file id when no original name is available', () => {
    assert.equal(
      buildMarkdownImageReference(null, fileId),
      `![${fileId}](ellia://file/${fileId})`,
    )
    assert.equal(
      buildMarkdownImageReference('   ', fileId),
      `![${fileId}](ellia://file/${fileId})`,
    )
  })
})
