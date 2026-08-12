/**
 * 管理员种子脚本：从环境变量创建首个 admin 账号（幂等）。
 *
 * 用法：npm run seed-admin
 * 环境变量：ADMIN_USERNAME / ADMIN_PASSWORD（未设置时用默认值并打印警告）
 */

import { db } from './db.js'
import bcrypt from 'bcryptjs'

const username = (process.env.ADMIN_USERNAME || 'admin').trim()
const password = process.env.ADMIN_PASSWORD || 'admin123456'

const exists = db.prepare('SELECT id, username FROM users WHERE role = ?').get('admin')
if (exists) {
  console.log(`管理员已存在（${exists.username}），跳过。`)
  process.exit(0)
}

const hash = bcrypt.hashSync(password, 10)
const now = new Date().toISOString()
db.prepare(
  'INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
).run(crypto.randomUUID(), username, hash, 'admin', now)

console.log(`已创建管理员账号：${username}`)
console.log('密码：' + (process.env.ADMIN_PASSWORD ? '(来自环境变量)' : '默认 admin123456，请尽快通过 .env 修改！'))
