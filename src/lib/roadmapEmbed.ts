import {
  normalizePostLanguage,
  originalPostLanguage,
  type PostLanguageCode,
} from '$lib/postLanguages'

export type RoadmapEmbedLabels = {
  planned: string
  inProgress: string
  done: string
  cardOne: string
  cardFew?: string
  cardOther: string
  votes: string
  comments: string
  openPost: string
  openRoadmap: string
  untitled: string
  emptyPlanned: string
  emptyInProgress: string
  emptyDone: string
}

const LABELS: Record<PostLanguageCode, RoadmapEmbedLabels> = {
  ru: {
    planned: 'Дальше',
    inProgress: 'В работе',
    done: 'Готово',
    cardOne: 'карточка',
    cardFew: 'карточки',
    cardOther: 'карточек',
    votes: 'Голоса',
    comments: 'Комментарии',
    openPost: 'Открыть карточку и обсуждение',
    openRoadmap: 'Открыть дорожную карту в Tambur',
    untitled: 'Без заголовка',
    emptyPlanned: 'В планах пока нет постов.',
    emptyInProgress: 'Сейчас в работе ничего нет.',
    emptyDone: 'Завершенных задач пока нет.',
  },
  en: {
    planned: 'Next',
    inProgress: 'In progress',
    done: 'Done',
    cardOne: 'card',
    cardOther: 'cards',
    votes: 'Votes',
    comments: 'Comments',
    openPost: 'Open card and discussion',
    openRoadmap: 'Open roadmap in Tambur',
    untitled: 'Untitled',
    emptyPlanned: 'No planned posts yet.',
    emptyInProgress: 'Nothing is in progress now.',
    emptyDone: 'No completed tasks yet.',
  },
  es: {
    planned: 'Siguiente',
    inProgress: 'En curso',
    done: 'Hecho',
    cardOne: 'tarjeta',
    cardOther: 'tarjetas',
    votes: 'Votos',
    comments: 'Comentarios',
    openPost: 'Abrir tarjeta y debate',
    openRoadmap: 'Abrir la hoja de ruta en Tambur',
    untitled: 'Sin título',
    emptyPlanned: 'Aún no hay publicaciones planificadas.',
    emptyInProgress: 'No hay nada en curso.',
    emptyDone: 'Aún no hay tareas completadas.',
  },
  pt: {
    planned: 'Próximo',
    inProgress: 'Em andamento',
    done: 'Concluído',
    cardOne: 'cartão',
    cardOther: 'cartões',
    votes: 'Votos',
    comments: 'Comentários',
    openPost: 'Abrir cartão e discussão',
    openRoadmap: 'Abrir roteiro no Tambur',
    untitled: 'Sem título',
    emptyPlanned: 'Ainda não há posts planejados.',
    emptyInProgress: 'Nada está em andamento agora.',
    emptyDone: 'Ainda não há tarefas concluídas.',
  },
  de: {
    planned: 'Als Nächstes',
    inProgress: 'In Arbeit',
    done: 'Erledigt',
    cardOne: 'Karte',
    cardOther: 'Karten',
    votes: 'Stimmen',
    comments: 'Kommentare',
    openPost: 'Karte und Diskussion öffnen',
    openRoadmap: 'Roadmap in Tambur öffnen',
    untitled: 'Ohne Titel',
    emptyPlanned: 'Noch keine geplanten Beiträge.',
    emptyInProgress: 'Derzeit ist nichts in Arbeit.',
    emptyDone: 'Noch keine abgeschlossenen Aufgaben.',
  },
  fr: {
    planned: 'Ensuite',
    inProgress: 'En cours',
    done: 'Terminé',
    cardOne: 'carte',
    cardOther: 'cartes',
    votes: 'Votes',
    comments: 'Commentaires',
    openPost: 'Ouvrir la carte et la discussion',
    openRoadmap: 'Ouvrir la feuille de route dans Tambur',
    untitled: 'Sans titre',
    emptyPlanned: 'Aucune publication planifiée.',
    emptyInProgress: 'Rien n’est en cours actuellement.',
    emptyDone: 'Aucune tâche terminée.',
  },
  tr: {
    planned: 'Sıradaki',
    inProgress: 'Devam ediyor',
    done: 'Tamamlandı',
    cardOne: 'kart',
    cardOther: 'kart',
    votes: 'Oylar',
    comments: 'Yorumlar',
    openPost: 'Kartı ve tartışmayı aç',
    openRoadmap: 'Yol haritasını Tambur’da aç',
    untitled: 'Başlıksız',
    emptyPlanned: 'Henüz planlanmış gönderi yok.',
    emptyInProgress: 'Şu anda devam eden bir şey yok.',
    emptyDone: 'Henüz tamamlanmış görev yok.',
  },
  id: {
    planned: 'Berikutnya',
    inProgress: 'Sedang dikerjakan',
    done: 'Selesai',
    cardOne: 'kartu',
    cardOther: 'kartu',
    votes: 'Suara',
    comments: 'Komentar',
    openPost: 'Buka kartu dan diskusi',
    openRoadmap: 'Buka peta jalan di Tambur',
    untitled: 'Tanpa judul',
    emptyPlanned: 'Belum ada postingan yang direncanakan.',
    emptyInProgress: 'Tidak ada yang sedang dikerjakan.',
    emptyDone: 'Belum ada tugas yang selesai.',
  },
}

const escapeAttribute = (value: string): string =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')

export const roadmapEmbedLabels = (
  language: string | null | undefined
): RoadmapEmbedLabels => LABELS[normalizePostLanguage(language)]

export const roadmapEmbedCardLabel = (
  language: string | null | undefined,
  count: number
): string => {
  const normalizedLanguage = normalizePostLanguage(language)
  const labels = LABELS[normalizedLanguage]
  const pluralCategory = new Intl.PluralRules(normalizedLanguage).select(count)
  if (pluralCategory === 'one') return labels.cardOne
  if (pluralCategory === 'few' && labels.cardFew) return labels.cardFew
  return labels.cardOther
}

export const buildComunRoadmapEmbedPath = (
  slug: string,
  language: string | null | undefined = originalPostLanguage
): string => {
  const normalizedLanguage = normalizePostLanguage(language)
  const path = `/embed/roadmap/${encodeURIComponent(slug)}`
  return normalizedLanguage === originalPostLanguage
    ? path
    : `/${normalizedLanguage}${path}`
}

export const buildComunRoadmapPagePath = (
  slug: string,
  language: string | null | undefined = originalPostLanguage
): string => {
  const normalizedLanguage = normalizePostLanguage(language)
  const path = `/comuns/${encodeURIComponent(slug)}/roadmap`
  return normalizedLanguage === originalPostLanguage
    ? path
    : `/${normalizedLanguage}${path}`
}

export const buildComunRoadmapEmbedCode = ({
  baseUrl,
  slug,
  language,
  communityName,
}: {
  baseUrl: string
  slug: string
  language?: string | null
  communityName: string
}): string => {
  const src = `${baseUrl.replace(/\/+$/, '')}${buildComunRoadmapEmbedPath(slug, language)}`
  const title = `Roadmap — ${communityName.trim() || 'Tambur'}`
  return `<iframe src="${escapeAttribute(src)}" title="${escapeAttribute(title)}" width="100%" height="720" style="border:0;border-radius:12px;" loading="lazy"></iframe>`
}
