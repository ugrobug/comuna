export const toLocalDateTime = (value: string | null | undefined): string => {
  if (!value) return ''
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return ''
  const pad = (part: number) => String(part).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export const scheduleError = (value: string | null | undefined): string => {
  if (!value) return ''
  const timestamp = new Date(value).getTime()
  return !Number.isFinite(timestamp) || timestamp <= Date.now()
    ? 'Дата публикации должна быть в будущем.'
    : ''
}

export const formatPublishAt = (value: string): string =>
  new Intl.DateTimeFormat('ru', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
