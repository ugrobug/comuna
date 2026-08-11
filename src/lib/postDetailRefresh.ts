const PERSONALIZED_POST_FIELDS = [
  'is_favorite',
  'user_vote',
  'can_manage_bug_report_status',
  'bug_report_confirmation',
  'vote_poll_participations',
  'poll',
  'post_ratings',
  'post_rating',
  'comments_count',
  'likes_count',
  'views_count',
] as const

const valuesEqual = (left: unknown, right: unknown) => {
  if (Object.is(left, right)) return true
  try {
    return JSON.stringify(left) === JSON.stringify(right)
  } catch {
    return false
  }
}

export const mergePostDetailPersonalization = <T extends Record<string, any>>(
  current: T,
  incoming: Record<string, any>
): T => {
  let changed = false
  const next: Record<string, any> = { ...current }

  for (const field of PERSONALIZED_POST_FIELDS) {
    if (!(field in incoming) || valuesEqual(current[field], incoming[field])) continue
    next[field] = incoming[field]
    changed = true
  }

  for (const field of ['author', 'comun'] as const) {
    if (!incoming[field] || typeof incoming[field] !== 'object') continue
    const merged = { ...(current[field] || {}), ...incoming[field] }
    if (valuesEqual(current[field], merged)) continue
    next[field] = merged
    changed = true
  }

  return changed ? (next as T) : current
}
