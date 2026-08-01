# Ellia Desktop

`desktop/` 是基于 Vue 3、Pinia 和 Vite 的桌面交互层。它提供窗口工作区、应用启动器、状态栏菜单、Dock、动态 SVG filter 和模态消息窗口。

## 开发

```sh
pnpm install
pnpm run dev
```

可用脚本：

- `pnpm run type-check`：执行 Vue TypeScript 检查。
- `pnpm run build`：执行类型检查并构建生产产物。
- `pnpm run build-only`：仅执行 Vite 构建。

## 结构

```text
src/
  components/
    applications/      应用内容组件
    desktop/           桌面壳、窗口、状态栏、Dock 和 filter 定义
  composables/         FilterService、WindowService 等组合式函数
  registries/          应用与 filter 的声明式注册表
  stores/              桌面状态与应用目录
  types/               桌面窗口和应用类型
  views/               DesktopView 组合根视图
```

## 核心服务

- [FilterService](services/filter-service.md)：创建、预热、更新和销毁动态 SVG filter。
- [WindowService](services/window-service.md)：注册应用、创建窗口、管理焦点、模态层和窗口命令。

## 前后端对接

- [前后端对接](backend-integration.md)：与 `mythos/` 后端的对接点清单、对接方式与约束。

## 注册表

- `src/registries/applications.ts`：应用标题、图标、异步内容组件和默认窗口尺寸。
- `src/registries/filters.ts`：可用 filter 类型、参数类型和渲染组件。

`DesktopView` 是窗口与共享窗口 filter 的拥有者；`App.vue` 是 FilterService 的提供者和 FilterHost 的挂载点。
