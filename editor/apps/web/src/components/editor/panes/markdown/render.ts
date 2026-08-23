import MarkdownIt from 'markdown-it'

const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: false,
})

export function renderMarkdown(content: string): string {
  return markdown.render(content)
}
