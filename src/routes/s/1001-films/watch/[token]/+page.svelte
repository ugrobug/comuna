<script lang="ts">
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import {
    buildBackendPostPath,
    buildSpecial1001FilmsEntryCommentsUrl,
    buildSpecial1001FilmsEntryRatingVoteUrl,
    buildSpecial1001FilmsEntryUrl,
    type BackendPostRating,
  } from '$lib/api/backend'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import PostTemplateHeader from '$lib/components/site/post-templates/PostTemplateHeader.svelte'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import type { SitePostTemplate } from '$lib/postTemplates'
  import { ArrowLeft, CheckCircle, Icon, LockClosed } from 'svelte-hero-icons'

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
    available_at: string
    rating?: number | null
    comment?: string
    completed_at?: string | null
    film: FilmJourneyFilm
    discussion_post?: {
      id: number
      title: string
      content: string
      template?: SitePostTemplate | null
      post_ratings?: Record<string, BackendPostRating>
      comments_count?: number
    } | null
  }

  let entry: FilmJourneyEntry | null = null
  let loading = true
  let error = ''
  let authOpen = false
  let confirmEarlyOpen = false
  let reviewOpen = false
  let submitSuccess = false
  let selectedRating: number | null = null
  let opinion = ''
  let submittingReview = false
  let reviewError = ''

  const token = String($page.params.token || '')
  const commentsUrl = buildSpecial1001FilmsEntryCommentsUrl(token)
  const ratingVoteUrl = buildSpecial1001FilmsEntryRatingVoteUrl(token)
  const watchGuardMs = 105 * 60 * 1000
  const ratingBlockId = 'film-rating'
  const ratingValues = Array.from({ length: 10 }, (_, index) => index + 1)
  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  async function loadEntry() {
    if (!$siteToken || !$siteUser) {
      const refreshedUser = await refreshSiteUser().catch(() => null)
      if (!refreshedUser) {
        loading = false
        authOpen = true
        return
      }
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
      const userVote = Number(entry?.discussion_post?.post_ratings?.[ratingBlockId]?.user_vote ?? 0)
      selectedRating = Number.isInteger(userVote) && userVote >= 1 && userVote <= 10 ? userVote : entry?.rating ?? null
    } catch (err) {
      error = (err as Error)?.message || 'Не удалось открыть фильм'
    }
    loading = false
  }

  $: film = entry?.film ?? null
  $: discussionPost = entry?.discussion_post ?? null
  $: enoughTimePassed = entry
    ? Date.now() - new Date(entry.available_at).getTime() >= watchGuardMs
    : false

  function openReviewFlow() {
    if (!entry || entry.completed_at) {
      openDiscussionPost()
      return
    }
    reviewError = ''
    if (!enoughTimePassed) {
      confirmEarlyOpen = true
      return
    }
    reviewOpen = true
  }

  async function submitReview() {
    if (!selectedRating) {
      reviewError = 'Поставьте оценку фильму.'
      return
    }
    if (!$siteToken) {
      authOpen = true
      return
    }

    submittingReview = true
    reviewError = ''
    try {
      const ratingResponse = await fetch(ratingVoteUrl, {
        method: 'POST',
        headers: {
          ...authHeaders(),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ block_id: ratingBlockId, value: selectedRating }),
      })
      const ratingPayload = await ratingResponse.json().catch(() => ({}))
      if (!ratingResponse.ok || !ratingPayload?.ok) {
        throw new Error(ratingPayload?.error || 'Не удалось сохранить оценку')
      }
      if (ratingPayload?.entry) {
        entry = ratingPayload.entry
      }

      const cleanOpinion = opinion.trim()
      if (cleanOpinion) {
        const commentResponse = await fetch(commentsUrl, {
          method: 'POST',
          headers: {
            ...authHeaders(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ body: cleanOpinion }),
        })
        const commentPayload = await commentResponse.json().catch(() => ({}))
        if (!commentResponse.ok || !commentPayload?.ok) {
          throw new Error(commentPayload?.error || 'Не удалось опубликовать мнение')
        }
        if (commentPayload?.entry) {
          entry = commentPayload.entry
        }
      }

      await loadEntry()
      reviewOpen = false
      confirmEarlyOpen = false
      submitSuccess = true
      opinion = ''
    } catch (err) {
      reviewError = (err as Error)?.message || 'Не удалось сохранить отзыв'
    } finally {
      submittingReview = false
    }
  }

  function openDiscussionPost() {
    if (!discussionPost) return
    goto(buildBackendPostPath({ id: discussionPost.id, title: discussionPost.title || film?.title || '' }))
  }

  onMount(loadEntry)
</script>

<svelte:head>
  <title>{film ? `${film.title} — 365 фильмов` : '365 фильмов'}</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<LoginModal bind:open={authOpen} initialMode="login" />

{#if confirmEarlyOpen}
  <div class="modal-layer" role="dialog" aria-modal="true" aria-labelledby="early-confirm-title">
    <div class="modal-card modal-card--compact">
      <h2 id="early-confirm-title">Вы действительно посмотрели фильм?</h2>
      <p>
        Время с момента как мы дали вам название фильма прошло слишком мало для просмотра,
        вы действительно посмотрели фильм?
      </p>
      <div class="modal-actions">
        <button type="button" class="plain-button" on:click={() => (confirmEarlyOpen = false)}>Нет</button>
        <button
          type="button"
          class="primary-action"
          on:click={() => {
            confirmEarlyOpen = false
            reviewOpen = true
          }}
        >
          Да
        </button>
      </div>
    </div>
  </div>
{/if}

{#if reviewOpen}
  <div class="modal-layer" role="dialog" aria-modal="true" aria-labelledby="review-title">
    <div class="modal-card">
      <div class="modal-head">
        <h2 id="review-title">Оцените фильм</h2>
        <button type="button" class="modal-close" aria-label="Закрыть" on:click={() => (reviewOpen = false)}>
          ×
        </button>
      </div>

      <div class="review-rating">
        <div class="review-rating__eyebrow">Рейтинг</div>
        <div class="review-rating__scale" role="group" aria-label="Оценка фильма от 1 до 10">
          {#each ratingValues as value}
            <button
              type="button"
              class:is-selected={selectedRating === value}
              aria-pressed={selectedRating === value}
              on:click={() => (selectedRating = value)}
            >
              {value}
            </button>
          {/each}
        </div>
      </div>

      <label class="opinion-field">
        <span>Ваше мнение о фильме</span>
        <textarea
          bind:value={opinion}
          rows="5"
          placeholder="Можно оставить пустым"
          disabled={submittingReview}
        ></textarea>
      </label>

      {#if reviewError}
        <p class="review-error">{reviewError}</p>
      {/if}

      <div class="modal-actions">
        <button type="button" class="plain-button" on:click={() => (reviewOpen = false)} disabled={submittingReview}>
          Отмена
        </button>
        <button type="button" class="primary-action" on:click={submitReview} disabled={submittingReview}>
          {submittingReview ? 'Публикуем...' : 'Дальше'}
        </button>
      </div>
    </div>
  </div>
{/if}

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
    <article class="film-card">
      <div class="film-heading">
        <span class="kicker">Фильм для просмотра на сегодня:</span>
        <h1>{film.title}</h1>
        {#if entry.completed_at}
          <p class="done-note">
            <Icon src={CheckCircle} size="18" mini />
            Ссылка на новый фильм придет завтра в Telegram-бота. Ваш отзыв о фильме был опубликован.
          </p>
        {:else}
          <p class="meta">
            Посмотрите фильм вне сайта, а затем вернитесь, чтобы поставить оценку.
          </p>
        {/if}
      </div>

      {#if discussionPost}
        {#if discussionPost.template}
          <div class="movie-template-header">
            <PostTemplateHeader
              template={discussionPost.template}
              fallbackTitle={discussionPost.title || film.title}
              postId={discussionPost.id}
            />
          </div>
        {/if}

        {#if film.description}
          <div class="film-description">
            {#each film.description.split('\n') as paragraph}
              {#if paragraph.trim()}
                <p>{paragraph}</p>
              {/if}
            {/each}
          </div>
        {/if}

        {#if submitSuccess}
          <div class="success-box">
            <Icon src={CheckCircle} size="20" mini />
            <div>
              <strong>Ссылка на новый фильм придет завтра в Telegram-бота.</strong>
              <span>Ваш отзыв о фильме был опубликован.</span>
            </div>
          </div>
        {/if}

        <div class="watch-actions">
          {#if entry.completed_at || submitSuccess}
            <button type="button" class="primary-action" on:click={openDiscussionPost}>
              Посмотреть все отзывы
            </button>
          {:else}
            <button type="button" class="primary-action" on:click={openReviewFlow}>
              Я посмотрел
            </button>
          {/if}
        </div>

      {:else}
        <p class="meta">Не удалось подготовить обсуждение фильма.</p>
      {/if}
    </article>
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

  .film-card,
  .state {
    max-width: 52rem;
    margin: 0 auto;
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    background: rgb(255 255 255 / 0.84);
    box-shadow: 0 18px 48px rgb(15 23 42 / 0.08);
  }

  .film-card {
    padding: clamp(1.25rem, 3vw, 2.25rem);
  }

  .film-heading {
    margin-bottom: 1.25rem;
  }

  .movie-template-header {
    margin-bottom: 1.25rem;
  }

  .kicker {
    color: var(--btn-primary-background);
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0;
  }

  h1 {
    margin-top: 0.4rem;
    font-size: clamp(1.8rem, 4vw, 3rem);
    line-height: 1.05;
    letter-spacing: 0;
    font-weight: 500;
  }

  .meta,
  .done-note,
  .state p {
    color: #475569;
    line-height: 1.55;
  }

  .done-note {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin-top: 0.75rem;
  }

  .film-description {
    margin-top: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    color: #263244;
    font-size: 1.02rem;
    line-height: 1.7;
  }

  .film-description p {
    margin: 0;
  }

  .watch-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 1.5rem;
  }

  .primary-action,
  .plain-button {
    border: 0;
    border-radius: 999px;
    padding: 0.75rem 1.15rem;
    font-weight: 700;
    cursor: pointer;
    transition:
      transform 0.16s ease,
      box-shadow 0.16s ease,
      background 0.16s ease;
  }

  .primary-action {
    background: var(--btn-primary-background);
    color: var(--btn-primary-color, #fff);
    box-shadow: 0 12px 28px rgb(37 99 235 / 0.2);
  }

  .primary-action:hover:not(:disabled),
  .plain-button:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  .primary-action:disabled,
  .plain-button:disabled {
    cursor: default;
    opacity: 0.65;
  }

  .plain-button {
    background: #e2e8f0;
    color: #0f172a;
  }

  .success-box {
    margin-top: 1.25rem;
    display: flex;
    gap: 0.7rem;
    align-items: flex-start;
    border: 1px solid rgb(187 247 208);
    border-radius: 12px;
    background: rgb(240 253 244);
    color: #14532d;
    padding: 0.9rem 1rem;
  }

  .success-box div {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .modal-layer {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    background: rgb(15 23 42 / 0.55);
    padding: 1rem;
  }

  .modal-card {
    width: min(100%, 38rem);
    border-radius: 18px;
    border: 1px solid rgb(203 213 225);
    background: #fff;
    color: #0f172a;
    box-shadow: 0 28px 80px rgb(15 23 42 / 0.25);
    padding: clamp(1rem, 3vw, 1.5rem);
  }

  .modal-card--compact {
    width: min(100%, 30rem);
  }

  .modal-card h2 {
    margin: 0;
    font-size: 1.45rem;
    line-height: 1.15;
    font-weight: 700;
  }

  .modal-card p {
    margin: 0.8rem 0 0;
    color: #475569;
    line-height: 1.55;
  }

  .modal-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .modal-close {
    width: 2rem;
    height: 2rem;
    border: 0;
    border-radius: 999px;
    background: #e2e8f0;
    color: #0f172a;
    font-size: 1.35rem;
    line-height: 1;
    cursor: pointer;
  }

  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.75rem;
    margin-top: 1.25rem;
  }

  .review-rating {
    margin-top: 1.2rem;
    border-radius: 14px;
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    padding: 1rem;
  }

  .review-rating__eyebrow {
    color: #475569;
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0;
    margin-bottom: 0.65rem;
  }

  .review-rating__scale {
    display: grid;
    grid-template-columns: repeat(10, minmax(0, 1fr));
    gap: 0.35rem;
  }

  .review-rating__scale button {
    min-width: 0;
    height: 2.8rem;
    border: 1px solid #cbd5e1;
    border-radius: 10px;
    background: #fff;
    color: #0f172a;
    font-weight: 800;
    cursor: pointer;
  }

  .review-rating__scale button.is-selected {
    border-color: var(--btn-primary-background);
    background: var(--btn-primary-background);
    color: var(--btn-primary-color, #fff);
  }

  .opinion-field {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 1rem;
    color: #334155;
    font-size: 0.92rem;
    font-weight: 700;
  }

  .opinion-field textarea {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 12px;
    padding: 0.85rem 0.95rem;
    font: inherit;
    font-weight: 400;
    line-height: 1.5;
    resize: vertical;
  }

  .review-error {
    margin-top: 0.8rem;
    color: #dc2626;
    font-size: 0.92rem;
  }

  .state {
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
  :global(.dark) .done-note,
  :global(.dark) .state p {
    color: #a1a1aa;
  }

  :global(.dark) .film-card,
  :global(.dark) .state {
    border-color: rgb(39 39 42);
    background: rgb(9 9 11 / 0.8);
    box-shadow: 0 18px 48px rgb(0 0 0 / 0.24);
  }

  :global(.dark) .film-description {
    color: #d4d4d8;
  }

  :global(.dark) .plain-button,
  :global(.dark) .modal-close {
    background: #27272a;
    color: #fafafa;
  }

  :global(.dark) .modal-card {
    border-color: #3f3f46;
    background: #18181b;
    color: #fafafa;
  }

  :global(.dark) .modal-card p,
  :global(.dark) .opinion-field,
  :global(.dark) .review-rating__eyebrow {
    color: #a1a1aa;
  }

  :global(.dark) .review-rating {
    border-color: #3f3f46;
    background: #09090b;
  }

  :global(.dark) .review-rating__scale button,
  :global(.dark) .opinion-field textarea {
    border-color: #3f3f46;
    background: #18181b;
    color: #fafafa;
  }

  @media (max-width: 820px) {
    .watch-page {
      padding: 1rem;
    }

    .review-rating__scale {
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }

    .modal-actions {
      justify-content: stretch;
    }

    .modal-actions > * {
      flex: 1;
    }
  }
</style>
