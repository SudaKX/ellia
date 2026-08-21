// 随机生成工具：供 RandomPanel 使用。
// 纯随机部分使用 Web Crypto / crypto.getRandomValues；派生部分使用 Web Crypto digest。

export type RandomDelimitedStyle = 'kebab' | 'snake'

const ALPHANUMERIC_POOL = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
const LOWERCASE_ALNUM_POOL = 'abcdefghijklmnopqrstuvwxyz0123456789'
const LOWERCASE_LETTERS = 'abcdefghijklmnopqrstuvwxyz'

const UUID_V5_DNS_NAMESPACE = '6ba7b810-9dad-11d1-80b4-00c04fd430c8'

function randomInt(max: number): number {
  const values = new Uint32Array(1)
  crypto.getRandomValues(values)
  return (values[0] ?? 0) % max
}

function randomFromPool(pool: string, length: number): string {
  let result = ''
  for (let index = 0; index < length; index += 1) {
    result += pool[randomInt(pool.length)] ?? ''
  }
  return result
}

/** 随机字母数字串，字符集 [a-zA-Z0-9]。 */
export function randomAlphanumeric(length: number): string {
  const safeLength = Math.max(1, Math.floor(length))
  return randomFromPool(ALPHANUMERIC_POOL, safeLength)
}

/** 随机 kebab-case：小写字母/数字段，段首为字母，段间用 - 分隔。 */
export function randomKebabCase(segmentCount: number, segmentLength: number): string {
  return randomDelimited('kebab', segmentCount, segmentLength)
}

/** 随机 snake_case：小写字母/数字段，段首为字母，段间用 _ 分隔。 */
export function randomSnakeCase(segmentCount: number, segmentLength: number): string {
  return randomDelimited('snake', segmentCount, segmentLength)
}

function randomDelimited(
  style: RandomDelimitedStyle,
  segmentCount: number,
  segmentLength: number,
): string {
  const safeSegments = Math.max(1, Math.floor(segmentCount))
  const safeLength = Math.max(1, Math.floor(segmentLength))
  const separator = style === 'kebab' ? '-' : '_'
  const parts: string[] = []
  for (let index = 0; index < safeSegments; index += 1) {
    const first = LOWERCASE_LETTERS[randomInt(LOWERCASE_LETTERS.length)] ?? 'a'
    const rest = randomFromPool(LOWERCASE_ALNUM_POOL, Math.max(0, safeLength - 1))
    parts.push(`${first}${rest}`)
  }
  return parts.join(separator)
}

/** 随机 UUID v4。 */
export function randomUuid(): string {
  return crypto.randomUUID()
}

/** UTF-8 文本的 SHA-256 hex 摘要。 */
export async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input)
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))
  return [...digest].map((byte) => byte.toString(16).padStart(2, '0')).join('')
}

/** UTF-8 文本的标准 Base64 编码。 */
export function base64Encode(input: string): string {
  const bytes = new TextEncoder().encode(input)
  let binary = ''
  const chunkSize = 0x8000
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    const chunk = bytes.subarray(offset, offset + chunkSize)
    binary += String.fromCharCode(...chunk)
  }
  return btoa(binary)
}

/**
 * 从输入文本派生确定性 UUID v5。
 * 默认使用 DNS 命名空间；相同输入始终得到相同 UUID。
 */
export async function uuidV5FromInput(
  input: string,
  namespace: string = UUID_V5_DNS_NAMESPACE,
): Promise<string> {
  const namespaceBytes = parseUuid(namespace)
  const nameBytes = new TextEncoder().encode(input)
  const data = new Uint8Array(namespaceBytes.length + nameBytes.length)
  data.set(namespaceBytes)
  data.set(nameBytes, namespaceBytes.length)

  const digest = new Uint8Array(await crypto.subtle.digest('SHA-1', data))
  const byte6 = digest[6] ?? 0
  const byte8 = digest[8] ?? 0
  digest[6] = (byte6 & 0x0f) | 0x50
  digest[8] = (byte8 & 0x3f) | 0x80
  return formatUuid(digest.subarray(0, 16))
}

function parseUuid(value: string): Uint8Array {
  const hex = value.replace(/-/g, '')
  const bytes = new Uint8Array(16)
  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(hex.slice(index * 2, index * 2 + 2), 16)
  }
  return bytes
}

function formatUuid(bytes: Uint8Array): string {
  const hex = [...bytes].map((byte) => byte.toString(16).padStart(2, '0')).join('')
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join('-')
}
