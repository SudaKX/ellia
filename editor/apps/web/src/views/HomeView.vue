<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { useProjectsStore } from '../stores/projects'

const auth = useAuthStore()
const projectsStore = useProjectsStore()
const router = useRouter()

const moduleId = ref('')
const displayName = ref('')
const creating = ref(false)
const formError = ref<string | null>(null)

onMounted(() => {
  projectsStore.loadProjects().catch(() => undefined)
})

async function submitCreate(): Promise<void> {
  formError.value = null
  if (!moduleId.value.trim() || !displayName.value.trim()) {
    formError.value = 'module_id 与 display_name 不能为空'
    return
  }
  creating.value = true
  try {
    const project = await projectsStore.createNewProject({
      module_id: moduleId.value.trim(),
      display_name: displayName.value.trim(),
    })
    moduleId.value = ''
    displayName.value = ''
    await router.push(`/projects/${project.id}`)
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '创建项目失败'
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <main class="page">
    <header class="card card--fill">
      <h1>项目</h1>
      <p>
        你好，<strong>{{ auth.user?.username }}</strong>（{{ auth.user?.role }}）。
      </p>
      <p class="muted">选择一个项目进入多人编辑器，或创建新项目。</p>
    </header>

    <section class="card" aria-labelledby="create-title">
      <h2 id="create-title">新建项目</h2>
      <form class="stack" @submit.prevent="submitCreate">
        <label class="field">
          <span>module_id</span>
          <input v-model="moduleId" autocomplete="off" placeholder="example2" />
        </label>
        <label class="field">
          <span>display_name</span>
          <input v-model="displayName" autocomplete="off" placeholder="示例模块" />
        </label>
        <p v-if="formError" class="error-text" role="alert">{{ formError }}</p>
        <button class="btn btn--primary" type="submit" :disabled="creating">
          {{ creating ? '创建中…' : '创建项目' }}
        </button>
      </form>
    </section>

    <section class="card" aria-labelledby="list-title">
      <h2 id="list-title">项目列表</h2>
      <p v-if="projectsStore.loading" class="muted">加载中…</p>
      <p v-else-if="projectsStore.projects.length === 0" class="muted">还没有项目。</p>
      <ul class="project-list">
        <li v-for="project in projectsStore.projects" :key="project.id" class="project-item">
          <RouterLink class="project-link" :to="`/projects/${project.id}`">
            <strong>{{ project.display_name }}</strong>
            <span class="muted">{{ project.module_id }}</span>
          </RouterLink>
        </li>
      </ul>
    </section>
  </main>
</template>

<style scoped>
.project-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 8px;
}

.project-item {
  border: 1px solid var(--md-sys-color-outline-variant, #cac4d0);
  border-radius: 8px;
  overflow: hidden;
}

.project-link {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  color: inherit;
  text-decoration: none;
}

.project-link:hover {
  background: var(--md-sys-color-surface-container-high, #ece6f0);
}

.field {
  display: grid;
  gap: 4px;
}
</style>