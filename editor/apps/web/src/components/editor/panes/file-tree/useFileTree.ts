import type { FileTreeNode, FileTreeState } from '@ellia/puzzle-schema'

export function defaultFileTreeState(): FileTreeState {
  return {
    rootId: 'root',
    nodes: {
      root: { id: 'root', name: '/', isDirectory: true, inode: null, parent: null, order: 0 },
    },
  }
}

export function childrenOf(state: FileTreeState, parentId: string): FileTreeNode[] {
  return Object.values(state.nodes)
    .filter((node) => node.parent === parentId)
    .sort((a, b) => a.order - b.order || a.id.localeCompare(b.id))
}

export function nodePath(state: FileTreeState, nodeId: string): string {
  const segments: string[] = []
  let current = state.nodes[nodeId]
  const seen = new Set<string>()
  while (current && current.parent !== null) {
    if (seen.has(current.id)) break
    seen.add(current.id)
    segments.unshift(current.name)
    current = state.nodes[current.parent]
  }
  return segments.length === 0 ? '/' : `/${segments.join('/')}`
}

export function pathFromRoot(state: FileTreeState, nodeId: string): string[] {
  const chain: string[] = []
  let current = state.nodes[nodeId]
  const seen = new Set<string>()
  while (current) {
    if (seen.has(current.id)) break
    seen.add(current.id)
    chain.unshift(current.id)
    if (current.parent === null) break
    current = state.nodes[current.parent]
  }
  return chain
}

export function descendantIds(state: FileTreeState, nodeId: string): string[] {
  const result: string[] = []
  const visit = (id: string): void => {
    result.push(id)
    for (const child of childrenOf(state, id)) visit(child.id)
  }
  visit(nodeId)
  return result
}

export function isDirectoryNode(node: FileTreeNode | null | undefined): boolean {
  return Boolean(node?.isDirectory)
}

export function nextOrder(state: FileTreeState, parentId: string): number {
  const siblings = childrenOf(state, parentId)
  return siblings.reduce((max, node) => Math.max(max, node.order + 1), 0)
}

export function isValidTreeNodeName(name: string): boolean {
  return (
    name.length > 0 &&
    name !== '.' &&
    name !== '..' &&
    !name.includes('/') &&
    !name.includes('\\')
  )
}

export function slugifyResourceId(name: string): string {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || 'node'
}
