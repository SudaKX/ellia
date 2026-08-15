import { jsonBody, request } from './client'
import type { AuthResponse, LoginInput, RegisterInput } from './types'

export function me(): Promise<AuthResponse> {
  return request<AuthResponse>('/api/auth/me')
}

export function login(input: LoginInput): Promise<AuthResponse> {
  return request<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: jsonBody(input),
  })
}

export function register(input: RegisterInput): Promise<AuthResponse> {
  return request<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: jsonBody(input),
  })
}

export function logout(): Promise<void> {
  return request<void>('/api/auth/logout', { method: 'POST' })
}
