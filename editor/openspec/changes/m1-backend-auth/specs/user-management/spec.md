## Purpose

Provides user registration, login sessions, one-time invite codes, initial admin bootstrap, and admin user management for the editor server.

## ADDED Requirements

### Requirement: Initial admin bootstrap

On first startup, the system SHALL create an initial admin user from the configured
`ADMIN_USERNAME` and `ADMIN_PASSWORD` when no admin user exists yet. The system SHALL
not create a second initial admin when at least one admin already exists. If the
configured password is the built-in insecure default, the system SHALL log a
security warning at startup.

#### Scenario: First startup with configured credentials

- **WHEN** the server starts with an empty database and configured `ADMIN_USERNAME=root` and `ADMIN_PASSWORD=secret`
- **THEN** a user `root` with role `admin` exists and can log in with `secret`

#### Scenario: Restart with existing admin

- **WHEN** the server restarts and at least one admin already exists
- **THEN** no additional admin is created from the environment credentials

### Requirement: User registration with one-time invite code

The system SHALL register a new user only when a valid, unused, and unexpired invite
code is supplied. Registration SHALL consume the invite code so it cannot be reused.
Username SHALL be unique. On success the system SHALL create an authenticated
session for the new user and return the user object.

#### Scenario: Successful registration

- **WHEN** a visitor submits a username, password, and a valid unused invite code
- **THEN** a `user`-role account is created, the invite code is marked used, and the response establishes an authenticated session and returns the user

#### Scenario: Reused invite code

- **WHEN** a second visitor submits an invite code that was already used
- **THEN** the system returns 400 and creates no account

#### Scenario: Expired invite code

- **WHEN** a visitor submits an invite code whose expiry time has passed
- **THEN** the system returns 400 and creates no account

#### Scenario: Duplicate username

- **WHEN** a visitor registers with a username that already exists
- **THEN** the system returns 409 and creates no account

### Requirement: Login and logout

The system SHALL authenticate a user by username and password. A successful login
SHALL create an authenticated session; a failed login SHALL return 401 without
revealing whether the username exists. Logout SHALL invalidate the current session.

#### Scenario: Successful login

- **WHEN** a user submits the correct username and password
- **THEN** the response establishes an authenticated session and returns the user

#### Scenario: Wrong password

- **WHEN** a user submits an existing username with a wrong password
- **THEN** the system returns 401 and establishes no session

#### Scenario: Logout

- **WHEN** an authenticated user logs out
- **THEN** the server invalidates the session and subsequent `me` requests return 401

### Requirement: Current user lookup

The system SHALL return the authenticated user for the session cookie on `GET /api/auth/me`
and SHALL return 401 when the session is missing, unknown, or expired.

#### Scenario: Authenticated me

- **WHEN** a request with a valid session cookie calls `GET /api/auth/me`
- **THEN** the response returns `{ user: { id, username, role } }` with status 200

#### Scenario: Anonymous me

- **WHEN** a request without a valid session cookie calls `GET /api/auth/me`
- **THEN** the response returns 401

### Requirement: Admin-only invite code generation

Only admin users SHALL create invite codes. Each code SHALL be unique, have an
expiry time derived from the requested lifetime, and be usable exactly once.

#### Scenario: Admin creates invite

- **WHEN** an admin submits a positive lifetime in seconds
- **THEN** the system returns a new invite code and its expiry time

#### Scenario: Non-admin cannot create invite

- **WHEN** a `user`-role account attempts to create an invite code
- **THEN** the system returns 403 and creates nothing

#### Scenario: Anonymous cannot create invite

- **WHEN** an unauthenticated request attempts to create an invite code
- **THEN** the system returns 401 and creates nothing

### Requirement: Invite code listing

The system SHALL list all invite codes for admin users, including creator, expiry,
used-by, used-at, and a computed status of `unused`, `used`, or `expired`.

#### Scenario: Admin lists invites

- **WHEN** an admin requests the invite list
- **THEN** the response contains every invite code with its current status

#### Scenario: Non-admin cannot list invites

- **WHEN** a non-admin authenticated user requests the invite list
- **THEN** the system returns 403

### Requirement: Invite code revocation

An admin SHALL be able to revoke an invite code so it can no longer be used for
registration, even before its expiry time.

#### Scenario: Revoke unused invite

- **WHEN** an admin revokes an existing unused invite code
- **THEN** the code is removed and registration with it returns 400

#### Scenario: Revoke unknown invite

- **WHEN** an admin revokes a code that does not exist
- **THEN** the system returns 404

### Requirement: Admin-only user listing and promotion

The system SHALL allow admin users to list all users and to promote a `user`-role
account to `admin`. Promotion SHALL be idempotent for users who are already admin.

#### Scenario: Admin lists users

- **WHEN** an admin requests the user list
- **THEN** the response contains every user with id, username, role, and creation time

#### Scenario: Admin promotes user

- **WHEN** an admin promotes a `user`-role account
- **THEN** the account becomes `admin` and the updated user is returned

#### Scenario: Promote already-admin user

- **WHEN** an admin promotes an account that already has role `admin`
- **THEN** the system returns 200 with the unchanged admin user

#### Scenario: Non-admin cannot list users or promote

- **WHEN** a non-admin account requests the user list or a promotion
- **THEN** the system returns 403

### Requirement: Password storage security

The system SHALL store passwords only as salted cryptographic hashes and SHALL
verify them in constant time. The system SHALL NOT return password material in
any API response or log it.

#### Scenario: No password material leaks

- **WHEN** any user-related API response or server log is inspected
- **THEN** no plaintext password or password hash appears

### Requirement: Uniform API error shape

All failed requests from these APIs SHALL return a JSON body of the form
`{ "error": { "code": string, "message": string } }` with an appropriate
4xx/5xx HTTP status.

#### Scenario: Validation failure shape

- **WHEN** a register request omits the invite code
- **THEN** the response has status 400 and a body with `error.code` and `error.message`
