<script lang="ts">
  import { onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import {
    buildSpecialBookAdminSelectionCensorUrl,
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
    Check,
    Clock,
    Icon,
    LockClosed,
  } from 'svelte-hero-icons'

  type BookWord = {
    id: number
    position: number
    word: string
    is_censored?: boolean
  }

  type CensorFragment = {
    word_id: number
    start: number
    end: number
  }

  type BookStatus = {
    ok: boolean
    max_words: number
    total_words: number
    remaining_words: number
    can_submit: boolean
    submit_block_reason?: string
    next_available_at?: string | null
    moderation_locked_until?: string | null
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

  const PAGE_LIMIT = 700
  const WORD_LIMIT = 30
  const REGISTRATION_SOURCE = 'book'
  const REGISTRATION_PATH = '/s/book'
  const SOCIAL_LINK_REQUIRED_MESSAGE =
    'Только пользователи с привязанным телеграм или вк могут писать эту книгу - привязать можно одной кнопкой в настройках: https://tambur.pub/settings'
  const DEFAULT_RULES_TEXT =
    'Каждый зарегистрированный пользователь с привязанным Telegram или VK может добавить одно слово или знак препинания в сутки. Запись должна состоять только из букв и знаков препинания и быть не длиннее 30 символов. Слова из стоп-листа не принимаются. Финальная версия книги будет отцензурирована по нарушениям закона и выпущена в электронном виде бесплатно.'

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
  let rulesOpen = false
  let rulesDraft = ''
  let cooldownOpen = false
  let exportOpen = false
  let finalNotificationLoading = false
  let bookSheetEl: HTMLElement | null = null
  let bookWordsEl: HTMLElement | null = null
  let selectedFragments: CensorFragment[] = []
  let selectedText = ''
  let selectionCensorButtonStyle = ''
  let selectionCensorLoading = false
  let reminderDisabledNotice = false
  let backgroundRefreshInFlight = false
  let backgroundRefreshPromise: Promise<void> | null = null

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  const normalizeInput = (value: string) =>
    value
      .replace(/\s+/g, '')
      .replace(/[^\p{L}\p{P}]/gu, '')
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

  async function loadWords(options: { reset?: boolean; silent?: boolean } = {}) {
    if (!options.silent) {
      wordsLoading = true
    }
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
      if (!options.silent) {
        toast({ content: (err as Error)?.message || 'Не удалось загрузить слова', type: 'error' })
      }
      throw err
    } finally {
      if (!options.silent) {
        wordsLoading = false
      }
    }
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

  async function refreshBookSilently(options: { force?: boolean } = {}) {
    if (backgroundRefreshPromise) {
      if (options.force) {
        await backgroundRefreshPromise
      }
      return
    }
    if (!options.force && (loading || submitLoading)) return

    backgroundRefreshInFlight = true
    backgroundRefreshPromise = (async () => {
      try {
        await loadStatus()
        const targetTotal = status?.total_words ?? loadedOffset
        if (targetTotal < loadedOffset) {
          await loadWords({ reset: true, silent: true })
          return
        }
        while (loadedOffset < targetTotal) {
          const previousOffset = loadedOffset
          await loadWords({ silent: true })
          if (loadedOffset <= previousOffset) break
        }
      } catch {
        // Фоновое обновление не должно мешать пользователю читать или вводить слово.
      } finally {
        backgroundRefreshInFlight = false
        backgroundRefreshPromise = null
      }
    })()
    await backgroundRefreshPromise
  }

  async function submitWord() {
    if (!$siteToken || !$siteUser) {
      authInitialMode = 'signup'
      authOpen = true
      return
    }
    if (!$siteUser.telegram_linked && !$siteUser.vk_linked) {
      toast({ content: SOCIAL_LINK_REQUIRED_MESSAGE, type: 'info' })
      return
    }
    await refreshBookSilently({ force: true })
    if (status && !status.can_submit) {
      if (status.submit_block_reason === 'moderation_lock' || status.moderation_locked_until) {
        toast({
          content: status.moderation_locked_until
            ? `Возможность добавить слово заблокирована до ${formatDate(status.moderation_locked_until)}.`
            : 'Возможность добавить слово временно заблокирована.',
          type: 'error',
        })
        return
      }
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
              moderation_locked_until: data?.moderation_locked_until ?? status.moderation_locked_until,
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
      reminderDisabledNotice = false
      toast({ content: 'Напоминание в Telegram включено', type: 'success' })
      cooldownOpen = false
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось поставить напоминание', type: 'error' })
    }
    reminderLoading = false
  }

  async function cancelReminder() {
    if (!$siteToken || !$siteUser) {
      authInitialMode = 'login'
      authOpen = true
      return
    }

    reminderLoading = true
    try {
      const response = await fetch(buildSpecialBookReminderUrl(), {
        method: 'DELETE',
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось выключить напоминание')
      }
      status = data as BookStatus
      reminderDisabledNotice = true
      toast({ content: 'Напоминание выключено', type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось выключить напоминание', type: 'error' })
    }
    reminderLoading = false
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

  function clearCensorSelection(removeBrowserSelection = false) {
    selectedFragments = []
    selectedText = ''
    selectionCensorButtonStyle = ''
    if (removeBrowserSelection) {
      window.getSelection()?.removeAllRanges()
    }
  }

  function rangeOffsetInsideSpan(range: Range, span: HTMLElement, boundary: 'start' | 'end') {
    const textLength = span.textContent?.length ?? 0
    const spanRange = document.createRange()
    spanRange.selectNodeContents(span)

    if (boundary === 'start') {
      if (range.compareBoundaryPoints(Range.START_TO_START, spanRange) <= 0) return 0
      const offsetRange = document.createRange()
      offsetRange.selectNodeContents(span)
      offsetRange.setEnd(range.startContainer, range.startOffset)
      return Math.min(textLength, Math.max(0, offsetRange.toString().length))
    }

    if (range.compareBoundaryPoints(Range.END_TO_END, spanRange) >= 0) return textLength
    const offsetRange = document.createRange()
    offsetRange.selectNodeContents(span)
    offsetRange.setEnd(range.endContainer, range.endOffset)
    return Math.min(textLength, Math.max(0, offsetRange.toString().length))
  }

  function updateCensorSelection() {
    if (!$siteUser?.is_staff || !bookWordsEl || !bookSheetEl) {
      clearCensorSelection()
      return
    }

    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      clearCensorSelection()
      return
    }

    const range = selection.getRangeAt(0)
    if (!range.intersectsNode(bookWordsEl)) {
      clearCensorSelection()
      return
    }

    const fragments: CensorFragment[] = []
    const spans = Array.from(bookWordsEl.querySelectorAll<HTMLElement>('[data-book-word-id]'))
    for (const span of spans) {
      if (!range.intersectsNode(span)) continue
      const wordId = Number(span.dataset.bookWordId)
      if (!wordId) continue
      const start = rangeOffsetInsideSpan(range, span, 'start')
      const end = rangeOffsetInsideSpan(range, span, 'end')
      if (start < end) {
        fragments.push({ word_id: wordId, start, end })
      }
    }

    if (!fragments.length) {
      clearCensorSelection()
      return
    }

    const rect = range.getBoundingClientRect()
    const fallbackRect = range.getClientRects()[0]
    const buttonRect = rect.width || rect.height ? rect : fallbackRect
    if (buttonRect) {
      const sheetRect = bookSheetEl.getBoundingClientRect()
      const left = Math.max(80, Math.min(sheetRect.width - 80, buttonRect.left - sheetRect.left + buttonRect.width / 2))
      const top = Math.max(44, buttonRect.bottom - sheetRect.top + 10)
      selectionCensorButtonStyle = `left: ${left}px; top: ${top}px;`
    }

    selectedText = selection.toString().trim()
    selectedFragments = fragments
  }

  async function censorSelection() {
    if (!$siteUser?.is_staff) {
      clearCensorSelection(true)
      toast({ content: 'Недостаточно прав для цензуры.', type: 'error' })
      return
    }
    if (!selectedFragments.length) {
      toast({ content: 'Выделите фрагмент книги.', type: 'info' })
      return
    }
    if (!window.confirm('Зацензурить выделенный фрагмент? Оригинальный текст будет удален из базы.')) {
      return
    }

    selectionCensorLoading = true
    try {
      const response = await fetch(buildSpecialBookAdminSelectionCensorUrl(), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
        },
        body: JSON.stringify({ fragments: selectedFragments }),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось зацензурить фрагмент')
      }
      const updatedWords = new Map<number, BookWord>(
        ((data.words || []) as BookWord[]).map((item) => [item.id, item]),
      )
      words = words.map((item) => updatedWords.get(item.id) || item)
      clearCensorSelection(true)
      toast({ content: 'Фрагмент зацензурирован', type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось зацензурить фрагмент', type: 'error' })
    }
    selectionCensorLoading = false
  }

  $: progressPercent = status
    ? Math.min(100, Math.max(0, (status.total_words / status.max_words) * 100))
    : 0
  $: displayTotalWords = status?.total_words ?? 0
  $: displayMaxWords = status?.max_words ?? 185000
  $: canLoadMore = Boolean(status && words.length < status.total_words)
  $: submitDisabled = submitLoading || loading
  $: needsSocialLink = Boolean($siteUser && !$siteUser.telegram_linked && !$siteUser.vk_linked)
  $: moderationLockedUntil = status?.moderation_locked_until || null
  $: canShowReminder = Boolean($siteUser && (status?.next_available_at || status?.reminder?.scheduled))
  $: reminderScheduled = Boolean(status?.reminder?.scheduled)
  $: reminderToggleLabel = reminderScheduled
    ? 'Напоминание включено'
    : reminderDisabledNotice
      ? 'Напоминание выключено'
      : 'Напомнить через 24 часа'
  $: displayedRulesText = status?.rules_text || rulesDraft || DEFAULT_RULES_TEXT
  $: finalNotificationSubscribed = Boolean(status?.final_notification?.subscribed)

  $: if (!$siteUser?.is_staff && selectedFragments.length) {
    clearCensorSelection()
  }

  $: if ($siteToken !== lastToken) {
    lastToken = $siteToken
    if (!loading) {
      loadStatus().catch((err) => {
        error = (err as Error)?.message || 'Не удалось обновить статус'
      })
    }
  }

  onMount(() => {
    loadProject()
    const refreshTimer = window.setInterval(() => {
      refreshBookSilently()
    }, 5000)
    document.addEventListener('selectionchange', updateCensorSelection)
    return () => {
      window.clearInterval(refreshTimer)
      document.removeEventListener('selectionchange', updateCensorSelection)
    }
  })
</script>

<svelte:head>
  <title>Книга интернет сообщества — Tambur</title>
  <meta
    name="description"
    content="Мы люди из интернет-сообщества совместно напишем книгу о том, что думаем, видим, чувствуем - это полная свобода самовыражения."
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
  </div>
</Modal>

<Modal bind:open={cooldownOpen}>
  <span slot="title">Следующее слово можно добавить только через 24 часа</span>
  <div class="book-modal-content">
    {#if status?.next_available_at}
      <p>Следующее слово можно будет добавить {formatDate(status.next_available_at)}. Напомнить?</p>
    {:else}
      <p>Следующее слово можно будет добавить через 24 часа. Напомнить?</p>
    {/if}
    <div class="modal-actions">
      <Button color="secondary" on:click={() => (cooldownOpen = false)}>Не сейчас</Button>
      {#if reminderScheduled}
        <Button loading={reminderLoading} disabled={reminderLoading} on:click={cancelReminder}>
          <Icon src={Bell} size="18" mini slot="prefix" />
          {reminderToggleLabel}
        </Button>
      {:else if reminderDisabledNotice}
        <Button loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
          <Icon src={Bell} size="18" mini slot="prefix" />
          {reminderToggleLabel}
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
        <h1>Книга интернет сообщества</h1>
        <p>
          Мы люди из интернет-сообщества совместно напишем книгу о том, что думаем,
          видим, чувствуем - это полная свобода самовыражения. Книга будет длинной
          185 000 слов, что примерно 500 страниц. Каждый пользователь пишет только
          одно слово в сутки. Финальная версия будет опубликована в PDF и доступна
          всем, а также будет возможность для печати бумажной версии. Проводится
          проверка публикации на законность и контент может быть отцензурирован.
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
        {#if moderationLockedUntil}
          <div class="counter-note">
            Возможность добавить слово заблокирована до {formatDate(moderationLockedUntil)}.
          </div>
        {/if}
        {#if needsSocialLink}
          <div class="counter-note">
            Только пользователи с привязанным телеграм или вк могут писать эту книгу -
            <a href="/settings">привязать можно одной кнопкой в настройках</a>.
          </div>
        {/if}
        {#if canShowReminder}
          <div class="counter-reminder">
            {#if reminderScheduled}
              <Button color="secondary" loading={reminderLoading} disabled={reminderLoading} on:click={cancelReminder}>
                <Icon src={Bell} size="18" mini slot="prefix" />
                {reminderToggleLabel}
              </Button>
            {:else if reminderDisabledNotice}
              <Button color="secondary" loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
                <Icon src={Bell} size="18" mini slot="prefix" />
                {reminderToggleLabel}
              </Button>
            {:else if $siteUser?.telegram_linked}
              <Button color="secondary" loading={reminderLoading} disabled={reminderLoading} on:click={scheduleReminder}>
                <Icon src={Bell} size="18" mini slot="prefix" />
                {reminderToggleLabel}
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
      <section class="book-sheet" bind:this={bookSheetEl} aria-label="Текст книги">
        <div class="sheet-head">
          <span>Текущая версия</span>
          <span>{formatNumber(displayTotalWords)} из {formatNumber(displayMaxWords)}</span>
        </div>
        {#if $siteUser?.is_staff && selectedFragments.length}
          <button
            class="selection-censor-button"
            style={selectionCensorButtonStyle}
            type="button"
            disabled={selectionCensorLoading}
            title={selectedText ? `Зацензурить: ${selectedText}` : 'Зацензурить выделенный фрагмент'}
            on:mousedown|preventDefault={() => undefined}
            on:click={censorSelection}
          >
            {selectionCensorLoading ? '...' : 'Цензура'}
          </button>
        {/if}
        <div class="book-text">
          {#if words.length}
            <span
              class="book-words-flow"
              bind:this={bookWordsEl}
            >
              {#each words as item, index (item.id)}
                <span
                  class="book-word"
                  class:censored={item.is_censored}
                  data-book-word-id={item.id}
                  data-position={item.position}
                >{item.word}</span>{index < words.length - 1 ? ' ' : ''}
              {/each}
            </span>
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
              autocapitalize="none"
              spellcheck="false"
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
                type="submit"
                class="inline-submit"
                aria-label="Привязать Telegram или VK"
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
    max-width: none;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(20px, 7.4cqw, 64px);
    line-height: 0.94;
    letter-spacing: 0;
    white-space: nowrap;
  }

  .hero-copy {
    container-type: inline-size;
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

  :global(.dark) .book-modal-content {
    color: #f4efe6;
  }

  .book-modal-content p {
    margin: 0;
    white-space: pre-wrap;
  }

  .modal-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: flex-end;
  }

  .book-counter-panel {
    align-self: start;
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

  .book-sheet {
    position: relative;
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

  .book-words-flow {
    user-select: text;
  }

  .book-word {
    border-radius: 2px;
  }

  .book-word.censored {
    letter-spacing: 0;
  }

  .selection-censor-button {
    position: absolute;
    z-index: 5;
    display: inline-flex;
    min-width: 92px;
    min-height: 34px;
    align-items: center;
    justify-content: center;
    transform: translateX(-50%);
    border: 1px solid #111827;
    border-radius: 999px;
    background: #111827;
    box-shadow: 0 12px 28px rgba(17, 24, 39, 0.24);
    color: #fffdf8;
    font-size: 13px;
    font-weight: 800;
    padding: 7px 12px;
  }

  .selection-censor-button:hover:not(:disabled) {
    background: #9f2a22;
    border-color: #9f2a22;
  }

  .selection-censor-button:disabled {
    cursor: default;
    opacity: 0.65;
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

    .book-sheet {
      padding: 20px;
    }

    .inline-word-form {
      margin-left: 4px;
    }
  }

</style>
