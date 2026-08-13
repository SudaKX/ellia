# FilterService

`FilterService` 负责动态 SVG filter 的实例生命周期。实例由 `FilterHost` 渲染到 App 根部，调用方通过返回的 `filterId` 在 CSS 中引用对应 filter。

## 所有权与注入

App 根部创建服务、提供注入键并挂载宿主：

```vue
<script setup lang="ts">
import { provide } from 'vue'

import FilterHost from '@/components/desktop/FilterHost.vue'
import { createFilterService, FilterServiceKey } from '@/composables/useFilterService'

const filterService = createFilterService()
provide(FilterServiceKey, filterService)
</script>

<template>
  <FilterHost :instances="filterService.instances" @ready="filterService.markReady" />
  <RouterView />
</template>
```

下级组件使用 `useFilterService()` 获取同一个服务；在提供者之外调用会抛出错误。

## API

| 方法或状态 | 说明 |
| --- | --- |
| `instances` | 由 `FilterHost` 消费的实例列表。 |
| `create(type, options)` | 创建实例，返回 `instanceId`、`filterId` 和 `ready`。 |
| `update(instanceId, options)` | 合并更新实例参数。 |
| `destroy(instanceId)` | 销毁一个实例并释放其资源。 |
| `destroyAll()` | 销毁全部实例。 |
| `markReady(instanceId)` | 由 FilterHost 在 filter 组件预热完成时调用。 |

## 创建与引用

```ts
const filterService = useFilterService()

const glitch = filterService.create('glitch', {
  intensity: 12,
  chromaticAberration: 0.002,
  animate: true,
  frameSkip: 8,
})

await glitch.ready

element.style.filter = `url(#${glitch.filterId})`
```

`ready` 在 filter 组件完成资源预热后解析。当前 glitch filter 会在空闲时生成并预解码 64 张 displacement map；实例在预热完成前不会开始播放帧池。实例提前销毁时，`ready` 也会解析，避免加载流程永久等待。

## Glitch 参数

`glitch` 的参数类型为 `GlitchOptions`：

- `seed`：帧池随机序列的起点。
- `intensity`：位移映射的强度。
- `frequencyX`、`frequencyY`：碎片和横带密度。
- `enableHorizontalDisplacement`、`enableVerticalDisplacement`：分别控制红、绿通道位移。
- `chromaticAberration`：红绿通道相反方向的水平 RGB 分离距离。
- `animate`：是否播放预生成帧池。
- `frameSkip`：每隔多少个 rAF 切换一帧。

## 窗口共享 filter

窗口不自行创建 filter。`DesktopView` 创建一个共享 glitch 实例，并将 `filterId` 传给 `WindowFrame`。窗口声明 `filters: { glitch: true }` 后引用该共享实例，因此不会为每个窗口重复创建 Canvas、Blob URL 或动画循环。

## 添加 filter

1. 在 `src/registries/filters.ts` 的 `FilterOptionsByType` 中加入参数类型。
2. 创建 filter 定义组件。它必须接收 `filterId` 与 `options` props。
3. 组件在完成可用资源初始化后发出 `ready` 事件。
4. 在同一注册表中把类型映射到组件；`FilterHost` 会自动实例化它。
5. 通过 `filterService.create('your-filter', options)` 创建并在不再需要时销毁。

新的 filter 如果含有异步预热，必须确保无论正常完成还是提前销毁，调用方等待的 `ready` 都不会永久挂起。
