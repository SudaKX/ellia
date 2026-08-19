## Purpose

Provides real-time voice communication for project editors, including persistent channels, WebRTC media relay, audio settings, and speaker presence.

## ADDED Requirements

### Requirement: Voice channel metadata is persisted per project

The system SHALL persist voice channel metadata in SQLite, scoped to a project, with a unique channel name per project and a maximum participant capacity.

#### Scenario: Create a channel

- **WHEN** an authenticated user creates a channel named `大厅` in a project
- **THEN** the channel is stored and appears in the project channel list with capacity 8 and participant count 0

#### Scenario: Duplicate channel name is rejected

- **WHEN** a user creates a second channel with the same name in the same project
- **THEN** the system rejects the request with a conflict error

### Requirement: Voice channels enforce capacity

The system SHALL enforce that no more than the channel capacity users are simultaneously connected to a voice channel.

#### Scenario: Channel is full

- **WHEN** a user attempts to join a channel whose participant count equals its capacity
- **THEN** the join is rejected with a channel full error

#### Scenario: A user leaves a full channel

- **WHEN** a participant leaves a full channel
- **THEN** the participant count decreases and a waiting user can join

### Requirement: Voice signaling is available over WebSocket

The system SHALL provide a project-scoped voice WebSocket endpoint for joining/leaving channels, RTP capability exchange, WebRTC transport setup, producer/consumer control, mute state, and speaking state.

#### Scenario: Join channel and publish audio

- **WHEN** a connected client sends a join channel request
- **THEN** the server creates WebRTC transports, sends transport parameters and router RTP capabilities, and later accepts the client's audio producer

#### Scenario: Receive remote audio

- **WHEN** a second participant publishes audio in the same channel
- **THEN** the first participant receives a consumer created notification and can play the remote audio

### Requirement: Voice media is relayed through the server

The system SHALL relay audio between participants through a server-side SFU using WebRTC over UDP, rather than direct peer-to-peer connections.

#### Scenario: Two users in same channel hear each other

- **WHEN** two users are in the same voice channel and both have audio producers
- **THEN** each user receives the other user's audio through the server relay

### Requirement: Remote audio plays while the project editor is open

The system SHALL keep remote voice audio playing for the duration of the project editor session, regardless of whether the voice settings panel is open.

#### Scenario: Audio continues with settings closed

- **WHEN** a user closes the voice settings panel while in a channel
- **THEN** remote participant audio continues to play

### Requirement: Audio settings are user-adjustable

The system SHALL allow users to toggle browser noise suppression, adjust microphone gain, adjust speaker gain, and configure a silence threshold used for voice activity detection.

#### Scenario: Adjust microphone gain

- **WHEN** a user changes microphone gain to 150%
- **THEN** the audio sent to peers is amplified by the configured gain

#### Scenario: Silence threshold pauses sending

- **WHEN** the local audio RMS falls below the configured silence threshold
- **THEN** the client pauses its audio producer and notifies the server that the user is not speaking

### Requirement: Speaker presence is broadcast to channel members

The system SHALL broadcast speaking state changes to all members of the current voice channel and display speaking state in the UI.

#### Scenario: Speaking state change

- **WHEN** a participant's voice activity changes from silent to speaking
- **THEN** all channel members receive a speaker event with the participant's user id and speaking state

#### Scenario: Muted user does not appear speaking

- **WHEN** a participant is manually muted
- **THEN** the participant is not reported as speaking and their audio producer remains paused
