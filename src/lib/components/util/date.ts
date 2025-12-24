const hasTimezoneOffset = (value: string): boolean => /[+-]\d{2}:\d{2}$/.test(value)

export const publishedToDate = (published: string): Date => {
  if (!published) {
    return new Date('')
  }
  return published.endsWith('Z') || hasTimezoneOffset(published)
    ? new Date(published)
    : new Date(`${published}Z`)
}
