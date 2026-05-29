<script lang="ts">
  import { page } from '$app/stores'
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import {
    buildSpecial1001FilmsAdminFilmUrl,
    type BackendPostRating,
  } from '$lib/api/backend'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import PostTemplateHeader from '$lib/components/site/post-templates/PostTemplateHeader.svelte'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import type { SitePostTemplate } from '$lib/postTemplates'

  type PreviewResponse = {
    ok: boolean
    error?: string
    film?: {
      id: number
      title: string
      sort_order: number
    }
    discussion_post?: {
      id: number | null
      title: string
      content: string
      template?: SitePostTemplate | null
      post_ratings?: Record<string, BackendPostRating>
    }
  }

  let loading = true
  let error = ''
  let film: PreviewResponse['film'] | null = null
  let discussionPost: PreviewResponse['discussion_post'] | null = null
  const filmId = String($page.params.filmId || '')

  const authHeaders = (): Record<string, string> => {
    return $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}
  }

  async function loadPreview() {
    loading = true
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsAdminFilmUrl(filmId), {
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = (await response.json()) as PreviewResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить предпросмотр')
      }
      film = data.film ?? null
      discussionPost = data.discussion_post ?? null
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить предпросмотр'
    } finally {
      loading = false
    }
  }

  onMount(async () => {
    if (!browser) return
    const currentUser = $siteUser || (await refreshSiteUser())
    if (!currentUser) {
      goto(`/login?next=${encodeURIComponent(`/s/365-films/admin/preview/${filmId}`)}`)
      return
    }
    if (!currentUser.is_staff) {
      goto('/s/365-films')
      return
    }
    await loadPreview()
  })
</script>

<svelte:head>
  <title>Предпросмотр фильма | 365 фильмов</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<main class="preview-page">
  <header class="preview-header">
    <div>
      <a href="/s/365-films/admin">← к управлению</a>
      <h1>{film ? `${film.sort_order}. ${film.title}` : 'Предпросмотр фильма'}</h1>
    </div>
    <Button on:click={loadPreview} disabled={loading}>Обновить</Button>
  </header>

  {#if loading}
    <section class="panel">Загрузка...</section>
  {:else if error}
    <section class="panel error">{error}</section>
  {:else if discussionPost}
    <section class="panel">
      {#if discussionPost.template}
        <div class="movie-template-header">
          <PostTemplateHeader
            template={discussionPost.template}
            fallbackTitle={discussionPost.title || film?.title || ''}
            postId={discussionPost.id}
          />
        </div>
      {/if}
      <PostBody
        body={discussionPost.content}
        template={discussionPost.template}
        postRatings={discussionPost.post_ratings ?? {}}
        postId={null}
        title={discussionPost.title || film?.title}
        showFullBody={true}
      />
    </section>
  {:else}
    <section class="panel">Предпросмотр пока пуст.</section>
  {/if}
</main>

<style>
  .preview-page {
    width: min(880px, 100%);
    margin: 0 auto;
    display: grid;
    gap: 16px;
    color: #0f172a;
  }

  .preview-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 12px;
  }

  .preview-header a {
    color: #475569;
    font-size: 0.9rem;
  }

  h1 {
    margin: 0.25rem 0 0;
    font-size: clamp(1.5rem, 3vw, 2.25rem);
    line-height: 1.1;
    letter-spacing: 0;
    font-weight: 600;
  }

  .panel {
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
    padding: clamp(1rem, 3vw, 1.5rem);
  }

  .movie-template-header {
    margin-bottom: 1.25rem;
  }

  .error {
    color: #b91c1c;
  }

  :global(.dark) .preview-page {
    color: #fafafa;
  }

  :global(.dark) .preview-header a {
    color: #a1a1aa;
  }

  :global(.dark) .panel {
    border-color: #27272a;
    background: #09090b;
  }

  @media (max-width: 720px) {
    .preview-header {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
