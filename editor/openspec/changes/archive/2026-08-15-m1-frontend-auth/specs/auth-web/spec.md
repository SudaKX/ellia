## Purpose

Provides the browser-accessible authentication interface for the editor: login, invite-code registration, route protection, session state, and an admin panel for invites and promotions.

## ADDED Requirements

### Requirement: Login page

The system SHALL provide a `/login` page with username and password fields. A
successful login SHALL redirect the visitor to `/`; a failed login SHALL keep the
visitor on the page and show a visible error message.

#### Scenario: Successful login redirects home

- **WHEN** a visitor submits valid credentials on `/login`
- **THEN** the application establishes the session and navigates to `/`

#### Scenario: Failed login shows error

- **WHEN** a visitor submits wrong credentials
- **THEN** the page displays an error message and the visitor stays on `/login`

### Requirement: Registration page with invite code

The system SHALL provide a `/register` page with username, password, and invite
code fields. Successful registration SHALL establish the session and redirect to
`/`. Invalid or reused invite codes SHALL produce a visible error without
navigating away.

#### Scenario: Successful registration

- **WHEN** a visitor submits a valid unused invite code with a new username and password
- **THEN** the session is established and the application navigates to `/`

#### Scenario: Invalid invite code

- **WHEN** a visitor submits an unknown, used, or expired invite code
- **THEN** the page shows the server-provided error and stays on `/register`

### Requirement: Session restore on load

On application start, the system SHALL query the current user with the session
cookie and make the result available to the UI before deciding which route is
allowed.

#### Scenario: Returning authenticated user

- **WHEN** an authenticated visitor opens the application
- **THEN** the UI shows the current username and grants access to protected routes without a login prompt

#### Scenario: Anonymous visitor

- **WHEN** a visitor without a session opens a protected route
- **THEN** the application redirects to `/login`

### Requirement: Route protection

The system SHALL redirect anonymous visitors away from protected routes to
`/login`, redirect authenticated visitors away from `/login` and `/register` to
`/`, and redirect non-admin authenticated users away from `/admin` to `/`.

#### Scenario: Anonymous visits home

- **WHEN** an anonymous visitor opens `/`
- **THEN** the application redirects to `/login`

#### Scenario: Authenticated user visits login

- **WHEN** an authenticated user opens `/login`
- **THEN** the application redirects to `/`

#### Scenario: Non-admin visits admin panel

- **WHEN** a `user`-role account opens `/admin`
- **THEN** the application redirects to `/`

### Requirement: Admin invite management panel

The `/admin` page SHALL provide controls for an admin to generate an invite code
with a chosen lifetime, view all invite codes with their status, copy a code, and
revoke a code.

#### Scenario: Generate invite

- **WHEN** an admin chooses a lifetime and submits the invite form
- **THEN** the new code appears in the invite list with its expiry time

#### Scenario: Revoke invite

- **WHEN** an admin revokes an invite code
- **THEN** the code disappears from the list and can no longer be used to register

### Requirement: Admin user promotion panel

The `/admin` page SHALL list all users with their role and provide a promotion
action for `user`-role accounts. After a successful promotion, the list SHALL
reflect the new role.

#### Scenario: Promote a user

- **WHEN** an admin triggers promotion for a `user`-role account
- **THEN** the account's role changes to `admin` in the user list

### Requirement: Logout control

The application SHALL provide a logout control visible to authenticated users.
Logout SHALL clear the session and return the visitor to `/login`.

#### Scenario: Logout from any protected page

- **WHEN** an authenticated user activates logout
- **THEN** the server session is invalidated, the UI clears the current user, and the application navigates to `/login`

### Requirement: Material 3 visual tokens

The application SHALL use Material 3 design styling, and all color values used by
views, forms, navigation, and feedback elements SHALL be consumed from CSS
custom-property color tokens defined in a single token stylesheet that contains
both light and dark token sets.

#### Scenario: Theme recolor from one place

- **WHEN** a developer changes a `--md-sys-color-*` token value in the token stylesheet
- **THEN** every component using that token reflects the new color without component-level edits

### Requirement: Light and dark theme switching

The application SHALL provide a theme control that switches between light and
dark themes, SHALL persist the chosen preference in the browser, and SHALL
restore it on the next visit. Without a saved preference, the application SHALL
follow the operating system's color-scheme preference.

#### Scenario: Toggle to dark theme

- **WHEN** a visitor activates the theme control and chooses dark
- **THEN** the entire interface switches to the dark token set and the choice survives a page reload

#### Scenario: First visit follows system preference

- **WHEN** a visitor with no saved theme preference opens the application
- **THEN** the initial theme matches the operating system's light/dark preference

### Requirement: Loading and error feedback

All authentication-related actions SHALL disable duplicate submission while in
progress and SHALL surface server error messages in the page language-visible
text near the relevant form.

#### Scenario: Duplicate submission prevented

- **WHEN** a visitor submits a login or registration form while a request is in progress
- **THEN** the submit control is disabled until the request completes
