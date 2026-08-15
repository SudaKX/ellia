export const USERNAME_RE = /^[A-Za-z0-9_-]{3,32}$/

export const MIN_PASSWORD_LENGTH = 8
export const MAX_PASSWORD_LENGTH = 128

export const DEFAULT_INVITE_TTL_SECONDS = 7 * 24 * 60 * 60
export const MIN_INVITE_TTL_SECONDS = 60
export const MAX_INVITE_TTL_SECONDS = 30 * 24 * 60 * 60

export function isValidUsername(value: string): boolean {
  return USERNAME_RE.test(value)
}

export function isValidPassword(value: string): boolean {
  return value.length >= MIN_PASSWORD_LENGTH && value.length <= MAX_PASSWORD_LENGTH
}

export function parseInviteTtlSeconds(value: unknown): number | undefined {
  if (value === undefined) return DEFAULT_INVITE_TTL_SECONDS
  if (typeof value !== 'number' || !Number.isInteger(value)) return undefined
  if (value < MIN_INVITE_TTL_SECONDS || value > MAX_INVITE_TTL_SECONDS) return undefined
  return value
}
