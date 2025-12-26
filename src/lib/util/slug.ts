export const slugifyTitle = (title: string): string => {
  if (!title) {
    return ''
  }

  return title
    .toLowerCase()
    .replace(/[^\wа-яё]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
