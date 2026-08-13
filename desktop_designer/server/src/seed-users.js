/**
 * 预置账号种子脚本：创建 10 个固定账号（1 管理员 + 9 普通出题者）。
 *
 * 用法：npm run seed-users
 * 幂等：已存在的用户名跳过，可重复执行。
 *
 * 账号清单（用户名 / 密码 / 角色）：
 *   admin1453    / admin1453    / admin（管理员）
 *   puzzler01    / puzzler1453  / author
 *   puzzler02    / puzzler1453  / author
 *   ...
 *   puzzler09    / puzzler1453  / author
 */

import { db } from './db.js'
import bcrypt from 'bcryptjs'

const USERS = [
  { username: 'admin1453', password: 'admin1453', role: 'admin' },
  ...Array.from({ length: 9 }, (_, index) => ({
    username: `puzzler${String(index + 1).padStart(2, '0')}`,
    password: 'puzzler1453',
    role: 'author',
  })),
]

let created = 0
const now = new Date().toISOString()

for (const user of USERS) {
  const exists = db.prepare('SELECT id FROM users WHERE username = ?').get(user.username)
  if (exists) {
    console.log(`跳过（已存在）：${user.username}`)
    continue
  }
  const hash = bcrypt.hashSync(user.password, 10)
  db.prepare(
    'INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
  ).run(crypto.randomUUID(), user.username, hash, user.role, now)
  console.log(`已创建：${user.username}（${user.role}）`)
  created += 1
}

console.log(`完成：本次新建 ${created} 个账号，共 ${USERS.length} 个预置账号。`)
