import type { ApiFileRecord, FileListResponse } from '@ellia/puzzle-schema'

import { request } from '../http'

export function listFiles(): Promise<FileListResponse> {
  return request<FileListResponse>('/api/files')
}

export function uploadFile(
  bytes: Blob,
  mediaType: string,
  originalName?: string,
): Promise<ApiFileRecord> {
  const headers = new Headers()
  headers.set('content-type', mediaType)
  if (originalName) {
    if (isLatin1(originalName)) {
      headers.set('x-original-name', originalName)
    } else {
      headers.set('x-original-name-base64', base64EncodeUtf8(originalName))
    }
  }
  return request<ApiFileRecord>('/api/files', {
    method: 'POST',
    headers,
    body: bytes,
  })
}

function isLatin1(value: string): boolean {
  return /^[\x00-\xFF]*$/.test(value)
}

function base64EncodeUtf8(value: string): string {
  const bytes = new TextEncoder().encode(value)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

export async function downloadFile(fileId: string): Promise<Blob> {
  const response = await fetch(`/api/files/${encodeURIComponent(fileId)}`, {
    credentials: 'include',
  })
  if (!response.ok) {
    const text = await response.text()
    let code = 'UNKNOWN'
    try {
      code = (JSON.parse(text) as { error?: { code?: string } }).error?.code ?? 'UNKNOWN'
    } catch {
      // ignore parse error
    }
    throw new Error(`下载失败（${response.status} ${code}）`)
  }
  return response.blob()
}

export function deleteFile(fileId: string): Promise<void> {
  return request<void>(`/api/files/${encodeURIComponent(fileId)}`, {
    method: 'DELETE',
  })
}