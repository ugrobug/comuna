<script lang="ts">
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildSpecialBookStatusUrl,
    buildSpecialBookSubmitUrl,
    buildSpecialBookWordsUrl,
  } from '$lib/api/backend'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import {
    ArrowPath,
    BookOpen,
    Clock,
    Icon,
    LockClosed,
    PaperAirplane,
  } from 'svelte-hero-icons'

  type BookWord = {
    id: number
    position: number
    word: string
    created_at: string
    submitted_by: {
      id: number
      username: string
    }
  }

  type BookStatus = {
    ok: boolean
    max_words: number
    total_words: number
    remaining_words: number
    can_submit: boolean
    next_available_at?: string | null
    discussion_post?: {
      id: number
      comments_count: number
    }
  }

  const PAGE_LIMIT = 700

  let status: BookStatus | null = null
  let words: BookWord[] = []
  let loading = true
  let wordsLoading = false
  let submitLoading = false
  let error = ''
  let word = ''
  let authOpen = false
  let loadedOffset = 0
  let lastToken: string | null = null

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  const normalizeInput = (value: string) =>
    value
      .replace(/\s+/g, '')
      .replace(/[^\p{L}]/gu, '')
      .slice(0, 64)

  const formatNumber = (value?: number | null) =>
    new Intl.NumberFormat('ru-RU').format(value ?? 0)

  const formatDate = (value?: string | null) => {
    if (!value) return ''
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(value))
    } catch {
      return value
    }
  }

  async function loadStatus() {
    const response = await fetch(buildSpecialBookStatusUrl(), {
      credentials: 'include',
      headers: authHeaders(),
    })
    const data = await response.json()
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || 'Не удалось загрузить проект')
    }
    status = data
  }

  async function loadWords(options: { reset?: boolean } = {}) {
    wordsLoading = true
    const offset = options.reset ? 0 : loadedOffset
    try {
      const response = await fetch(buildSpecialBookWordsUrl({ offset, limit: PAGE_LIMIT }), {
        cache: 'no-store',
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось загрузить слова')
      }
      const nextWords = (data.words ?? []) as BookWord[]
      words = options.reset ? nextWords : [...words, ...nextWords]
      loadedOffset = offset + nextWords.length
      if (status) {
        status = { ...status, total_words: data.total_words ?? status.total_words }
      }
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось загрузить слова', type: 'error' })
    }
    wordsLoading = false
  }

  async function loadProject() {
    loading = true
    error = ''
    try {
      await loadStatus()
      await loadWords({ reset: true })
    } catch (err) {
      error = (err as Error)?.message || 'Не удалось загрузить проект'
    }
    loading = false
  }

  async function submitWord() {
    if (!$siteToken || !$siteUser) {
      authOpen = true
      return
    }
    const cleanWord = normalizeInput(word)
    word = cleanWord
    if (!cleanWord) {
      toast({ content: 'Введите одно слово', type: 'info' })
      return
    }

    submitLoading = true
    try {
      const response = await fetch(buildSpecialBookSubmitUrl(), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ word: cleanWord }),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        status = status
          ? {
              ...status,
              can_submit: Boolean(data?.can_submit),
              next_available_at: data?.next_available_at ?? status.next_available_at,
            }
          : status
        throw new Error(data?.error || 'Не удалось добавить слово')
      }
      word = ''
      toast({ content: `Слово добавлено под номером ${formatNumber(data.word?.position)}`, type: 'success' })
      await loadProject()
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось добавить слово', type: 'error' })
    }
    submitLoading = false
  }

  $: progressPercent = status
    ? Math.min(100, Math.max(0, (status.total_words / status.max_words) * 100))
    : 0
  $: displayTotalWords = status?.total_words ?? 0
  $: displayRemainingWords = status?.remaining_words ?? 150000
  $: bookText = words.map((item) => item.word).join(' ')
  $: canLoadMore = Boolean(status && words.length < status.total_words)
  $: submitDisabled = submitLoading || loading || Boolean(status && !status.can_submit)

  $: if ($siteToken !== lastToken) {
    lastToken = $siteToken
    if (!loading) {
      loadStatus().catch((err) => {
        error = (err as Error)?.message || 'Не удалось обновить статус'
      })
    }
  }

  onMount(loadProject)
</script>

<svelte:head>
  <title>Книга одного слова — спецпроект Tambur</title>
  <meta
    name="description"
    content="Ироничный спецпроект Tambur: каждый зарегистрированный пользователь может добавить одно слово в общую книгу."
  />
  <link rel="canonical" href="/s/book" />
</svelte:head>

<LoginModal bind:open={authOpen} initialMode="signup" />

<section class="book-page">
  <div class="hero-band">
    <div class="hero-inner">
      <div class="hero-copy">
        <div class="project-mark">
          <Icon src={BookOpen} size="18" mini />
          спецпроект
        </div>
        <h1>Книга одного слова</h1>
        <p>
          Это ироничный проект, создающий артефакт интернета, который дает свободу
          написать, что думает сообщество совместными усилиями. Финальная версия
          будет отцензурирована по нарушениям закона и выпущена в виде бумажной
          версии и PDF, доступной бесплатно любому.
        </p>
      </div>

      <div class="write-panel">
        <div class="counter-row">
          <span>{formatNumber(displayTotalWords)} слов</span>
          <span>{formatNumber(displayRemainingWords)} осталось</span>
        </div>
        <div class="progress-track" aria-label="Прогресс книги">
          <span style={`width: ${progressPercent}%`}></span>
        </div>

        <form on:submit|preventDefault={submitWord} class="word-form">
          <input
            bind:value={word}
            on:input={(event) => (word = normalizeInput((event.currentTarget as HTMLInputElement).value))}
            placeholder="Ваше слово"
            maxlength="64"
            autocomplete="off"
          />
          {#if !$siteUser}
            <Button color="primary" disabled={submitLoading} on:click={() => (authOpen = true)}>
              <Icon src={LockClosed} size="18" mini slot="prefix" />
              Войти
            </Button>
          {:else}
            <Button color="primary" submit loading={submitLoading} disabled={submitDisabled}>
              <Icon src={PaperAirplane} size="18" mini slot="prefix" />
              Добавить
            </Button>
          {/if}
        </form>

        {#if status?.next_available_at}
          <div class="cooldown">
            <Icon src={Clock} size="16" mini />
            Следующее слово: {formatDate(status.next_available_at)}
          </div>
        {/if}
      </div>
    </div>
  </div>

  <div class="book-inner">
    {#if error}
      <p class="error">{error}</p>
    {:else if loading}
      <div class="loading-line">
        <Icon src={ArrowPath} size="18" mini />
        Загрузка
      </div>
    {:else}
      <section class="book-sheet" aria-label="Текст книги">
        <div class="sheet-head">
          <span>Текущая версия</span>
          <span>{formatNumber(words.length)} из {formatNumber(status?.total_words)}</span>
        </div>
        <div class="book-text">
          {bookText || 'Книга пока пустая.'}
        </div>
        {#if canLoadMore}
          <div class="load-more">
            <Button color="secondary" loading={wordsLoading} disabled={wordsLoading} on:click={() => loadWords()}>
              Загрузить еще
            </Button>
          </div>
        {/if}
      </section>

      {#if status?.discussion_post?.id}
        <PostComments postId={status.discussion_post.id} postAuthor="tambur-book" />
      {/if}
    {/if}
  </div>
</section>

<style>
  .book-page {
    min-height: 100vh;
    background: #f6f1e9;
    color: #1f2933;
  }

  .hero-band {
    border-bottom: 1px solid #ded6c9;
    background:
      linear-gradient(90deg, rgba(31, 41, 51, 0.06) 1px, transparent 1px),
      linear-gradient(#fbf8f2, #f0e7da);
    background-size: 28px 28px, auto;
  }

  .hero-inner,
  .book-inner {
    width: min(1120px, calc(100vw - 32px));
    margin: 0 auto;
  }

  .hero-inner {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
    gap: 48px;
    align-items: end;
    padding: 64px 0 42px;
  }

  .project-mark {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    color: #2f6f59;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  h1 {
    margin: 0;
    max-width: 720px;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(46px, 8vw, 92px);
    line-height: 0.94;
    letter-spacing: 0;
  }

  .hero-copy p {
    max-width: 700px;
    margin: 24px 0 0;
    color: #374151;
    font-size: 18px;
    line-height: 1.65;
  }

  .write-panel {
    border: 1px solid #d6c8b6;
    border-radius: 8px;
    background: #fffdf8;
    box-shadow: 0 18px 50px rgba(49, 37, 21, 0.14);
    padding: 20px;
  }

  .counter-row,
  .sheet-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    color: #5b6470;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .progress-track {
    height: 10px;
    margin-top: 12px;
    overflow: hidden;
    border: 1px solid #d6c8b6;
    border-radius: 999px;
    background: #e7dccd;
  }

  .progress-track span {
    display: block;
    height: 100%;
    background: #2f6f59;
  }

  .word-form {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
    margin-top: 18px;
  }

  .word-form input {
    min-width: 0;
    border: 1px solid #c7b8a4;
    border-radius: 8px;
    background: #ffffff;
    color: #111827;
    font: inherit;
    font-size: 18px;
    padding: 12px 14px;
    outline: none;
  }

  .word-form input:focus {
    border-color: #2f6f59;
    box-shadow: 0 0 0 3px rgba(47, 111, 89, 0.14);
  }

  .cooldown,
  .loading-line {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
    color: #6b7280;
    font-size: 14px;
  }

  .book-inner {
    padding: 36px 0 64px;
  }

  .book-sheet {
    border: 1px solid #d8cbb9;
    border-radius: 8px;
    background: #fffdf8;
    padding: 28px;
  }

  .book-text {
    min-height: 260px;
    margin-top: 22px;
    color: #1f2933;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(22px, 3vw, 34px);
    line-height: 1.7;
    overflow-wrap: anywhere;
  }

  .load-more {
    display: flex;
    justify-content: center;
    margin-top: 24px;
  }

  .error {
    color: #b42318;
  }

  :global(.book-page #comments) {
    margin-top: 42px;
    color: #111827;
  }

  @media (max-width: 820px) {
    .hero-inner {
      grid-template-columns: 1fr;
      gap: 28px;
      padding-top: 42px;
    }

    .word-form {
      grid-template-columns: 1fr;
    }

    .book-sheet {
      padding: 20px;
    }
  }
</style>
