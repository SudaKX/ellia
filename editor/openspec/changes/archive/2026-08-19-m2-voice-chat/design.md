## Context

现有编辑器已具备项目、实体同步、文件等能力，但缺少实时语音。后端使用 Express + WebSocket + SQLite，前端使用 Vue3 + Pinia。语音需要复用现有认证会话与 WS 基础，同时引入实时媒体转发。

## Goals / Non-Goals

**Goals:**

- 提供 project 级、持久化的语音频道（上限 8 人）。
- 服务端通过 SFU 转发音频，媒体走 UDP。
- 前端在 project 界面持续播放远端音频，并提供可调音频设置。
- 通过现有 voice WS 传递频道、WebRTC 信令、静音与说话人状态。

**Non-Goals:**

- 不做视频。
- 不做频道权限/管理员角色。
- 不做录制、转写、AI 降噪等高级能力。

## Decisions

### 使用 mediasoup 作为 SFU

- 选择 mediasoup 而非自研 werift SFU。
- 理由：mediasoup 提供生产级 SFU、单端口 `WebRtcServer` 解复用、内置带宽/重传/音频电平能力。
- 备选：werift + 自研转发，开发量更大且不够稳定。

### 每成员使用 send / recv 两个 WebRtcTransport

- mediasoup-client 官方要求 send/recv 分离。
- 两个 transport 共享同一个 `WebRtcServer` UDP 端口，由 mediasoup 按 ICE ufrag / SSRC 解复用。
- 备选：单个 transport 同时收发，mediasoup-client 支持不理想，复杂度更高。

### Voice WebSocket 作为唯一实时信令通道

- 频道加入/离开、RTP 能力、transport connect、produce、consumer resume、mic.state、speaking 都走 `/ws/projects/:id/voice`。
- 频道元数据 CRUD 走 HTTP。
- 使用 `ref/ack` 机制让前端等待服务端处理完成。
- 备选：全 HTTP 轮询不适合 SDP/ICE 实时双向交换。

### 前端使用 `VoiceService` 抽象 + mediasoup-client

- `VoiceService` 隔离 WebRTC 细节；`WebRTCVoiceService` 基于 mediasoup-client。
- 远端音频通过 `RemoteVoiceAudio` 常驻播放，不依赖设置面板打开。
- 备选：手动实现 WebRTC offer/answer，工作量大且易错。

### VAD 与静音阈值采用客户端 RMS 检测

- 每 200ms 计算 `AnalyserNode` 时域 RMS。
- `RMS > threshold` 判定说话并恢复 producer；否则暂停 producer 并广播 speaking=false。
- 备选：服务端 `AudioLevelObserver` 更权威，但需要额外 observer 生命周期管理，作为后续增强。

## Risks / Trade-offs

- [客户端 VAD 准确度有限] → 静音阈值可调；后续可迁移 mediasoup `AudioLevelObserver`。
- [单 UDP 端口被占用或 NAT 不可达] → 通过 `VOICE_MEDIA_LISTEN_IP` / `VOICE_MEDIA_ANNOUNCED_ADDRESS` 显式配置；本机默认自动选择局域网 IP。
- [多个 worker/实例时端口冲突] → 每个 worker 需要独立 `WebRtcServer` 端口，当前单 worker 部署。
- [mediasoup 原生依赖] → 已配置 pnpm `allowBuilds`，Windows/Linux 构建脚本需保持可用。

## Migration Plan

1. 已完成的实现保持兼容：新增 `voice_channels` 表迁移，不影响现有表。
2. 启动时主动初始化 mediasoup，暴露配置/端口问题。
3. 回滚策略：前端禁用语音入口、后端不挂载 voice 路由即可回退，不影响实体编辑。
