import type { Project } from '@ellia/puzzle-schema'

import { jsonBody, request } from '../http'

export interface CreateProjectInput {
  module_id: string
  display_name: string
  description?: string | null
  deploy_baseline?: string | null
}

export interface UpdateProjectInput {
  display_name?: string
  description?: string | null
  deploy_baseline?: string | null
}

export interface ProjectListResponse {
  projects: Project[]
}

export interface ProjectResponse {
  project: Project
}

export function listProjects(): Promise<ProjectListResponse> {
  return request<ProjectListResponse>('/api/projects')
}

export function createProject(input: CreateProjectInput): Promise<ProjectResponse> {
  return request<ProjectResponse>('/api/projects', {
    method: 'POST',
    body: jsonBody(input),
  })
}

export function getProject(id: string): Promise<ProjectResponse> {
  return request<ProjectResponse>(`/api/projects/${encodeURIComponent(id)}`)
}

export function updateProject(
  id: string,
  input: UpdateProjectInput,
): Promise<ProjectResponse> {
  return request<ProjectResponse>(`/api/projects/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: jsonBody(input),
  })
}