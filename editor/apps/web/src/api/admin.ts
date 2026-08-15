import { jsonBody, request } from './client'
import type {
  CreateInviteResult,
  InviteListResponse,
  PromoteResponse,
  UserListResponse,
} from './types'

export function createInvite(expiresInSeconds: number): Promise<CreateInviteResult> {
  return request<CreateInviteResult>('/api/admin/invites', {
    method: 'POST',
    body: jsonBody({ expires_in_seconds: expiresInSeconds }),
  })
}

export function listInvites(): Promise<InviteListResponse> {
  return request<InviteListResponse>('/api/admin/invites')
}

export function revokeInvite(code: string): Promise<void> {
  return request<void>(`/api/admin/invites/${encodeURIComponent(code)}`, { method: 'DELETE' })
}

export function listUsers(): Promise<UserListResponse> {
  return request<UserListResponse>('/api/admin/users')
}

export function promoteUser(id: string): Promise<PromoteResponse> {
  return request<PromoteResponse>(`/api/admin/users/${encodeURIComponent(id)}/promote`, {
    method: 'POST',
  })
}
