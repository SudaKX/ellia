# WindowService

`WindowService` 管理应用注册、窗口实例、焦点、最小化、关闭、模态约束和窗口层级。它是一个工厂函数，不是全局注入服务：`DesktopView` 创建并拥有唯一实例，其他组件应通过事件将窗口操作上提给 DesktopView，而不应各自调用 `useWindowService()` 创建独立状态。

## 注册应用

应用定义位于 `src/registries/applications.ts`。每个条目包含应用 ID、标题、图标、异步内容组件和默认窗口尺寸。

```ts
for (const descriptor of Object.values(applicationRegistry)) {
  windowService.registerApplication(descriptor)
}
```

打开已注册应用：

```ts
windowService.open('files')
```

若同一应用已有窗口，`open()` 会恢复并聚焦最高层实例；否则使用注册表创建窗口。

## 窗口命令

`send()` 接收判别联合 `WindowMessage`：

```ts
windowService.send({ type: 'focus-window', windowId })
windowService.send({ type: 'minimize-window', windowId })
windowService.send({ type: 'close-window', windowId })

windowService.send({
  type: 'create-window',
  payload: {
    title: 'Notice',
    icon: Info,
    component: MessageBox,
    defaultWidth: 440,
    defaultHeight: 220,
  },
})
```

`create-window` 返回窗口实例或 `null`；其余命令没有返回值。`WindowFrame` 将内容组件发出的 `close` 事件转为窗口关闭动画。

## CreateWindowPayload

| 字段 | 说明 |
| --- | --- |
| `applicationId` | 可选的注册应用 ID。一次性窗口可省略。 |
| `title`、`icon`、`component` | 窗口标题栏和动态内容组件。 |
| `componentProps` | 传给内容组件的 props。 |
| `defaultWidth`、`defaultHeight` | 初始尺寸。 |
| `placement` | `cascade` 或 `center`。 |
| `mode` | `normal` 或 `modal`，默认 `normal`。 |
| `controls` | `minimize`、`close` 的可用性开关。 |
| `resizable` | 是否渲染并允许使用尺寸调整手柄，默认 `true`。 |
| `filters` | 已注册 filter 的布尔开关，例如 `{ glitch: true }`。 |

## 模态窗口与层级

普通窗口和模态窗口使用独立队列分配 z-index。模态窗口存在时：

- 普通窗口不能获得焦点，也不能新建。
- 模态窗口不可最小化。
- 共享遮罩覆盖普通窗口和 Dock。
- 关闭最上层模态窗口后，焦点回到下一个可见窗口。

网络状态面板通过 `DesktopStatusBar` 发出 `networkAction`，由 `DesktopView` 转换为 `create-window` 命令，因此状态栏不直接拥有 WindowService。

## 添加应用

1. 在 `src/types/desktop.ts` 的 `ApplicationId` 联合类型中加入 ID。
2. 在 `src/components/applications/` 创建应用内容组件。
3. 在 `src/registries/applications.ts` 新增条目。使用 `defineAsyncComponent(() => import(...))` 保持按需加载。
4. 在 `src/stores/desktop.ts` 的应用目录中加入名称、描述、分组和可用状态，使 Launchpad 能显示它。
5. 若应用需要 Dock 图标，DockBar 已从应用注册表读取 `icon`，无需额外映射。

应用组件应专注于内容本身。窗口控制、拖拽、缩放、进入和退出动画由 `WindowFrame` 统一提供。
