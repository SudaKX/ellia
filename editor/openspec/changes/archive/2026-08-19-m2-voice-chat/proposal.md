## Why

编辑器缺少实时语音沟通能力，多人协作时无法即时讨论谜题模块。需要为 project 提供低延迟语音频道，并复用服务端权威同步与 WS 信令基础设施。

## What Changes

- 新增 project 级语音频道：SQLite 持久化频道元数据，频道人数上限 8 人。
- 新增 HTTP 频道管理端点：列表、创建、删除。
- 新增 voice WebSocket 端点 `/ws/projects/:id/voice`：处理频道加入/离开、RTP 能力、WebRTC transport、producer/consumer、静音、说话人状态。
- 后端引入 mediasoup 作为 SFU，通过 `WebRtcServer` 单 UDP 端口承载多路 WebRTC 媒体。
- 前端新增 `VoiceService` 抽象与 mediasoup-client 实现，在 project 内持续连接、播放远端音频。
- 前端新增语音设置面板、常驻音频宿主、说话人悬浮层、频道状态展示。
- 音频默认 Opus 128kbps；支持浏览器降噪、麦克风/扬声器音量、静音阈值与 VAD 自动暂停发送。

## Capabilities

### New Capabilities

- `voice-chat`: 在线语音频道管理、WebRTC 媒体传输、成员状态、音频设置与说话人指示。

### Modified Capabilities

无。

## Impact

- `packages/puzzle-schema`：新增 voice 共享类型。
- `apps/server`：新增 `voice_channels` 迁移、mediasoup service、voice WS/HTTP 路由；新增依赖 `mediasoup`，移除 `werift`。
- `apps/web`：新增 `mediasoup-client` 依赖、VoiceService、voice store、语音相关 UI 组件。
- 配置：新增 `VOICE_MEDIA_LISTEN_IP`、`VOICE_MEDIA_ANNOUNCED_ADDRESS`、`VOICE_MEDIA_PORT`。
