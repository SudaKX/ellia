import 'dotenv/config'

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
}

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw ?? fallback)
  return Number.isInteger(value) && value > 0 ? value : fallback
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ServerConfig {
  return {
    port: parsePositiveInt(env.PORT, 3000),
    adminUsername: env.ADMIN_USERNAME?.trim() || 'admin',
    adminPassword: env.ADMIN_PASSWORD ?? 'admin',
    databasePath: env.DATABASE_PATH?.trim() || 'data/ellia.db',
    sessionTtlDays: parsePositiveInt(env.SESSION_TTL_DAYS, 30),
    secureCookies: env.NODE_ENV === 'production',
  }
}
