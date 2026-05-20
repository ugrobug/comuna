<script lang="ts">
  import { onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import {
    buildSpecialBookAdminSettingsUrl,
    buildSpecialBookAdminStatsUrl,
    buildSpecialBookFinalNotificationUrl,
    buildSpecialBookReminderUrl,
    buildSpecialBookStatusUrl,
    buildSpecialBookSubmitUrl,
    buildSpecialBookWordsUrl,
  } from '$lib/api/backend'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import {
    ArrowPath,
    Bell,
    ChartBar,
    Check,
    Clock,
    Cog6Tooth,
    Icon,
    LockClosed,
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
    submit_block_reason?: string
    next_available_at?: string | null
    telegram_linked?: boolean
    vk_linked?: boolean
    has_social_identity?: boolean
    rules_text?: string
    final_pdf?: {
      available: boolean
      url?: string | null
      uploaded_at?: string | null
      announced_at?: string | null
    }
    final_notification?: {
      subscribed: boolean
      notified_at?: string | null
    }
    reminder?: {
      scheduled: boolean
      scheduled_at?: string | null
      sent_at?: string | null
    }
    discussion_post?: {
      id: number
      comments_count: number
    }
  }

  type BookAdminStats = {
    ok: boolean
    total_words: number
    contributors_count: number
    average_words_per_user: number
    top_three_words: number
    registrations_from_page_count: number
    top_users: Array<{
      user: {
        id: number
        username: string
        first_name?: string
        last_name?: string
      }
      words_count: number
    }>
  }

  const PAGE_LIMIT = 700
  const WORD_LIMIT = 30
  const REGISTRATION_SOURCE = 'book'
  const REGISTRATION_PATH = '/s/book'
  const DEFAULT_RULES_TEXT =
    'Каждый зарегистрированный пользователь с привязанным Telegram или VK может добавить одно слово в сутки. Слово должно состоять только из букв и быть не длиннее 30 символов. Слова из стоп-листа не принимаются. Финальная версия книги будет отцензурирована по нарушениям закона и выпущена в электронном виде бесплатно.'

  let status: BookStatus | null = null
  let words: BookWord[] = []
  let loading = true
  let wordsLoading = false
  let submitLoading = false
  let reminderLoading = false
  let error = ''
  let word = ''
  let authOpen = false
  let authInitialMode: 'login' | 'signup' = 'signup'
  let loadedOffset = 0
  let lastToken: string | null = null
  let adminStats: BookAdminStats | null = null
  let adminStatsLoading = false
  let adminStatsError = ''
  let adminStatsLoadedForToken: string | null = null
  let rulesOpen = false
  let rulesDraft = ''
  let rulesSaving = false
  let cooldownOpen = false
  let exportOpen = false
  let finalNotificationLoading = false

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  const normalizeInput = (value: string) =>
    value
      .replace(/\s+/g, '')
      .replace(/[^\p{L}]/gu, '')
      .slice(0, WORD_LIMIT)

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

  const displayUserName = (user: BookAdminStats['top_users'][number]['user']) => {
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ').trim()
    return name || user.username || `id ${user.id}`
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
    rulesDraft = data.rules_text || rulesDraft || DEFAULT_RULES_TEXT
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

  async function loadAdminStats() {
    if (!$siteToken || !$siteUser?.is_staff) return
    adminStatsLoading = true
    adminStatsError = ''
    try {
      const response = await fetch(buildSpecialBookAdminStatsUrl(), {
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось загрузить статистику')
      }
      adminStats = data as BookAdminStats
    } catch (err) {
      adminStatsError = (err as Error)?.message || 'Не удалось загрузить статистику'
    }
    adminStatsLoading = false
  }

  async function submitWord() {
    if (!$siteToken || !$siteUser) {
      authInitialMode = 'signup'
      authOpen = true
      return
    }
    if (!$siteUser.telegram_linked && !$siteUser.vk_linked) {
      authInitialMode = 'login'
      authOpen = true
      toast({ content: 'Привяжите Telegram или VK, чтобы добавить слово.', type: 'info' })
      return
    }
    if (status && !status.can_submit) {
      if (status.submit_block_reason === 'cooldown' || status.next_available_at) {
        cooldownOpen = true
        return
      }
      toast({ content: 'Сейчас нельзя добавить слово.', type: 'info' })
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
              submit_block_reason: data?.submit_block_reason ?? status.submit_block_reason,
              telegram_linked: data?.telegram_linked ?? status.telegram_linked,
              vk_linked: data?.vk_linked ?? status.vk_linked,
              has_social_identity: data?.has_social_identity ?? status.has_social_identity,
              reminder: data?.reminder ?? status.reminder,
            }
          : status
        if (data?.submit_block_reason === 'cooldown' || data?.next_available_at) {
          cooldownOpen = true
          submitLoading = false
          return
        }
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

  async function scheduleReminder() {
    if (!$siteToken || !$siteUser) {
      authInitialMode = 'login'
      authOpen = true
      return
    }
    if (!$siteUser.telegram_linked) {
      authInitialMode = 'login'
      authOpen = true
      toast({ content: 'Привяжите Telegram, чтобы получить напоминание.', type: 'info' })
      return
    }

    reminderLoading = true
    try {
      const response = await fetch(buildSpecialBookReminderUrl(), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        status = status
          ? {
              ...status,
              reminder: data?.reminder ?? status.reminder,
              can_submit: Boolean(data?.can_submit),
              next_available_at: data?.next_available_at ?? status.next_available_at,
            }
          : status
        if (data?.requires_telegram) {
          authInitialMode = 'login'
          authOpen = true
        }
        throw new Error(data?.error || 'Не удалось поставить напоминание')
      }
      status = data as BookStatus
      toast({ content: 'Напоминание в Telegram включено', type: 'success' })
      cooldownOpen = false
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось поставить напоминание', type: 'error' })
    }
    reminderLoading = false
  }

  async function saveRules() {
    if (!$siteToken || !$siteUser?.is_staff) return
    rulesSaving = true
    try {
      const response = await fetch(buildSpecialBookAdminSettingsUrl(), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ rules_text: rulesDraft }),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось сохранить правила')
      }
      status = status ? { ...status, rules_text: data.rules_text, final_pdf: data.final_pdf } : status
      rulesDraft = data.rules_text || DEFAULT_RULES_TEXT
      toast({ content: 'Правила сохранены', type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось сохранить правила', type: 'error' })
    }
    rulesSaving = false
  }

  async function subscribeFinalNotification() {
    if (!$siteToken || !$siteUser) {
      authInitialMode = 'signup'
      authOpen = true
      return
    }
    finalNotificationLoading = true
    try {
      const response = await fetch(buildSpecialBookFinalNotificationUrl(), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось включить оповещение')
      }
      status = data as BookStatus
      toast({ content: 'Оповещение о финальной версии включено', type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось включить оповещение', type: 'error' })
    }
    finalNotificationLoading = false
  }

  $: progressPercent = status
    ? Math.min(100, Math.max(0, (status.total_words / status.max_words) * 100))
    : 0
  $: displayTotalWords = status?.total_words ?? 0
  $: displayMaxWords = status?.max_words ?? 185000
  $: bookText = words.map((item) => item.word).join(' ')
  $: canLoadMore = Boolean(status && words.length < status.total_words)
  $: submitDisabled = submitLoading || loading
  $: needsSocialLink = Boolean($siteUser && !$siteUser.telegram_linked && !$siteUser.vk_linked)
  $: canShowReminder = Boolean($siteUser && status?.next_available_at)
  $: reminderScheduled = Boolean(status?.reminder?.scheduled)
  $: displayedRulesText = status?.rules_text || rulesDraft || DEFAULT_RULES_TEXT
  $: finalNotificationSubscribed = Boolean(status?.final_notification?.subscribed)

  $: if ($siteToken !== lastToken) {
    lastToken = $siteToken
    if (!loading) {
      loadStatus().catch((err) => {
        error = (err as Error)?.message || 'Не удалось обновить статус'
      })
    }
  }

  $: if ($siteUser?.is_staff && $siteToken && adminStatsLoadedForToken !== $siteToken) {
    adminStatsLoadedForToken = $siteToken
    loadAdminStats()
  }

  $: if (!$siteUser?.is_staff) {
    adminStats = null
    adminStatsError = ''
    adminStatsLoadedForToken = null
  }

  onMount(loadProject)
</script>

<svelte:head>
  <title>Книга сообщества интернет — Tambur</title>
  <meta
    name="description"
    content="Мы люди из интернет-сообщества вместе напишем книгу о том, что думаем, видим, чувствуем."
  />
  <link rel="canonical" href="/s/book" />
</svelte:head>

<LoginModal
  bind:open={authOpen}
  initialMode={authInitialMode}
  registrationSource={REGISTRATION_SOURCE}
  registrationPath={REGISTRATION_PATH}
/>

<Modal bind:open={rulesOpen}>
  <span slot="title">Правила</span>
  <div class="book-modal-content">
    <p>{displayedRulesText}</p>
    {#if $siteUser?.is_staff}
      <label class="rules-editor">
        <span>Текст правил</span>
        <textarea bind:value={rulesDraft} rows="8"></textarea>
      </label>
      <div class="modal-actions">
        <Button color="secondary" on:click={() => (rulesOpen = false)}>Закрыть</Button>
        <Button loading={rulesSaving} disabled={rulesSaving} on:click={saveRules}>Сохранить</Button>
      </div>
    {/if}
  </div>
</Modal>

<Modal bind:open={cooldownOpen}>
  <span slot="title">Второе слово можно добавить только через 24 часа</span>
  <div class="book-modal-content">
    {#if status?.next_available_at}
      <p>Следующее слово можно будет добавить {formatDate(status.next_available_at)}. Напомнить?</p>
    {:else}
      <p>Следующее слово можно будет добавить через 24 часа. Напомнить?</p>
    {/if}
    <div class="modal-actions">
      <Button color="secondary" on:click={() => (cooldownOpen = false)}>Не сейчас</Button>
      {#if reminderScheduled}
        <Button disabled>
          <Icon src={Bell} size="18" mini slot="prefix" />
          Напоминание включено
        </Button>
      {:else if $siteUser?.telegram_linked}
        <Button loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
          <Icon src={Bell} size="18" mini slot="prefix" />
          Напомнить
        </Button>
      {:else}
        <Button loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
          <Icon src={Bell} size="18" mini slot="prefix" />
          Привязать Telegram
        </Button>
      {/if}
    </div>
  </div>
</Modal>

<Modal bind:open={exportOpen}>
  <span slot="title">Экспорт в PDF</span>
  <div class="book-modal-content">
    {#if status?.final_pdf?.available && status.final_pdf.url}
      <p>Финальная версия книги уже доступна для скачивания.</p>
      <div class="modal-actions">
        <Button color="secondary" on:click={() => (exportOpen = false)}>Закрыть</Button>
        <Button href={status.final_pdf.url || ''}>Открыть PDF</Button>
      </div>
    {:else}
      <p>PDF станет доступен только после полного завершения и цензурирования.</p>
      <p>Оповестить о завершении книги?</p>
      <div class="modal-actions">
        <Button color="secondary" on:click={() => (exportOpen = false)}>Не сейчас</Button>
        {#if finalNotificationSubscribed}
          <Button disabled>Оповещение включено</Button>
        {:else}
          <Button loading={finalNotificationLoading} disabled={finalNotificationLoading} on:click={subscribeFinalNotification}>
            Оповестить
          </Button>
        {/if}
      </div>
    {/if}
  </div>
</Modal>

<section class="book-page">
  <div class="hero-band">
    <div class="hero-inner">
      <div class="hero-copy">
        <h1>Книга сообщества интернет</h1>
        <p>
          Мы люди из интернет-сообщества вместе напишем книгу о том, что думаем,
          видим, чувствуем. После завершения книга будет отцензурирована и выпущена
          в электронном виде доступном бесплатно каждому и в печатном виде. Каждый
          может добавлять только одно слово в сутки.
        </p>
        <button class="rules-button" type="button" on:click={() => (rulesOpen = true)}>
          Правила
        </button>
      </div>

      <div class="book-counter-panel">
        <div class="counter-title">Объем книги</div>
        <div class="counter-value">
          {formatNumber(displayTotalWords)}
          <span>из</span>
          {formatNumber(displayMaxWords)}
        </div>
        <div class="progress-track" aria-label="Прогресс книги">
          <span style={`width: ${progressPercent}%`}></span>
        </div>
        {#if status?.next_available_at}
          <div class="cooldown">
            <Icon src={Clock} size="16" mini />
            Следующее слово: {formatDate(status.next_available_at)}
          </div>
        {/if}
        {#if needsSocialLink}
          <div class="counter-note">
            Чтобы добавить слово, привяжите Telegram или VK к учетной записи.
          </div>
        {/if}
        {#if canShowReminder}
          <div class="counter-reminder">
            {#if reminderScheduled}
              <Button color="secondary" disabled>
                <Icon src={Bell} size="18" mini slot="prefix" />
                Напоминание включено
              </Button>
            {:else if $siteUser?.telegram_linked}
              <Button color="secondary" loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
                <Icon src={Bell} size="18" mini slot="prefix" />
                Напомнить через 24 часа
              </Button>
            {:else}
              <Button color="secondary" disabled={reminderLoading} on:click={scheduleReminder}>
                <Icon src={Bell} size="18" mini slot="prefix" />
                Привязать Telegram для напоминания
              </Button>
            {/if}
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
      {#if $siteUser?.is_staff}
        <section class="admin-panel" aria-label="Управление книгой">
          <div class="admin-panel-head">
            <div>
              <div class="admin-kicker">
                <Icon src={ChartBar} size="16" mini />
                Статистика
              </div>
              <h2>Управление книгой</h2>
            </div>
            <a class="manage-link" href="/admin/special_projects/" target="_blank" rel="noreferrer">
              <Icon src={Cog6Tooth} size="16" mini />
              Управление проектом
            </a>
          </div>

          {#if adminStatsError}
            <p class="admin-error">{adminStatsError}</p>
          {:else if adminStatsLoading && !adminStats}
            <div class="admin-loading">
              <Icon src={ArrowPath} size="16" mini />
              Загружаем статистику
            </div>
          {:else if adminStats}
            <div class="admin-stats-grid">
              <div class="admin-stat">
                <span>Пользователей внесли слова</span>
                <strong>{formatNumber(adminStats.contributors_count)}</strong>
              </div>
              <div class="admin-stat">
                <span>В среднем слов на пользователя</span>
                <strong>{formatNumber(adminStats.average_words_per_user)}</strong>
              </div>
              <div class="admin-stat">
                <span>Слов у первой тройки</span>
                <strong>{formatNumber(adminStats.top_three_words)}</strong>
              </div>
              <div class="admin-stat">
                <span>Регистраций с этой страницы</span>
                <strong>{formatNumber(adminStats.registrations_from_page_count)}</strong>
              </div>
            </div>

            <div class="top-users">
              <div class="top-users-title">Первая тройка</div>
              {#if adminStats.top_users.length}
                <ol>
                  {#each adminStats.top_users as item}
                    <li>
                      <a href={`/id${item.user.id}`}>{displayUserName(item.user)}</a>
                      <span>@{item.user.username}</span>
                      <strong>{formatNumber(item.words_count)}</strong>
                    </li>
                  {/each}
                </ol>
              {:else}
                <p>Пока нет добавленных слов.</p>
              {/if}
            </div>
          {/if}
        </section>
      {/if}

      <section class="book-sheet" aria-label="Текст книги">
        <div class="sheet-head">
          <span>Текущая версия</span>
          <span>{formatNumber(displayTotalWords)} из {formatNumber(displayMaxWords)}</span>
        </div>
        <div class="book-text">
          {#if bookText}
            <span>{bookText}</span>
          {:else}
            <span class="empty-book">Книга пока пустая.</span>
          {/if}
          <form on:submit|preventDefault={submitWord} class="inline-word-form">
            <input
              bind:value={word}
              on:input={(event) => (word = normalizeInput((event.currentTarget as HTMLInputElement).value))}
              on:focus={() => {
                if (!$siteUser) {
                  authInitialMode = 'signup'
                  authOpen = true
                }
              }}
              placeholder="слово"
              maxlength={WORD_LIMIT}
              autocomplete="off"
              disabled={submitLoading || loading}
              aria-label="Добавить слово в книгу"
            />
            {#if !$siteUser}
              <button
                type="button"
                class="inline-submit"
                aria-label="Войти, чтобы добавить слово"
                on:click={() => {
                  authInitialMode = 'signup'
                  authOpen = true
                }}
              >
                <Icon src={LockClosed} size="16" mini />
              </button>
            {:else if needsSocialLink}
              <button
                type="button"
                class="inline-submit"
                aria-label="Привязать Telegram или VK"
                on:click={() => {
                  authInitialMode = 'login'
                  authOpen = true
                }}
              >
                <Icon src={LockClosed} size="16" mini />
              </button>
            {:else}
              <button
                type="submit"
                class="inline-submit"
                aria-label="Добавить слово"
                disabled={submitDisabled}
              >
                {#if submitLoading}
                  <Icon src={ArrowPath} size="16" mini />
                {:else}
                  <Icon src={Check} size="16" mini />
                {/if}
              </button>
            {/if}
          </form>
        </div>
        <div class="book-export-row">
          <button class="pdf-export-button" type="button" on:click={() => (exportOpen = true)}>
            Экспорт в PDF
          </button>
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

  .rules-button {
    display: inline-flex;
    min-height: 40px;
    align-items: center;
    margin-top: 18px;
    border: 1px solid #2f6f59;
    border-radius: 999px;
    background: #fffdf8;
    color: #2f6f59;
    font-size: 14px;
    font-weight: 700;
    padding: 8px 16px;
  }

  .rules-button:hover {
    background: #eef7f1;
  }

  .book-modal-content {
    display: grid;
    gap: 16px;
    color: #1f2933;
    line-height: 1.55;
  }

  .book-modal-content p {
    margin: 0;
    white-space: pre-wrap;
  }

  .rules-editor {
    display: grid;
    gap: 8px;
  }

  .rules-editor span {
    color: #6b5f51;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .rules-editor textarea {
    width: 100%;
    min-height: 170px;
    border: 1px solid #d8cbb9;
    border-radius: 8px;
    background: #fffdf8;
    color: #1f2933;
    font: inherit;
    line-height: 1.5;
    padding: 12px;
  }

  .modal-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: flex-end;
  }

  .book-counter-panel {
    border: 1px solid #d6c8b6;
    border-radius: 8px;
    background: #fffdf8;
    box-shadow: 0 18px 50px rgba(49, 37, 21, 0.14);
    padding: 20px;
  }

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

  .counter-title {
    color: #6b5f51;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .counter-value {
    margin-top: 8px;
    color: #1f2933;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(32px, 5vw, 54px);
    line-height: 1;
    letter-spacing: 0;
  }

  .counter-value span {
    margin: 0 8px;
    color: #8a7a67;
    font-family: inherit;
    font-size: 0.46em;
    font-style: italic;
  }

  .progress-track {
    height: 10px;
    margin-top: 18px;
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

  .cooldown,
  .loading-line {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-top: 14px;
    color: #6b7280;
    font-size: 14px;
  }

  .counter-note {
    margin-top: 14px;
    color: #7c5f2f;
    font-size: 14px;
    line-height: 1.45;
  }

  .counter-reminder {
    display: flex;
    justify-content: flex-start;
    margin-top: 16px;
  }

  .book-inner {
    padding: 36px 0 64px;
  }

  .admin-panel {
    margin-bottom: 28px;
    border: 1px solid #d8cbb9;
    border-radius: 8px;
    background: #fffdf8;
    padding: 22px;
  }

  .admin-panel-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 18px;
  }

  .admin-kicker {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    color: #2f6f59;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .admin-panel h2 {
    margin: 6px 0 0;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 28px;
    line-height: 1.1;
  }

  .manage-link {
    display: inline-flex;
    min-height: 38px;
    align-items: center;
    gap: 8px;
    border: 1px solid #2f6f59;
    border-radius: 999px;
    color: #2f6f59;
    font-size: 14px;
    font-weight: 700;
    padding: 8px 14px;
    text-decoration: none;
    white-space: nowrap;
  }

  .manage-link:hover {
    background: #eef7f1;
  }

  .admin-stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
    margin-top: 20px;
  }

  .admin-stat {
    border: 1px solid #eadfce;
    border-radius: 8px;
    background: #fbf8f2;
    padding: 14px;
  }

  .admin-stat span {
    display: block;
    min-height: 38px;
    color: #6b5f51;
    font-size: 13px;
    line-height: 1.45;
  }

  .admin-stat strong {
    display: block;
    margin-top: 8px;
    color: #1f2933;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 30px;
    font-weight: 700;
    line-height: 1;
  }

  .top-users {
    margin-top: 20px;
    border-top: 1px solid #eadfce;
    padding-top: 18px;
  }

  .top-users-title {
    color: #6b5f51;
    font-size: 13px;
    font-weight: 700;
    text-transform: uppercase;
  }

  .top-users ol {
    display: grid;
    gap: 8px;
    margin: 12px 0 0;
    padding: 0;
    list-style: none;
  }

  .top-users li {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
    gap: 12px;
    align-items: center;
    border: 1px solid #eadfce;
    border-radius: 8px;
    background: #ffffff;
    padding: 10px 12px;
  }

  .top-users a {
    min-width: 0;
    color: #1f2933;
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  .top-users span {
    min-width: 0;
    color: #6b7280;
    font-size: 13px;
    overflow-wrap: anywhere;
  }

  .top-users strong {
    color: #2f6f59;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 20px;
  }

  .admin-loading,
  .admin-error {
    margin-top: 16px;
    color: #6b7280;
    font-size: 14px;
  }

  .admin-loading {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .admin-error {
    color: #b42318;
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

  .empty-book {
    color: #8a7a67;
    font-style: italic;
  }

  .inline-word-form {
    display: inline-flex;
    width: auto;
    align-items: center;
    gap: 4px;
    margin-left: 8px;
    vertical-align: baseline;
  }

  .inline-word-form input {
    width: 7.2em;
    min-width: 92px;
    max-width: 42vw;
    border: 0;
    border-bottom: 2px solid #b79d7c;
    border-radius: 0;
    background: rgba(255, 255, 255, 0.58);
    color: #1f2933;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 0.86em;
    letter-spacing: 0;
    line-height: 1.25;
    padding: 2px 4px 3px;
    outline: none;
  }

  .inline-word-form input:focus {
    border-bottom-color: #2f6f59;
    background: #fffdf8;
  }

  .inline-word-form input::placeholder {
    color: #a18f77;
    font-style: italic;
  }

  .inline-submit {
    display: inline-flex;
    width: 28px;
    height: 28px;
    align-items: center;
    justify-content: center;
    border: 1px solid #2f6f59;
    border-radius: 999px;
    background: #2f6f59;
    color: #fffdf8;
    vertical-align: middle;
    transition:
      background 0.15s ease,
      border-color 0.15s ease,
      opacity 0.15s ease;
  }

  .inline-submit:hover:not(:disabled) {
    border-color: #245946;
    background: #245946;
  }

  .inline-submit:disabled {
    cursor: default;
    opacity: 0.45;
  }

  .load-more {
    display: flex;
    justify-content: center;
    margin-top: 24px;
  }

  .book-export-row {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
  }

  .pdf-export-button {
    display: inline-flex;
    min-height: 38px;
    align-items: center;
    border: 1px solid #d8cbb9;
    border-radius: 999px;
    background: #fbf8f2;
    color: #3f4a3f;
    font-size: 14px;
    font-weight: 700;
    padding: 8px 14px;
  }

  .pdf-export-button:hover {
    border-color: #2f6f59;
    color: #2f6f59;
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

    .admin-panel-head,
    .top-users li {
      grid-template-columns: 1fr;
    }

    .admin-panel-head {
      display: grid;
    }

    .admin-stats-grid {
      grid-template-columns: 1fr 1fr;
    }

    .manage-link {
      width: fit-content;
      white-space: normal;
    }

    .book-sheet {
      padding: 20px;
    }

    .inline-word-form {
      margin-left: 4px;
    }
  }

  @media (max-width: 520px) {
    .admin-stats-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
