<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildSpecial1001FilmsAdminFilmUrl,
    buildSpecial1001FilmsAdminFilmsUrl,
    buildSpecial1001FilmsAdminLandingImagesUrl,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'

  type FilmAnalytics = {
    delivered_count: number
    completed_count: number
    waiting_review_count: number
    avg_user_rating?: number | null
  }

  type AdminFilm = {
    id: number
    title: string
    original_title: string
    year?: number | null
    category: string
    description: string
    imdb_url: string
    imdb_rating: string
    poster_url: string
    runtime_minutes?: number | null
    director: string
    country: string
    genres: string
    sort_order: number
    is_active: boolean
    analytics: FilmAnalytics
  }

  type AdminAnalytics = {
    public_total: number
    loaded_films: number
    active_films: number
    subscriptions: {
      total: number
      active: number
      paused: number
      completed: number
    }
    entries: {
      delivered: number
      completed: number
      waiting_review: number
      commented: number
    }
    stages: {
      active_no_film: number
      active_review_required: number
      active_waiting_next: number
      paused: number
      completed: number
    }
  }

  type LandingImage = {
    id?: number | null
    slot: string
    title: string
    image_url: string
    source_url?: string
    is_active: boolean
  }

  type AdminResponse = {
    ok: boolean
    error?: string
    analytics?: AdminAnalytics
    landing_images?: LandingImage[]
    landing_image?: LandingImage
    films?: AdminFilm[]
    film?: AdminFilm
  }

  const emptyFilm = () => ({
    title: '',
    original_title: '',
    year: '',
    category: '',
    description: '',
    imdb_url: '',
    imdb_rating: '',
    poster_url: '',
    runtime_minutes: '',
    director: '',
    country: '',
    genres: '',
    sort_order: '',
    is_active: true,
  })

  let loading = true
  let saving = false
  let error = ''
  let analytics: AdminAnalytics | null = null
  let landingImages: LandingImage[] = []
  let landingDrafts: Record<string, LandingImage> = {}
  let landingFiles: Record<string, File | null> = {}
  let landingSaving: Record<string, boolean> = {}
  let films: AdminFilm[] = []
  let draft = emptyFilm()
  let editing: Record<number, AdminFilm> = {}
  let rowSaving: Record<number, boolean> = {}

  const authHeaders = (): Record<string, string> => {
    return $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}
  }

  const formatNumber = (value: number) => new Intl.NumberFormat('ru-RU').format(value || 0)

  const emptyLandingImage = (slot: string): LandingImage => ({
    id: null,
    slot,
    title: `Кадр ${slot}`,
    image_url: '',
    source_url: '',
    is_active: true,
  })

  const normalizeLandingImages = (items: LandingImage[] = []) => {
    return ['1', '2', '3'].map((slot) => items.find((item) => item.slot === slot) ?? emptyLandingImage(slot))
  }

  const syncLandingDrafts = (items: LandingImage[]) => {
    landingDrafts = Object.fromEntries(items.map((item) => [item.slot, { ...item }]))
    landingFiles = Object.fromEntries(items.map((item) => [item.slot, null]))
  }

  const stageItems = (data: AdminAnalytics) => [
    ['Всего участников', data.subscriptions.total],
    ['Активны', data.subscriptions.active],
    ['Еще без фильма', data.stages.active_no_film],
    ['Ждут оценки', data.stages.active_review_required],
    ['Ждут следующую выдачу', data.stages.active_waiting_next],
    ['На паузе', data.stages.paused],
    ['Завершили доступное', data.stages.completed],
    ['Комментариев', data.entries.commented],
  ]

  async function loadAdmin() {
    loading = true
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsAdminFilmsUrl(), {
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = (await response.json()) as AdminResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить управление фильмами')
      }
      analytics = data.analytics ?? null
      landingImages = normalizeLandingImages(data.landing_images ?? [])
      syncLandingDrafts(landingImages)
      films = data.films ?? []
      editing = {}
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить управление фильмами'
      films = []
      landingImages = normalizeLandingImages([])
      syncLandingDrafts(landingImages)
      analytics = null
    } finally {
      loading = false
    }
  }

  function normalizePayload(value: Record<string, unknown>) {
    return {
      ...value,
      year: value.year === '' || value.year == null ? null : Number(value.year),
      runtime_minutes:
        value.runtime_minutes === '' || value.runtime_minutes == null
          ? null
          : Number(value.runtime_minutes),
      sort_order: value.sort_order === '' || value.sort_order == null ? undefined : Number(value.sort_order),
      imdb_rating: value.imdb_rating === '' ? null : value.imdb_rating,
    }
  }

  async function createFilm() {
    saving = true
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsAdminFilmsUrl(), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify(normalizePayload(draft)),
      })
      const data = (await response.json()) as AdminResponse
      if (!response.ok || !data.ok || !data.film) {
        throw new Error(data.error || 'Не удалось добавить фильм')
      }
      draft = emptyFilm()
      toast({ content: 'Фильм добавлен', type: 'success' })
      await loadAdmin()
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось добавить фильм'
    } finally {
      saving = false
    }
  }

  function editFilm(film: AdminFilm) {
    editing = {
      ...editing,
      [film.id]: {
        ...film,
        analytics: { ...film.analytics },
      },
    }
  }

  async function saveFilm(filmId: number) {
    const edited = editing[filmId]
    if (!edited) return
    rowSaving = { ...rowSaving, [filmId]: true }
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsAdminFilmUrl(filmId), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify(normalizePayload(edited as unknown as Record<string, unknown>)),
      })
      const data = (await response.json()) as AdminResponse
      if (!response.ok || !data.ok || !data.film) {
        throw new Error(data.error || 'Не удалось сохранить фильм')
      }
      films = films.map((film) => (film.id === filmId ? data.film! : film))
      const nextEditing = { ...editing }
      delete nextEditing[filmId]
      editing = nextEditing
      toast({ content: 'Фильм сохранен', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить фильм'
    } finally {
      rowSaving = { ...rowSaving, [filmId]: false }
    }
  }

  async function deactivateFilm(film: AdminFilm) {
    rowSaving = { ...rowSaving, [film.id]: true }
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsAdminFilmUrl(film.id), {
        method: 'DELETE',
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = (await response.json()) as AdminResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось скрыть фильм')
      }
      films = films.map((item) => (item.id === film.id ? { ...item, is_active: false } : item))
      toast({ content: 'Фильм скрыт из выдачи', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось скрыть фильм'
    } finally {
      rowSaving = { ...rowSaving, [film.id]: false }
    }
  }

  function setLandingFile(slot: string, event: Event) {
    const input = event.currentTarget as HTMLInputElement
    const file = input.files?.[0] ?? null
    landingFiles = {
      ...landingFiles,
      [slot]: file,
    }
    if (file) {
      const draftImage = landingDrafts[slot] ?? emptyLandingImage(slot)
      landingDrafts = {
        ...landingDrafts,
        [slot]: {
          ...draftImage,
          is_active: true,
        },
      }
    }
  }

  async function saveLandingImage(slot: string) {
    const draftImage = landingDrafts[slot] ?? emptyLandingImage(slot)
    landingSaving = { ...landingSaving, [slot]: true }
    error = ''
    try {
      const file = landingFiles[slot]
      const requestInit: RequestInit = {
        method: 'POST',
        credentials: 'include',
        headers: authHeaders(),
      }
      if (file) {
        const form = new FormData()
        form.set('slot', slot)
        form.set('title', draftImage.title || `Кадр ${slot}`)
        form.set('image_url', draftImage.image_url || '')
        form.set('source_url', draftImage.source_url || '')
        form.set('is_active', draftImage.is_active ? '1' : '0')
        form.set('image', file)
        requestInit.body = form
      } else {
        requestInit.headers = {
          'Content-Type': 'application/json',
          ...authHeaders(),
        }
        requestInit.body = JSON.stringify(draftImage)
      }
      const response = await fetch(buildSpecial1001FilmsAdminLandingImagesUrl(), requestInit)
      const data = (await response.json()) as AdminResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось сохранить картинку')
      }
      landingImages = normalizeLandingImages(data.landing_images ?? [])
      syncLandingDrafts(landingImages)
      toast({ content: 'Картинка лендинга сохранена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить картинку'
    } finally {
      landingSaving = { ...landingSaving, [slot]: false }
    }
  }

  onMount(async () => {
    if (!browser) return
    const currentUser = $siteUser || (await refreshSiteUser())
    if (!currentUser) {
      goto(`/login?next=${encodeURIComponent('/s/1001-films/admin')}`)
      return
    }
    if (!currentUser.is_staff) {
      goto('/s/1001-films')
      return
    }
    await loadAdmin()
  })
</script>

<svelte:head>
  <title>Управление фильмами | 1001 фильм</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<main class="admin-page">
  <header class="page-header">
    <div>
      <a class="back-link" href="/s/1001-films">← к лендингу</a>
      <h1>1001 фильм: управление</h1>
    </div>
    <Button on:click={loadAdmin} disabled={loading}>Обновить</Button>
  </header>

  {#if error}
    <div class="notice">{error}</div>
  {/if}

  {#if loading}
    <div class="panel">Загрузка...</div>
  {:else}
    {#if analytics}
      <section class="stats-grid" aria-label="Аналитика спецпроекта">
        <article>
          <span>Загружено фильмов</span>
          <strong>{formatNumber(analytics.loaded_films)}</strong>
          <small>публичный маршрут: {formatNumber(analytics.public_total)}</small>
        </article>
        <article>
          <span>Активных фильмов</span>
          <strong>{formatNumber(analytics.active_films)}</strong>
          <small>участвуют в выдаче</small>
        </article>
        <article>
          <span>Выдано фильмов</span>
          <strong>{formatNumber(analytics.entries.delivered)}</strong>
          <small>завершено: {formatNumber(analytics.entries.completed)}</small>
        </article>
        <article>
          <span>Ждут оценки</span>
          <strong>{formatNumber(analytics.entries.waiting_review)}</strong>
          <small>следующий фильм закрыт</small>
        </article>
      </section>

      <section class="panel">
        <div class="section-heading">
          <h2>Люди по этапам</h2>
        </div>
        <div class="stage-grid">
          {#each stageItems(analytics) as item}
            <div>
              <span>{item[0]}</span>
              <strong>{formatNumber(Number(item[1]))}</strong>
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <section class="panel">
      <div class="section-heading">
        <h2>Фотки лендинга</h2>
        <span>3 правые карточки</span>
      </div>
      <div class="landing-images-grid">
        {#each landingImages as image (image.slot)}
          {@const draftImage = landingDrafts[image.slot] ?? image}
          <article>
            <div class="landing-preview">
              {#if draftImage.image_url}
                <img src={draftImage.image_url} alt={draftImage.title || `Кадр ${image.slot}`} />
              {:else}
                <span>Кадр {image.slot}</span>
              {/if}
            </div>
            <label>
              <span>Название</span>
              <input bind:value={draftImage.title} placeholder={`Кадр ${image.slot}`} />
            </label>
            <label>
              <span>URL картинки</span>
              <input bind:value={draftImage.image_url} placeholder="https://..." />
            </label>
            <label>
              <span>Загрузить файл</span>
              <input type="file" accept="image/*" on:change={(event) => setLandingFile(image.slot, event)} />
            </label>
            <label class="checkbox-row">
              <input type="checkbox" bind:checked={draftImage.is_active} />
              <span>Показывать на лендинге</span>
            </label>
            <Button
              color="primary"
              size="sm"
              disabled={landingSaving[image.slot]}
              on:click={() => saveLandingImage(image.slot)}
            >
              {landingSaving[image.slot] ? 'Сохраняю' : 'Сохранить'}
            </Button>
          </article>
        {/each}
      </div>
    </section>

    <section class="panel">
      <div class="section-heading">
        <h2>Добавить фильм</h2>
      </div>
      <form class="film-form" on:submit|preventDefault={createFilm}>
        <input bind:value={draft.title} placeholder="Название" required />
        <input bind:value={draft.original_title} placeholder="Оригинальное название" />
        <input bind:value={draft.year} type="number" min="1880" max="3000" placeholder="Год" />
        <input bind:value={draft.sort_order} type="number" min="1" placeholder="Порядок" />
        <input bind:value={draft.category} placeholder="Категория" />
        <input bind:value={draft.imdb_url} placeholder="IMDb URL" />
        <input bind:value={draft.poster_url} placeholder="Постер URL" />
        <textarea bind:value={draft.description} placeholder="Описание"></textarea>
        <Button color="primary" submit disabled={saving}>{saving ? 'Добавляю' : 'Добавить'}</Button>
      </form>
    </section>

    <section class="panel films-panel">
      <div class="section-heading">
        <h2>Список фильмов</h2>
        <span>{formatNumber(films.length)} строк</span>
      </div>
      <div class="films-table">
        {#each films as film (film.id)}
          {@const edited = editing[film.id]}
          <article class:inactive={!film.is_active}>
            <div class="film-main">
              {#if edited}
                <input bind:value={edited.sort_order} type="number" min="1" aria-label="Порядок" />
                <input bind:value={edited.title} aria-label="Название" />
                <input bind:value={edited.year} type="number" min="1880" max="3000" aria-label="Год" />
                <input bind:value={edited.imdb_url} aria-label="IMDb URL" placeholder="IMDb URL" />
              {:else}
                <strong>{film.sort_order}. {film.title}</strong>
                <span>{film.original_title || 'Без оригинального названия'}{film.year ? ` · ${film.year}` : ''}</span>
                <span>{film.category || 'Без категории'}{film.imdb_url ? ' · IMDb заполнен' : ' · IMDb пустой'}</span>
              {/if}
            </div>
            <div class="film-analytics">
              <div><span>Выдан</span><strong>{formatNumber(film.analytics.delivered_count)}</strong></div>
              <div><span>Оценен</span><strong>{formatNumber(film.analytics.completed_count)}</strong></div>
              <div><span>Ждет</span><strong>{formatNumber(film.analytics.waiting_review_count)}</strong></div>
              <div><span>Средняя</span><strong>{film.analytics.avg_user_rating ?? '-'}</strong></div>
            </div>
            <div class="row-actions">
              {#if edited}
                <Button size="sm" color="primary" disabled={rowSaving[film.id]} on:click={() => saveFilm(film.id)}>
                  Сохранить
                </Button>
                <Button size="sm" on:click={() => {
                  const nextEditing = { ...editing }
                  delete nextEditing[film.id]
                  editing = nextEditing
                }}>
                  Отмена
                </Button>
              {:else}
                <Button size="sm" on:click={() => editFilm(film)}>Править</Button>
                <Button size="sm" href={`/s/1001-films/admin/preview/${film.id}`}>
                  Предпросмотр
                </Button>
                {#if film.is_active}
                  <Button size="sm" on:click={() => deactivateFilm(film)} disabled={rowSaving[film.id]}>
                    Скрыть
                  </Button>
                {/if}
              {/if}
            </div>
          </article>
        {/each}
      </div>
    </section>
  {/if}
</main>

<style>
  .admin-page {
    width: min(1180px, 100%);
    margin: 0 auto;
    display: grid;
    gap: 16px;
    color: #0f172a;
  }

  .page-header,
  .section-heading {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
  }

  .back-link {
    color: #475569;
    font-size: 0.9rem;
  }

  h1,
  h2 {
    margin: 0;
    font-weight: 600;
    letter-spacing: 0;
  }

  h1 {
    margin-top: 0.25rem;
    font-size: clamp(1.6rem, 3vw, 2.4rem);
  }

  h2 {
    font-size: 1.2rem;
  }

  .notice,
  .panel,
  .stats-grid article {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
  }

  .notice {
    padding: 12px;
    color: #b91c1c;
  }

  .panel {
    padding: 14px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .stats-grid article,
  .stage-grid div {
    display: grid;
    gap: 4px;
    padding: 12px;
  }

  .stats-grid span,
  .stage-grid span,
  .film-analytics span,
  .section-heading span,
  small {
    color: #64748b;
    font-size: 0.82rem;
  }

  .stats-grid strong,
  .stage-grid strong {
    font-size: 1.65rem;
    font-weight: 600;
  }

  .stage-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    margin-top: 12px;
  }

  .stage-grid div {
    border-radius: 8px;
    background: #f8fafc;
  }

  .landing-images-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
    margin-top: 12px;
  }

  .landing-images-grid article {
    display: grid;
    gap: 10px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
    background: #f8fafc;
  }

  .landing-preview {
    aspect-ratio: 16 / 10;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid #cbd5e1;
    background:
      linear-gradient(90deg, rgb(15 23 42 / 0.1) 0 12%, transparent 12% 88%, rgb(15 23 42 / 0.1) 88%),
      linear-gradient(145deg, #e2e8f0, #f8fafc 48%, #cbd5e1);
    display: grid;
    place-items: center;
    color: #64748b;
    font-size: 0.9rem;
  }

  .landing-preview img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .landing-images-grid label {
    display: grid;
    gap: 4px;
  }

  .landing-images-grid label span,
  .checkbox-row span {
    color: #64748b;
    font-size: 0.82rem;
  }

  .checkbox-row {
    display: flex !important;
    grid-template-columns: none;
    align-items: center;
    gap: 8px !important;
  }

  .checkbox-row input {
    width: auto;
  }

  .film-form {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-top: 12px;
  }

  input,
  textarea {
    min-width: 0;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0.65rem 0.75rem;
    background: #fff;
    color: #0f172a;
  }

  textarea {
    grid-column: span 3;
    min-height: 42px;
    resize: vertical;
  }

  .films-table {
    display: grid;
    gap: 8px;
    margin-top: 12px;
  }

  .films-table article {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(25rem, 1fr) auto;
    gap: 12px;
    align-items: center;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
    background: #fff;
  }

  .films-table article.inactive {
    opacity: 0.58;
  }

  .film-main {
    display: grid;
    gap: 5px;
  }

  .film-main span {
    color: #64748b;
    font-size: 0.9rem;
  }

  .film-main:has(input) {
    grid-template-columns: 5rem minmax(12rem, 1fr) 5rem minmax(12rem, 1fr);
  }

  .film-analytics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
  }

  .film-analytics div {
    border-radius: 8px;
    background: #f1f5f9;
    padding: 8px;
  }

  .film-analytics strong {
    display: block;
    font-size: 1.05rem;
  }

  .row-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
  }

  :global(.dark) .admin-page {
    color: #fafafa;
  }

  :global(.dark) .notice,
  :global(.dark) .panel,
  :global(.dark) .stats-grid article,
  :global(.dark) .landing-images-grid article,
  :global(.dark) .films-table article {
    border-color: #27272a;
    background: #09090b;
  }

  :global(.dark) input,
  :global(.dark) textarea {
    border-color: #3f3f46;
    background: #18181b;
    color: #fafafa;
  }

  :global(.dark) .stage-grid div,
  :global(.dark) .film-analytics div {
    background: #18181b;
  }

  :global(.dark) .landing-preview {
    border-color: #3f3f46;
    background:
      linear-gradient(90deg, rgb(255 255 255 / 0.08) 0 12%, transparent 12% 88%, rgb(255 255 255 / 0.08) 88%),
      linear-gradient(145deg, #18181b, #27272a 48%, #09090b);
  }

  @media (max-width: 860px) {
    .page-header,
    .section-heading {
      align-items: flex-start;
      flex-direction: column;
    }

    .stats-grid,
    .stage-grid,
    .landing-images-grid,
    .film-form,
    .films-table article,
    .film-main:has(input),
    .film-analytics {
      grid-template-columns: 1fr;
    }

    textarea {
      grid-column: auto;
    }

    .row-actions {
      justify-content: flex-start;
      flex-wrap: wrap;
    }
  }
</style>
