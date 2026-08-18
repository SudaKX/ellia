import { defineStore } from 'pinia'
import { ref } from 'vue'

import type { Project } from '@ellia/puzzle-schema'

import {
  createProject,
  getProject,
  listProjects,
  type CreateProjectInput,
} from '../client/rest/projects'

export const useProjectsStore = defineStore('projects', () => {
  const projects = ref<Project[]>([])
  const currentProject = ref<Project | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function loadProjects(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await listProjects()
      projects.value = response.projects
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目列表失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function loadProject(id: string): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const response = await getProject(id)
      currentProject.value = response.project
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载项目失败'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function createNewProject(input: CreateProjectInput): Promise<Project> {
    error.value = null
    try {
      const response = await createProject(input)
      await loadProjects()
      return response.project
    } catch (err) {
      error.value = err instanceof Error ? err.message : '创建项目失败'
      throw err
    }
  }

  return {
    projects,
    currentProject,
    loading,
    error,
    loadProjects,
    loadProject,
    createNewProject,
  }
})