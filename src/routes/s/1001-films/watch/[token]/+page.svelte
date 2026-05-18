<script lang="ts">
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import { buildSpecial1001FilmsEntryUrl } from '$lib/api/backend'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { ArrowLeft, CheckCircle, Film, Icon, LockClosed, Star } from 'svelte-hero-icons'

  type FilmJourneyFilm = {
    title: string
    original_title?: string
    year?: number
    category?: string
    description?: string
    imdb_url?: string
    imdb_rating?: string
    poster_url?: string
    runtime_minutes?: number
    director?: string
    country?: string
    genres?: string
  }

  type FilmJourneyEntry = {
    position: number
    rating?: number | null
    comment?: string
    completed_at?: string | null
    film: FilmJourneyFilm
  }

  let entry: FilmJourneyEntry | null = null
  let loading = true
  let submitting = false
  let error = ''
  let authOpen = false
  let rating = 8
  let comment = ''

  const token = String($page.params.token || '')
  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  async function loadEntry() {
    if (!$siteToken || !$siteUser) {
      loading = false
      authOpen = true
      return
    }
    loading = true
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsEntryUrl(token), {
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось открыть фильм')
      }
      entry = data.entry
      rating = entry?.rating || 8
      comment = entry?.comment || ''
    } catch (err) {
      error = (err as Error)?.message || 'Не удалось открыть фильм'
    }
    loading = false
  }

  async function submitReview() {
    if (!entry) return
    submitting = true
    try {
      const response = await fetch(buildSpecial1001FilmsEntryUrl(token), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ rating, comment }),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось сохранить оценку')
      }
      entry = data.entry
      toast({ content: 'Оценка сохранена. Следующий фильм придёт завтра.', type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось сохранить оценку', type: 'error' })
    }
    submitting = false
  }

  const filmMeta = (film: FilmJourneyFilm) =>
    [film.original_title, film.year, film.category, film.genres].filter(Boolean).join(' · ')

  $: film = entry?.film ?? null

  onMount(loadEntry)
</script>

<svelte:head>
  <title>{film ? `${film.title} — 1001 фильм` : '1001 фильм'}</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<LoginModal bind:open={authOpen} initialMode="login" />

<section class="watch-page">
  <a class="back-link" href="/s/1001-films">
    <Icon src={ArrowLeft} size="16" mini />
    К проекту
  </a>

  {#if loading}
    <div class="state">Открываем секретную ссылку...</div>
  {:else if !$siteToken || !$siteUser}
    <div class="state">
      <Icon src={LockClosed} size="34" solid />
      <h1>Нужна авторизация</h1>
      <p>Эта страница доступна только участнику, которому пришла ссылка.</p>
      <Button color="primary" size="lg" on:click={() => (authOpen = true)}>Войти</Button>
    </div>
  {:else if error}
    <div class="state">
      <h1>{error}</h1>
      <p>Проверьте аккаунт или откройте последнюю ссылку из уведомлений.</p>
    </div>
  {:else if entry && film}
    <div class="film-layout">
      <div class="poster">
        {#if film.poster_url}
          <img src={film.poster_url} alt={film.title} />
        {:else}
          <div class="poster-placeholder">
            <Icon src={Film} size="54" solid />
            <span>#{entry.position}</span>
          </div>
        {/if}
      </div>

      <article class="film-card">
        <span class="kicker">фильм #{entry.position}</span>
        <h1>{film.title}</h1>
        {#if filmMeta(film)}
          <p class="meta">{filmMeta(film)}</p>
        {/if}

        <div class="facts">
          {#if film.imdb_rating}
            <span><Icon src={Star} size="16" mini /> IMDb {film.imdb_rating}</span>
          {/if}
          {#if film.runtime_minutes}
            <span>{film.runtime_minutes} мин.</span>
          {/if}
          {#if film.director}
            <span>{film.director}</span>
          {/if}
          {#if film.country}
            <span>{film.country}</span>
          {/if}
        </div>

        {#if film.description}
          <p class="description">{film.description}</p>
        {/if}

        {#if film.imdb_url}
          <a class="imdb-link" href={film.imdb_url} target="_blank" rel="noopener noreferrer">
            Открыть IMDb
          </a>
        {/if}

        <form on:submit|preventDefault={submitReview} class="review">
          <div class="review-top">
            <label for="rating">Оценка</label>
            <strong>{rating}/10</strong>
          </div>
          <input id="rating" type="range" min="1" max="10" step="1" bind:value={rating} />

          <label for="comment">Комментарий</label>
          <textarea
            id="comment"
            bind:value={comment}
            rows="5"
            minlength="3"
            maxlength="5000"
            required
            placeholder="Что осталось после просмотра?"
          ></textarea>

          <Button
            color="primary"
            size="lg"
            submit
            loading={submitting}
            disabled={submitting || comment.trim().length < 3}
          >
            <Icon src={entry.completed_at ? CheckCircle : Star} size="18" mini slot="prefix" />
            {entry.completed_at ? 'Обновить оценку' : 'Сохранить и ждать следующий'}
          </Button>
        </form>
      </article>
    </div>
  {/if}
</section>

<style>
  .watch-page {
    min-height: calc(100svh - 4.5rem);
    background: rgb(248 250 252);
    color: #0f172a;
    padding: clamp(1rem, 3vw, 2.25rem);
  }

  .back-link {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    color: #475569;
    margin-bottom: 1.25rem;
  }

  .film-layout {
    max-width: 72rem;
    margin: 0 auto;
    display: grid;
    grid-template-columns: minmax(16rem, 24rem) minmax(0, 1fr);
    gap: clamp(1.5rem, 4vw, 3rem);
    align-items: start;
  }

  .poster,
  .film-card,
  .state {
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    background: rgb(255 255 255 / 0.84);
    box-shadow: 0 18px 48px rgb(15 23 42 / 0.08);
  }

  .poster {
    overflow: hidden;
    aspect-ratio: 2 / 3;
  }

  .poster img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .poster-placeholder {
    height: 100%;
    display: grid;
    place-items: center;
    background:
      linear-gradient(90deg, rgb(15 23 42 / 0.1) 0 11%, transparent 11% 89%, rgb(15 23 42 / 0.1) 89%),
      linear-gradient(150deg, #f8fafc, rgb(11 93 215 / 0.16) 52%, #e2e8f0);
    color: #0f172a;
  }

  .poster-placeholder span {
    font-size: 3rem;
    font-weight: 800;
  }

  .film-card {
    padding: clamp(1.25rem, 3vw, 2.25rem);
  }

  .kicker {
    color: var(--btn-primary-background);
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0;
  }

  h1 {
    margin-top: 0.4rem;
    font-size: clamp(2.2rem, 6vw, 4.8rem);
    line-height: 0.98;
    letter-spacing: 0;
    font-weight: 500;
  }

  .meta,
  .description,
  .state p {
    color: #475569;
    line-height: 1.7;
  }

  .facts {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin: 1rem 0;
  }

  .facts span,
  .imdb-link {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border-radius: 999px;
    background: rgb(241 245 249);
    padding: 0.38rem 0.7rem;
    font-size: 0.9rem;
    color: #0f172a;
  }

  .imdb-link {
    width: max-content;
    margin-top: 0.5rem;
    background: rgb(219 234 254);
  }

  .review {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    margin-top: 1.5rem;
    border-top: 1px solid rgb(226 232 240);
    padding-top: 1.25rem;
  }

  .review-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  label {
    color: #334155;
    font-weight: 600;
  }

  input[type='range'] {
    width: 100%;
  }

  textarea {
    width: 100%;
    border-radius: 8px;
    border: 1px solid rgb(203 213 225);
    background: rgb(255 255 255);
    color: #0f172a;
    padding: 0.85rem;
    resize: vertical;
  }

  .state {
    max-width: 34rem;
    margin: 4rem auto;
    padding: 2rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    align-items: flex-start;
  }

  :global(.dark) .watch-page {
    background: rgb(9 9 11);
    color: #fafafa;
  }

  :global(.dark) .back-link,
  :global(.dark) .meta,
  :global(.dark) .description,
  :global(.dark) .state p {
    color: #a1a1aa;
  }

  :global(.dark) .poster,
  :global(.dark) .film-card,
  :global(.dark) .state {
    border-color: rgb(39 39 42);
    background: rgb(9 9 11 / 0.8);
    box-shadow: 0 18px 48px rgb(0 0 0 / 0.24);
  }

  :global(.dark) .poster-placeholder {
    background:
      linear-gradient(90deg, rgb(255 255 255 / 0.08) 0 11%, transparent 11% 89%, rgb(255 255 255 / 0.08) 89%),
      linear-gradient(150deg, #09090b, rgb(37 99 235 / 0.36) 52%, #18181b);
    color: #fafafa;
  }

  :global(.dark) .facts span,
  :global(.dark) .imdb-link {
    background: rgb(24 24 27);
    color: #fafafa;
  }

  :global(.dark) .review {
    border-top-color: rgb(39 39 42);
  }

  :global(.dark) label {
    color: #e4e4e7;
  }

  :global(.dark) textarea {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
    color: #fafafa;
  }

  @media (max-width: 820px) {
    .film-layout {
      grid-template-columns: 1fr;
    }

    .poster {
      max-width: 20rem;
    }
  }
</style>
