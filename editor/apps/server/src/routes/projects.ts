import { Router } from 'express'

import { isValidModuleId } from '@ellia/puzzle-schema'

import { requireAuth } from '../auth/middleware.js'
import { ApiError } from '../errors.js'
import { createProject, findProjectById, listProjects, updateProject } from '../services/projects.js'

export const projectsRouter = Router()

projectsRouter.use(requireAuth)

projectsRouter.get('/', (_req, res) => {
  res.json({ projects: listProjects() })
})

projectsRouter.post('/', (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  const moduleId = typeof body.module_id === 'string' ? body.module_id : ''
  const displayName = typeof body.display_name === 'string' ? body.display_name : ''

  if (!isValidModuleId(moduleId)) {
    throw new ApiError(400, 'VALIDATION', 'module_id 必须是单一路径段（不含 / 与 \\）')
  }
  if (!displayName.trim()) {
    throw new ApiError(400, 'VALIDATION', 'display_name 不能为空')
  }

  const user = res.locals.user as { id: string }
  const project = createProject(
    {
      module_id: moduleId,
      display_name: displayName,
      description: parseNullableString(body.description, 'description'),
      deploy_baseline: parseNullableString(body.deploy_baseline, 'deploy_baseline'),
    },
    user.id,
  )
  res.status(201).json({ project })
})

projectsRouter.get('/:id', (req, res) => {
  const project = findProjectById(req.params.id)
  if (!project) throw new ApiError(404, 'PROJECT_NOT_FOUND', '项目不存在')
  res.json({ project })
})

projectsRouter.patch('/:id', (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>
  if ('module_id' in body) {
    throw new ApiError(400, 'VALIDATION', 'module_id 创建后不可修改')
  }

  const patch: {
    display_name?: string
    description?: string | null
    deploy_baseline?: string | null
  } = {}
  if (body.display_name !== undefined) {
    const displayName = typeof body.display_name === 'string' ? body.display_name : ''
    if (!displayName.trim()) {
      throw new ApiError(400, 'VALIDATION', 'display_name 不能为空')
    }
    patch.display_name = displayName
  }
  if (body.description !== undefined) {
    patch.description = parseNullableString(body.description, 'description')
  }
  if (body.deploy_baseline !== undefined) {
    patch.deploy_baseline = parseNullableString(body.deploy_baseline, 'deploy_baseline')
  }

  const project = updateProject(req.params.id, patch)
  if (!project) throw new ApiError(404, 'PROJECT_NOT_FOUND', '项目不存在')
  res.json({ project })
})

function parseNullableString(value: unknown, field: string): string | null {
  if (value === null || value === undefined) return null
  if (typeof value === 'string') return value
  throw new ApiError(400, 'VALIDATION', `${field} 必须是字符串或 null`)
}
