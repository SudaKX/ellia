export type UserRole = 'user' | 'admin'

export interface AuthUser {
  id: string
  username: string
  role: UserRole
  created_at: string
}

export interface LoginInput {
  username: string
  password: string
}

export interface RegisterInput {
  username: string
  password: string
  invite_code: string
}

export interface InviteStatus {
  status: 'unused' | 'used' | 'expired'
}

export interface InviteCode {
  code: string
  created_by: string
  expires_at: string
  used_by: string | null
  used_at: string | null
  status: InviteStatus['status']
}

export interface CreateInviteResult {
  code: string
  expires_at: string
}

export interface AuthResponse {
  user: AuthUser
}

export interface InviteListResponse {
  invites: InviteCode[]
}

export interface UserListResponse {
  users: AuthUser[]
}

export interface PromoteResponse {
  user: AuthUser
}
