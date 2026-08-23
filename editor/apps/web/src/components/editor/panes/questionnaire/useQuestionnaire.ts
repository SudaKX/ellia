import type { QuestionnaireQuestion, QuestionnaireState } from '@ellia/puzzle-schema'

export function sortedQuestions(state: QuestionnaireState): QuestionnaireQuestion[] {
  return state.sort
    .map((id) => state.questions[id])
    .filter((question): question is QuestionnaireQuestion => Boolean(question))
}

export function moveQuestionInSort(
  sort: string[],
  questionId: string,
  direction: -1 | 1,
): string[] | null {
  const index = sort.indexOf(questionId)
  const target = index + direction
  if (index < 0 || target < 0 || target >= sort.length) return null
  const current = sort[index]
  const targetValue = sort[target]
  if (current === undefined || targetValue === undefined) return null
  const next = [...sort]
  ;[next[index], next[target]] = [targetValue, current]
  return next
}
