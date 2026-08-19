import 'dotenv/config'
import os from 'node:os'

export interface ServerConfig {
  port: number
  /** 首次启动播种的初始 admin 用户名（M1） */
  adminUsername: string
  /** 初始 admin 密码（.env 提供，未配置时用不安全默认值并在日志提示） */
  adminPassword: string
  /** SQLite 数据库文件路径（相对 apps/server 运行目录） */
  databasePath: string
  /** 服务端会话有效期（天） */
  sessionTtlDays: number
  /** 生产环境给会话 cookie 附加 Secure 标记 */
  secureCookies: boolean
  /** 文件数据目录（UUID → bytes 单层存储） */
  fileDataDir: string
  /** 单文件上传上限（字节） */
  maxFileBytes: number
  /** 每实体历史快照上限 N（建库时固化进 app_meta） */
  entityHistoryLimit: number
  /** 语音：mediasoup WebRtcServer 监听 IP */
  voiceMediaListenIp: string
  /** 语音：mediasoup WebRtcServer 对外公布的地址（IP 或域名，NAT 后使用公网地址） */
  voiceMediaAnnouncedAddress: string
  /** 语音：mediasoup WebRtcServer 监听端口 */
  voiceMediaPort: number
}

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw ?? fallback)
  return Number.isInteger(value) && value > 0 ? value : fallback
}

/** 自动选择本机第一个非内部 IPv4，避免 localhost + VPN/多网卡导致的 ICE 问题 */
function defaultMediaAddress(): string {
  const interfaces = os.networkInterfaces()
  for (const entries of Object.values(interfaces)) {
    for (const entry of entries ?? []) {
      if (entry.family === 'IPv4' && !entry.internal) return entry.address
    }
  }
  return '127.0.0.1'
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ServerConfig {
  return {
    port: parsePositiveInt(env.PORT, 3000),
    adminUsername: env.ADMIN_USERNAME?.trim() || 'admin',
    adminPassword: env.ADMIN_PASSWORD ?? 'admin',
    databasePath: env.DATABASE_PATH?.trim() || 'data/ellia.db',
    sessionTtlDays: parsePositiveInt(env.SESSION_TTL_DAYS, 30),
    secureCookies: env.NODE_ENV === 'production',
    fileDataDir: env.FILE_DATA_DIR?.trim() || 'data/files',
    maxFileBytes: parsePositiveInt(env.MAX_FILE_BYTES, 50 * 1024 * 1024),
    entityHistoryLimit: parsePositiveInt(env.ENTITY_HISTORY_LIMIT, 20),
    voiceMediaListenIp: env.VOICE_MEDIA_LISTEN_IP?.trim() || defaultMediaAddress(),
    voiceMediaAnnouncedAddress:
      env.VOICE_MEDIA_ANNOUNCED_ADDRESS?.trim() || defaultMediaAddress(),
    voiceMediaPort: parsePositiveInt(env.VOICE_MEDIA_PORT, 40_000),
  }
}
