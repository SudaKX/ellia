/** 只允许站内相对路径，避免 open redirect。 */
export function safeRedirect(raw: unknown): string {
  if (typeof raw === 'string' && raw.startsWith('/') && !raw.startsWith('//')) {
    return raw
  }
  return '/'
}
