/**
 * 认证层：注册 / 登录 / JWT 中间件。
 *
 * 安全要点：
 * - 密码使用 bcryptjs 哈希存储（绝不存明文）
 * - JWT（HS256）签名密钥来自环境变量 JWT_SECRET，默认只用于开发
 * - 请求受保护接口必须携带 `Authorization: Bearer <token>`
 */

import bcrypt from 'bcryptjs'
import jwt from 'jsonwebtoken'

import { db } from './db.js'

const JWT_SECRET = process.env.JWT_SECRET || 'dev-only-secret-change-me'
const TOKEN_TTL = process.env.JWT_TTL || '7d'

/** 生成访问令牌 */
export function signToken(user) {
  return jwt.sign(
    { sub: user.id, username: user.username, role: user.role },
    JWT_SECRET,
    { expiresIn: TOKEN_TTL },
  )
}

/** 注册（默认角色 author） */
export function registerUser(username, password) {
  const name = String(username ?? '').trim()
  if (!name || !password) {
    const error = new Error('用户名和密码不能为空')
    error.status = 400
    throw error
  }
  const exists = db.prepare('SELECT id FROM users WHERE username = ?').get(name)
  if (exists) {
    const error = new Error('用户名已存在')
    error.status = 409
    throw error
  }
  const hash = bcrypt.hashSync(String(password), 10)
  const user = {
    id: crypto.randomUUID(),
    username: name,
    role: 'author',
    created_at: new Date().toISOString(),
  }
  db.prepare(
    'INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
  ).run(user.id, user.username, hash, user.role, user.created_at)
  return user
}

/** 登录校验，成功返回用户 */
export function loginUser(username, password) {
  const row = db.prepare('SELECT * FROM users WHERE username = ?').get(String(username ?? '').trim())
  if (!row || !bcrypt.compareSync(String(password), row.password_hash)) {
    const error = new Error('用户名或密码错误')
    error.status = 401
    throw error
  }
  return { id: row.id, username: row.username, role: row.role, created_at: row.created_at }
}

/** 校验 Bearer token 的 Express 中间件，挂载到受保护路由 */
export function requireAuth(req, _res, next) {
  const header = req.headers.authorization || ''
  const token = header.startsWith('Bearer ') ? header.slice(7) : null
  if (!token) {
    return next(Object.assign(new Error('未登录'), { status: 401 }))
  }
  try {
    req.user = jwt.verify(token, JWT_SECRET)
    return next()
  } catch {
    return next(Object.assign(new Error('登录已过期，请重新登录'), { status: 401 }))
  }
}

/** 仅管理员可访问的中间件（须在 requireAuth 之后使用） */
export function requireAdmin(req, _res, next) {
  if (req.user?.role !== 'admin') {
    return next(Object.assign(new Error('仅管理员可执行此操作'), { status: 403 }))
  }
  return next()
}
