import 'dotenv/config'

export interface ServerConfig {
  port: number
  /** M1：首次启动播种的初始 admin 用户名 */
  adminUsername: string
  /** M1：初始 admin 密码（.env 提供，未配置时用不安全默认值并在日志提示） */
  adminPassword: string
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): ServerConfig {
  const rawPort = Number(env.PORT ?? 3000)
  return {
    port: Number.isInteger(rawPort) && rawPort > 0 ? rawPort : 3000,
    adminUsername: env.ADMIN_USERNAME ?? 'admin',
    adminPassword: env.ADMIN_PASSWORD ?? 'admin',
  }
}
