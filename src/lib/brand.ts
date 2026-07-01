export const originalBrandName = 'Тамбур'
export const internationalBrandName = 'Tambur'

export const brandNameForLanguage = (language?: string | null): string => {
  const normalized = String(language || 'ru').trim().toLowerCase()
  return normalized === 'ru' || normalized.startsWith('ru-')
    ? originalBrandName
    : internationalBrandName
}
