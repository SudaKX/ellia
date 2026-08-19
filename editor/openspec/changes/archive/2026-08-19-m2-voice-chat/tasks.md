## 1. Dependencies and Configuration

- [x] 1.1 Install mediasoup in server package
- [x] 1.2 Install mediasoup-client in web package
- [x] 1.3 Remove werift dependency
- [x] 1.4 Add VOICE_MEDIA_LISTEN_IP / VOICE_MEDIA_ANNOUNCED_ADDRESS / VOICE_MEDIA_PORT configuration

## 2. Shared Types and Persistence

- [x] 2.1 Add voice shared types in puzzle-schema
- [x] 2.2 Add voice_channels table migration
- [x] 2.3 Add voice channel metadata service

## 3. Backend Mediasoup Service

- [x] 3.1 Implement MediasoupService with Worker and WebRtcServer
- [x] 3.2 Create per-project Router with Opus codec
- [x] 3.3 Implement transport/produce/consume/resume/pause operations
- [x] 3.4 Handle worker died reset and auto-recovery
- [x] 3.5 Add transport/producer/consumer close cleanup

## 4. Voice Manager and Signaling

- [x] 4.1 Implement VoiceManager channel/participant state
- [x] 4.2 Implement join/leave channel flow
- [x] 4.3 Implement rtp.capabilities / transport.connect / produce / consumer.resume messages
- [x] 4.4 Implement mic.state and speaking broadcast
- [x] 4.5 Implement consumer.created/closed and producer.closed notifications
- [x] 4.6 Add voice WebSocket endpoint with authentication

## 5. HTTP Channel Management

- [x] 5.1 Add GET/POST/DELETE voice channels routes
- [x] 5.2 Mount voice router with mergeParams
- [x] 5.3 Add voice API tests

## 6. Frontend Voice Service

- [x] 6.1 Implement VoiceService abstraction and WebRTCVoiceService
- [x] 6.2 Implement channel list/create/delete and join/leave
- [x] 6.3 Implement remote audio track events and playback host
- [x] 6.4 Implement mic gain, speaker gain, noise suppression, silence threshold
- [x] 6.5 Implement local VAD and auto-pause/resume producer

## 7. Voice UI

- [x] 7.1 Add voice settings overlay
- [x] 7.2 Add persistent voice audio host
- [x] 7.3 Add speaker overlay
- [x] 7.4 Add entity browser menu entry
- [x] 7.5 Add voice channel state to entity browser footer

## 8. Verification

- [x] 8.1 Run server type-check and tests
- [x] 8.2 Run web type-check and build
- [x] 8.3 Manual dual-browser voice test
