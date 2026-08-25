import MarkdownIt, {
  type Env,
  type MarkdownItOptions,
  type Renderer,
  type Token,
} from 'markdown-it'

import { buildFileAccessUrl, parseElliaFileReference } from '../../../../utils/fileReferences'

const INVALID_ELLIA_IMAGE_LABEL = '图片引用无效'

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
})

const defaultImageRenderer = markdown.renderer.rules.image

type MarkdownRenderEnv = Env & {
  elliaFileOrigin?: string
}

markdown.renderer.rules.image = (tokens, idx, options, env, renderer) => {
  const token = tokens[idx]
  const source = token?.attrGet('src')
  if (typeof source !== 'string') {
    return defaultImageRenderer?.(tokens, idx, options, env, renderer) ?? renderer.renderToken(tokens, idx, options)
  }

  const reference = parseElliaFileReference(source)
  if (reference) {
    const origin = (env as MarkdownRenderEnv | undefined)?.elliaFileOrigin
    return renderWithSource(
      tokens,
      idx,
      buildFileAccessUrl(reference.fileId, origin),
      (nextTokens) =>
        defaultImageRenderer?.(nextTokens, idx, options, env, renderer) ??
        renderer.renderToken(nextTokens, idx, options),
    )
  }

  if (isElliaSource(source)) {
    return renderInvalidElliaImage(tokens, idx, options, env, renderer)
  }

  return defaultImageRenderer?.(tokens, idx, options, env, renderer) ?? renderer.renderToken(tokens, idx, options)
}

export function renderMarkdown(content: string, origin?: string): string {
  const env: MarkdownRenderEnv = {}
  if (origin) env.elliaFileOrigin = origin
  return markdown.render(content, env)
}

function renderWithSource(
  tokens: Token[],
  idx: number,
  source: string,
  render: (tokens: Token[]) => string,
): string {
  const token = tokens[idx]
  if (!token) return ''

  const previousAttrs = token.attrs
  const nextAttrs = previousAttrs?.map(([name, value]) => [name, value] as [string, string | number]) ?? []
  const sourceIndex = nextAttrs.findIndex(([name]) => name === 'src')
  if (sourceIndex >= 0) {
    nextAttrs[sourceIndex] = ['src', source]
  } else {
    nextAttrs.push(['src', source])
  }
  token.attrs = nextAttrs

  try {
    return render(tokens)
  } finally {
    token.attrs = previousAttrs
  }
}

function renderInvalidElliaImage(
  tokens: Token[],
  idx: number,
  options: Required<MarkdownItOptions>,
  env: Env | undefined,
  renderer: Renderer,
): string {
  const token = tokens[idx]
  if (!token) return ''

  const alt = renderer.renderInlineAsText(token.children ?? [], options, env)
  const label = alt || INVALID_ELLIA_IMAGE_LABEL
  const title = token.attrGet('title')
  const titleAttribute = typeof title === 'string'
    ? ` title="${markdown.utils.escapeHtml(title)}"`
    : ''
  const escapedLabel = markdown.utils.escapeHtml(label)

  return `<span class="markdown-image--invalid" role="img" aria-label="${escapedLabel}"${titleAttribute}>${escapedLabel}</span>`
}

function isElliaSource(source: string): boolean {
  return source.toLowerCase().startsWith('ellia:')
}
