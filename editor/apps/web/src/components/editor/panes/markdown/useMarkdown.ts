import type { MarkdownSegment, MarkdownState } from '@ellia/puzzle-schema'

export function sortedSegments(state: MarkdownState): MarkdownSegment[] {
  return state.sort
    .map((id) => state.segments[id])
    .filter((segment): segment is MarkdownSegment => Boolean(segment))
}

export function moveSegmentInSort(
  sort: string[],
  segmentId: string,
  direction: -1 | 1,
): string[] | null {
  const index = sort.indexOf(segmentId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= sort.length) return null
  const current = sort[index]
  const targetValue = sort[target]
  if (current === undefined || targetValue === undefined) return null
  const next = [...sort]
  ;[next[index], next[target]] = [targetValue, current]
  return next
}
