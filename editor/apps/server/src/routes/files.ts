import { createHash, randomUUID } from 'node:crypto'
import { existsSync, mkdirSync, renameSync, unlinkSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import express, { Router } from 'express'

import { requireAuth } from '../auth/middleware.js'
import type { ServerConfig } from '../config.js'
import { ApiError } from '../errors.js'
import { deleteFile, findFileById, insertFile } from '../services/files.js'

export const filesRouter = Router()

filesRouter.use(requireAuth)

filesRouter.post(
  '/',
  (req, res, next) => {
    express
      .raw({ type: () => true, limit: serverConfig(req).maxFileBytes })(req, res, next)
  },
  (req, res) => {
    const config = serverConfig(req)
    const bytes = Buffer.isBuffer(req.body) ? req.body : Buffer.alloc(0)
    const contentTypeHeader = req.headers['content-type']
    const contentType = Array.isArray(contentTypeHeader)
      ? (contentTypeHeader[0] ?? 'application/octet-stream')
      : (contentTypeHeader ?? 'application/octet-stream')
    const mediaType = contentType.split(';')[0].trim()
    const originalName = parseOriginalName(req.headers['x-original-name'])
    const fileId = randomUUID()
    const sha256 = createHash('sha256').update(bytes).digest('hex')

    mkdirSync(path.resolve(config.fileDataDir), { recursive: true })
    const finalPath = path.resolve(config.fileDataDir, fileId)
    const tmpPath = path.resolve(config.fileDataDir, `${fileId}.tmp`)
    writeFileSync(tmpPath, bytes)
    renameSync(tmpPath, finalPath)

    const user = res.locals.user as { id: string }
    const file = insertFile({
      id: fileId,
      originalName,
      mediaType,
      size: bytes.length,
      sha256,
      uploadedBy: user.id,
    })

    res.status(201).json({
      file_id: file.id,
      original_name: file.original_name,
      media_type: file.media_type,
      size: file.size,
      sha256: file.sha256,
      uploaded_by: file.uploaded_by,
      created_at: file.created_at,
    })
  },
)

filesRouter.get('/:file_id', (req, res) => {
  const config = serverConfig(req)
  const file = findFileById(req.params.file_id)
  if (!file) throw new ApiError(404, 'FILE_NOT_FOUND', '文件不存在')

  const filePath = path.resolve(config.fileDataDir, file.id)
  if (!existsSync(filePath)) {
    console.error(`[ellia-server] file metadata exists but bytes missing: ${file.id}`)
    throw new ApiError(404, 'FILE_NOT_FOUND', '文件不存在')
  }
  res.setHeader('Content-Type', file.media_type)
  res.setHeader('X-File-Sha256', file.sha256)
  res.setHeader('X-File-Size', String(file.size))
  if (file.original_name) {
    res.setHeader('X-Original-Name', file.original_name)
  }
  res.sendFile(filePath)
})

filesRouter.delete('/:file_id', (req, res) => {
  const config = serverConfig(req)
  const file = findFileById(req.params.file_id)
  if (!file) throw new ApiError(404, 'FILE_NOT_FOUND', '文件不存在')

  deleteFile(file.id)
  const filePath = path.resolve(config.fileDataDir, file.id)
  try {
    unlinkSync(filePath)
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== 'ENOENT') {
      console.error(`[ellia-server] failed to unlink ${filePath}:`, error)
    }
  }
  res.status(204).end()
})

function serverConfig(req: express.Request): ServerConfig {
  return req.app.locals.config as ServerConfig
}

function parseOriginalName(header: string | string[] | undefined): string | null {
  const value = Array.isArray(header) ? header[0] : header
  return value && value.trim().length > 0 ? value.trim() : null
}
