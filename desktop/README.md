# Ellia Desktop

`desktop/` 是 Ellia 的 Vue 3/Vite FakeOS 控制台。当前提供模拟桌面、窗口管理、应用总览、文件浏览、归档查看、终端和 Sandbox 控制界面；桌面状态由 Pinia 管理。

部署基路径固定为 `/console/`，`@` 映射到 `src/`。路由使用该基路径，当前只提供桌面根视图。

## 开发

从仓库根目录使用 pnpm：

```powershell
pnpm --dir desktop install --frozen-lockfile
pnpm --dir desktop dev
```

生产构建会先运行 `vue-tsc --build`，再运行 Vite：

```powershell
pnpm --dir desktop build
```

推荐在编辑器中使用 [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar) 提供 `.vue` 的类型支持。
