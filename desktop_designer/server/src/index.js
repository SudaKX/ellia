/**
 * 出题器后端入口。
 *
 * 启动：npm start（或 npm run dev 热重载）
 * 环境变量（.env，见 .env.example）：
 *   PORT          监听端口（默认 3000）
 *   JWT_SECRET    JWT 签名密钥（生产环境必须修改）
 *   CORS_ORIGIN   允许的前端来源（默认 http://localhost:5174）
 *   ADMIN_USERNAME / ADMIN_PASSWORD  启动时自动创建管理员（幂等）
 */

import express from 'express'
import cors from 'cors'

import { db } from './db.js'
import { loginUser, registerUser, requireAuth, signToken } from './auth.js'
import { questionsRouter } from './questions.js'
import bcrypt from 'bcryptjs'

const PORT = Number(process.env.PORT || 3000)
const CORS_ORIGIN = process.env.CORS_ORIGIN || 'http://localhost:5174'

const app = express()
app.use(cors({ origin: CORS_ORIGIN, credentials: true }))
app.use(express.json({ limit: '1mb' }))

// 健康检查
app.get('/health', (_req, res) => {
  res.json({ status: 'ok' })
})

// ─── 认证路由 ───────────────────────────────────────

/** POST /api/v1/auth/register — 注册（角色 author） */
app.post('/api/v1/auth/register', (req, res, next) => {
  try {
    const user = registerUser(req.body?.username, req.body?.password)
    return res.status(201).json({ access_token: signToken(user), user })
  } catch (error) {
    return next(error)
  }
})

/** POST /api/v1/auth/login — 登录 */
app.post('/api/v1/auth/login', (req, res, next) => {
  try {
    const user = loginUser(req.body?.username, req.body?.password)
    return res.json({ access_token: signToken(user), user })
  } catch (error) {
    return next(error)
  }
})

/** GET /api/v1/auth/me — 当前用户（前端刷新时恢复登录态） */
app.get('/api/v1/auth/me', requireAuth, (req, res) => {
  return res.json({
    id: req.user.sub,
    username: req.user.username,
    role: req.user.role,
  })
})

// ─── 题目路由 ───────────────────────────────────────

app.use('/api/v1/questions', questionsRouter)

// ─── 统一错误处理 ───────────────────────────────────

app.use((error, _req, res, _next) => {
  const status = error.status || 500
  if (status >= 500) {
    console.error('[server] 未处理错误：', error)
  }
  return res.status(status).json({ error: error.message || '服务器内部错误' })
})

// ─── 启动 ───────────────────────────────────────────

/** 启动时自动创建管理员（幂等，环境变量存在时执行） */
function ensureAdminOnBoot() {
  const username = (process.env.ADMIN_USERNAME || '').trim()
  const password = process.env.ADMIN_PASSWORD || ''
  if (!username || !password) return

  const exists = db.prepare('SELECT id FROM users WHERE role = ?').get('admin')
  if (exists) return

  const hash = bcrypt.hashSync(password, 10)
  db.prepare(
    'INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
  ).run(crypto.randomUUID(), username, hash, 'admin', new Date().toISOString())
  console.log(`[boot] 已自动创建管理员：${username}`)
}

ensureAdminOnBoot()

app.listen(PORT, () => {
  console.log(`出题器后端已启动：http://localhost:${PORT}`)
  console.log(`健康检查：http://localhost:${PORT}/health`)
  console.log(`允许的前端来源：${CORS_ORIGIN}`)
})
