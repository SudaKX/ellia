import dagre from '@dagrejs/dagre'
import type { DagNode, DagState, EntityRecord } from '@ellia/puzzle-schema'

export const DAG_NODE_WIDTH = 144
export const DAG_NODE_HEIGHT = 56
const PADDING = 20
const NODE_GAP = 14
const RANK_SEP = 64
const NODE_SEP = 36
const ISOLATED_GAP = 28

export interface DagLayoutNode {
  id: string
  node: DagNode
  entity: EntityRecord | null
  name: string
  resourceId: string | null
  label: string
  isEntry: boolean
  isMissing: boolean
  isIsolated: boolean
  x: number
  y: number
}

export interface DagLayoutEdge {
  id: string
  from: string
  to: string
  points: Array<{ x: number; y: number }>
}

export interface DagLayout {
  nodes: DagLayoutNode[]
  edges: DagLayoutEdge[]
  isolatedNodes: DagLayoutNode[]
  width: number
  height: number
  isEmpty: boolean
}

export function buildDagLayout(
  state: DagState,
  entities: Record<string, EntityRecord>,
): DagLayout {
  const nodesById = new Map<string, DagLayoutNode>()
  const entrySet = new Set(state.entryIds)

  for (const node of Object.values(state.nodes)) {
    const entity = node.pnode ? (entities[node.pnode] ?? null) : null
    nodesById.set(node.id, {
      id: node.id,
      node,
      entity,
      name: node.name,
      resourceId: entity?.resource_id ?? null,
      label: node.name,
      isEntry: entrySet.has(node.id),
      isMissing: Boolean(node.pnode) && !entity,
      isIsolated: false,
      x: 0,
      y: 0,
    })
  }

  const rawEdges: Array<{ from: string; to: string }> = []
  for (const layoutNode of nodesById.values()) {
    for (const successorId of layoutNode.node.successors) {
      if (successorId !== layoutNode.id && nodesById.has(successorId)) {
        rawEdges.push({ from: layoutNode.id, to: successorId })
      }
    }
  }

  const incident = new Set<string>()
  for (const edge of rawEdges) {
    incident.add(edge.from)
    incident.add(edge.to)
  }

  const allNodes = [...nodesById.values()]
  for (const node of allNodes) {
    node.isIsolated = !incident.has(node.id)
  }

  const connectedNodes = allNodes.filter((node) => !node.isIsolated)
  const isolatedNodes = allNodes.filter((node) => node.isIsolated)
  const edges: DagLayoutEdge[] = []

  let mainWidth = 0
  let mainHeight = 0
  const positioned: DagLayoutNode[] = []

  if (connectedNodes.length > 0) {
    const graph = new dagre.graphlib.Graph()
    graph.setGraph({
      rankdir: 'LR',
      nodesep: NODE_SEP,
      ranksep: RANK_SEP,
      marginx: PADDING,
      marginy: PADDING,
      acyclicer: 'greedy',
    })
    graph.setDefaultEdgeLabel(() => ({}))

    for (const node of connectedNodes) {
      graph.setNode(node.id, {
        width: DAG_NODE_WIDTH,
        height: DAG_NODE_HEIGHT,
      })
    }
    for (const edge of rawEdges) {
      graph.setEdge(edge.from, edge.to)
    }

    dagre.layout(graph)

    for (const node of connectedNodes) {
      const label = graph.node(node.id)
      positioned.push({
        ...node,
        x: label.x,
        y: label.y,
      })
    }

    for (const edge of rawEdges) {
      const label = graph.edge(edge.from, edge.to)
      edges.push({
        id: `${edge.from}->${edge.to}`,
        from: edge.from,
        to: edge.to,
        points: label?.points ?? [],
      })
    }

    const graphSize = graph.graph()
    mainWidth = graphSize.width ?? 0
    mainHeight = graphSize.height ?? 0
  }

  const isolatedRowWidth =
    isolatedNodes.length > 0
      ? isolatedNodes.length * (DAG_NODE_WIDTH + NODE_GAP) - NODE_GAP + PADDING * 2
      : 0

  const width = Math.max(mainWidth, isolatedRowWidth)
  let height = mainHeight
  let isolatedTop = 0

  if (isolatedNodes.length > 0) {
    isolatedTop = mainHeight > 0 ? mainHeight + ISOLATED_GAP : PADDING
    height = isolatedTop + DAG_NODE_HEIGHT + PADDING

    const rowTotal = isolatedNodes.length * (DAG_NODE_WIDTH + NODE_GAP) - NODE_GAP
    const startX = (width - rowTotal) / 2 + DAG_NODE_WIDTH / 2
    isolatedNodes.forEach((node, index) => {
      positioned.push({
        ...node,
        x: startX + index * (DAG_NODE_WIDTH + NODE_GAP),
        y: isolatedTop + DAG_NODE_HEIGHT / 2,
      })
    })
  }

  return {
    nodes: positioned,
    edges,
    isolatedNodes,
    width,
    height,
    isEmpty: allNodes.length === 0,
  }
}
