/**
 * # useBrowserPolicy — 浏览器安全拦截策略
 *
 * 纯函数模块（无 Vue 依赖）：判定"某地址是否允许浏览器加载"。
 *
 * ## 为什么需要它
 *
 * FakeOS 浏览器（Browser.vue）是"沙盒内受限网络访问"的叙事载体：
 * 玩家浏览器若加载 localhost / 127.0.0.1 即可访问本机服务（后端 API、
 * 开发者工具），这与"玩家权限受限"的设定冲突，也属于潜在越权面。
 * 早期实现只按主机名字符串精确匹配 `localhost` / `127.0.0.1`，存在明显绕过：
 *
 * - `file:` / `data:` / `javascript:` 等协议解析出的 hostname 为空字符串，不命中集合
 * - `127.1`、`0x7f000001`、`0177.1`、`2130706433` 等 IP 字面量变形（实际解析为 127.0.0.1）
 * - 私有/内网网段（10.x、172.16-31.x、192.168.x）、IPv6 回环 `[::1]` 均未覆盖
 *
 * 本模块按"协议 → 主机名 → IP 网段"三层判定，命中任一即拒绝。
 *
 * ## 设计决策
 *
 * ### 宁可错杀
 * 纯数字主机名（1~4 段、十进制/十六进制/八进制混合）一律按 IP 字面量解析，
 * 解析后命中保留网段即拒绝——安全边界优先于可用性。
 *
 * ### 不解析域名
 * 域名是否解析到内网（DNS rebinding）无法在浏览器沙盒内静态判定，
 * 因此仅拦截字面 IP / localhost；普通域名一律放行。此为已知限制。
 *
 * ### 纯函数、可测试
 * 不引入 Vue API，模块级常量 + 导出函数，与 useFileSystem.ts 同风格。
 *
 * ## 使用示例
 *
 * ```ts
 * import { evaluateBrowserAddress } from '@/composables/useBrowserPolicy'
 *
 * evaluateBrowserAddress('localhost')          // false → 走"禁止访问"页
 * evaluateBrowserAddress('127.1')              // false → 实际解析为 127.0.0.1
 * evaluateBrowserAddress('https://example.com') // true  → 正常加载
 * ```
 */

// ─── 协议黑名单 ──────────────────────────────────────
// 这些协议在 iframe 中要么加载本机文件（file:）、要么执行脚本（data:/javascript:），
// 要么是无内容占位（about:），一律拒绝。
const DENIED_PROTOCOLS = new Set(['file:', 'data:', 'javascript:', 'about:', 'blob:'])

/**
 * 解析单个 IPv4 分段：支持十进制、`0x` 十六进制、`0` 前缀八进制。
 *
 * @param part - 分段字符串（不含点）
 * @returns 数值，非法分段返回 null
 */
function parseSegment(part: string): number | null {
  let value: number
  if (/^0[xX][0-9a-fA-F]+$/.test(part)) {
    value = parseInt(part.slice(2), 16)
  } else if (/^0[0-7]+$/.test(part)) {
    value = parseInt(part, 8)
  } else if (/^\d+$/.test(part)) {
    value = parseInt(part, 10)
  } else {
    return null
  }
  if (!Number.isFinite(value) || value < 0) return null
  return value
}

/**
 * 解析 IPv4 字面量（兼容短形式与进制变形，语义对齐 POSIX inet_aton）。
 *
 * 规则：
 * - 1~4 段；每段支持十进制 / 0x 十六进制 / 0 前缀八进制
 * - 非最后一段各占 1 字节（0–255）
 * - 最后一段占剩余字节位宽（1 段→4 字节、2 段→3 字节、3 段→2 字节、4 段→1 字节），
 *   因此 `127.1` = 127.0.0.1、`2130706433` = 127.0.0.1
 *
 * @param host - 主机名字符串（已确定是数字形态）
 * @returns 32 位无符号整数，非法（含非数字字符）返回 null
 */
function parseIpv4Literal(host: string): number | null {
  const parts = host.split('.')
  if (parts.length === 0 || parts.length > 4) return null

  const segments: number[] = []
  for (const part of parts) {
    const value = parseSegment(part)
    if (value === null) return null
    segments.push(value)
  }

  let value = 0
  for (let i = 0; i < segments.length; i++) {
    const isLast = i === segments.length - 1
    // 最后一段占剩余字节位宽，其余各占 1 字节
    const byteCount = isLast ? 4 - segments.length + 1 : 1
    const max = 2 ** (8 * byteCount) - 1
    if (segments[i] > max) return null
    value = isLast ? (value << (8 * byteCount)) + segments[i] : (value << 8) + segments[i]
  }
  return value >>> 0
}

/**
 * 组合 4 字节为无符号 32 位 IPv4 值。
 *
 * @param a - 第一字节（最高位）
 * @param b - 第二字节
 * @param c - 第三字节
 * @param d - 第四字节（最低位）
 * @returns 32 位无符号整数值
 */
function ipv4(a: number, b: number, c: number, d: number): number {
  return ((a << 24) | (b << 16) | (c << 8) | d) >>> 0
}

/**
 * 业务指定的精确禁止 IP（与网段规则分开维护，便于后续按剧情需要增删）。
 * 如游戏世界观中"玩家无权访问的服务器地址"。
 */
const EXACT_BLOCKED_IPV4 = new Set<number>([
  ipv4(121, 37, 190, 132), // 121.37.190.132
])

/**
 * 判定 32 位 IPv4 值是否命中保留/内网网段或业务黑名单。
 *
 * @param value - 无符号 32 位 IPv4
 * @returns true 表示应拦截
 */
function isBlockedIpv4(value: number): boolean {
  // 业务精确黑名单优先
  if (EXACT_BLOCKED_IPV4.has(value)) return true
  // 127.0.0.0/8 回环
  if ((value >>> 24) === 127) return true
  // 0.0.0.0/8 未指定
  if ((value >>> 24) === 0) return true
  // 10.0.0.0/8 私有
  if ((value >>> 24) === 10) return true
  // 172.16.0.0/12 私有（172.16.0.0 – 172.31.255.255，高 12 位均为 0xAC1）
  if ((value >>> 20) === 0xac1) return true
  // 192.168.0.0/16 私有
  if ((value >>> 16) === 0xc0a8) return true
  // 169.254.0.0/16 链路本地
  if ((value >>> 16) === 0xa9fe) return true
  // 100.64.0.0/10 运营商级 NAT（CGNAT）
  if ((value >>> 22) === 0x191) return true
  return false
}

/**
 * 判定 IPv6 地址是否应拦截（字符串前缀匹配，不做完整校验）。
 *
 * @param host - 不含方括号的 IPv6 主机名
 * @returns true 表示应拦截
 */
function isBlockedIpv6(host: string): boolean {
  // IPv4-mapped 地址 ::ffff:a.b.c.d → 交给 IPv4 网段判定
  const v4Mapped = host.match(/^::ffff:(.+)$/i)
  if (v4Mapped) {
    const v4 = parseIpv4Literal(v4Mapped[1])
    return v4 !== null && isBlockedIpv4(v4)
  }
  // ::1 回环、:: 未指定
  if (host === '::1' || host === '::') return true
  // fc00::/7 唯一本地地址（ULA，等价内网）
  if (/^f[c-d]/i.test(host)) return true
  // fe80::/10 链路本地
  if (/^fe[89ab]/i.test(host)) return true
  return false
}

/**
 * 判断地址是否允许浏览器加载。
 *
 * 判定顺序：协议黑名单 → 主机名（localhost / 空）→ IP 字面量网段。
 * 命中任一拒绝条件返回 false（调用方走"禁止访问"页），否则返回 true。
 *
 * @param raw - 地址栏原始输入（允许无协议，如 `example.com`）
 * @returns true 允许加载；false 应拦截
 */
export function evaluateBrowserAddress(raw: string): boolean {
  const trimmed = raw.trim()
  if (!trimmed) return false

  // 优先按原样解析；无协议（或 scheme 被误判，如 `example.com:8080`）时补 https://
  let url: URL | null = null
  try {
    url = new URL(trimmed)
  } catch {
    url = null
  }
  // 协议层拦截（file:/data:/javascript: 等，其 hostname 为空无法用主机名判定）
  if (url && DENIED_PROTOCOLS.has(url.protocol)) return false
  if (!url || url.hostname === '') {
    try {
      url = new URL(`https://${trimmed}`)
    } catch {
      return false
    }
    if (DENIED_PROTOCOLS.has(url.protocol)) return false
  }

  // 主机名层
  const hostname = url.hostname
  if (!hostname) return false
  const lower = hostname.toLowerCase()
  if (lower === 'localhost' || lower === 'localhost.localdomain' || lower.endsWith('.localhost')) {
    return false
  }

  // IP 层：含冒号视为 IPv6（URL.hostname 对 IPv6 会带方括号，先剔除）
  if (lower.includes(':')) {
    const bare = lower.startsWith('[') && lower.endsWith(']') ? lower.slice(1, -1) : lower
    return !isBlockedIpv6(bare)
  }

  // IPv4 字面量（含 127.1 / 0x7f000001 等变形）；解析失败视为普通域名放行
  const v4 = parseIpv4Literal(lower)
  if (v4 !== null) {
    return !isBlockedIpv4(v4)
  }
  return true
}
