import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import { renderMarkdown } from '../src/components/editor/panes/markdown/render'

const fileId = '550e8400-e29b-41d4-a716-446655440000'

void describe('Markdown rendering', () => {
  it('resolves Ellia file images while preserving alt and title', () => {
    const source = `![Cover](ellia://file/${fileId} "Front cover")`
    const rendered = renderMarkdown(source, 'https://editor.example.test')

    assert.match(rendered, new RegExp(`<img src="https://editor\\.example\\.test/api/files/${fileId}"`))
    assert.match(rendered, /alt="Cover"/)
    assert.match(rendered, /title="Front cover"/)
    assert.doesNotMatch(rendered, /ellia:\/\/file\//)
  })

  it('keeps ordinary image destinations unchanged', () => {
    const rendered = renderMarkdown('![Remote](https://cdn.example.test/image.png)')
    assert.match(rendered, /src="https:\/\/cdn\.example\.test\/image\.png"/)
  })

  it('renders malformed Ellia images as non-network placeholders', () => {
    const rendered = renderMarkdown('![Broken](ellia://file/not-a-uuid)')
    assert.match(rendered, /class="markdown-image--invalid"/)
    assert.match(rendered, /aria-label="Broken"/)
    assert.doesNotMatch(rendered, /src=/)
    assert.doesNotMatch(rendered, /ellia:\/\//)
  })

  it('does not mutate source content or leak a resolved URL across renders', () => {
    const source = `![Cover](ellia://file/${fileId})`
    const first = renderMarkdown(source, 'https://first.example.test')
    const second = renderMarkdown(source, 'https://second.example.test')

    assert.match(first, /https:\/\/first\.example\.test\/api\/files/)
    assert.match(second, /https:\/\/second\.example\.test\/api\/files/)
    assert.doesNotMatch(second, /first\.example\.test/)
    assert.equal(source, `![Cover](ellia://file/${fileId})`)
  })

  it('keeps raw HTML disabled', () => {
    const rendered = renderMarkdown('<img src="javascript:alert(1)">')
    assert.match(rendered, /&lt;img src=&quot;javascript:alert\(1\)&quot;&gt;/)
    assert.doesNotMatch(rendered, /<img\s/)
  })
})
