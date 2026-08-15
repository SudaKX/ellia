import { randomBytes, scrypt, timingSafeEqual } from 'node:crypto'

const SCRYPT_N = 16384
const SCRYPT_R = 8
const SCRYPT_P = 1
const SCRYPT_KEY_LENGTH = 64
const SALT_LENGTH = 16
const PREFIX = `scrypt:${SCRYPT_N}:${SCRYPT_R}:${SCRYPT_P}`

function scryptAsync(password: string, salt: Buffer, keyLength: number): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password, salt, keyLength, { N: SCRYPT_N, r: SCRYPT_R, p: SCRYPT_P }, (error, derived) => {
      if (error) reject(error)
      else resolve(derived)
    })
  })
}

export async function hashPassword(password: string): Promise<string> {
  const salt = randomBytes(SALT_LENGTH)
  const derived = await scryptAsync(password, salt, SCRYPT_KEY_LENGTH)
  return `${PREFIX}:${salt.toString('hex')}:${derived.toString('hex')}`
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const marker = `${PREFIX}:`
  if (!stored.startsWith(marker)) return false
  const [saltHex, hashHex, ...rest] = stored.slice(marker.length).split(':')
  if (!saltHex || !hashHex || rest.length > 0) return false

  const salt = Buffer.from(saltHex, 'hex')
  const expected = Buffer.from(hashHex, 'hex')
  if (salt.length === 0 || expected.length !== SCRYPT_KEY_LENGTH) return false

  const actual = await scryptAsync(password, salt, expected.length)
  return actual.length === expected.length && timingSafeEqual(actual, expected)
}
