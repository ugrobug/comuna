<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import {
    buildSpecialLandnameAdminGenerationsUrl,
    buildSpecialLandnameAdminLetterUrl,
    buildSpecialLandnameAdminLettersUrl,
    buildSpecialLandnameAdminSuggestionUrl,
    buildSpecialLandnameAdminSuggestionApproveUrl,
    buildSpecialLandnameShareUrl,
    buildSpecialLandnameSuggestionUrl,
    buildSpecialLandnameUrl,
  } from '$lib/api/backend'
  import {
    login as siteLogin,
    refreshSiteUser,
    register as siteRegister,
    siteToken,
    siteUser,
  } from '$lib/siteAuth'
  import {
    ArrowPath,
    ClipboardDocument,
    Icon,
    ListBullet,
    MapPin,
    PaperAirplane,
    PlusCircle,
    Photo,
    Share,
    Sparkles,
    Trash,
  } from 'svelte-hero-icons'
  import { onMount } from 'svelte'

  type LandnameItem = {
    id: number | string
    letter: string
    title: string
    location_name: string
    image_url: string
    map_url: string
    latitude: string
    longitude: string
    source_name: string
    source_url: string
    is_default?: boolean
    item_type?: 'letter'
    status?: string
    created_at?: string
    updated_at?: string
  }

  type AdminSuggestionItem = {
    id: number
    item_type: 'suggestion'
    status: 'pending' | 'approved' | 'rejected'
    letter: string
    title: string
    location_name: string
    image_url: string
    map_url: string
    coordinates: string
    latitude: string
    longitude: string
    submitted_by?: {
      id: number
      username: string
    }
    created_at: string
    updated_at: string
  }

  type AdminLandnameItem = LandnameItem | AdminSuggestionItem

  type RenderedLetter =
    | { type: 'space'; position: number }
    | { type: 'letter'; position: number; item: LandnameItem }

  type RenderedLandname = {
    ok: boolean
    project: string
    text: string
    letters: RenderedLetter[]
    share_query: string
    generation_id?: number | null
  }

  type AdminGeneratedPhrase = {
    id: number
    text: string
    share_query: string
    was_shared: boolean
    share_clicks: number
    shared_at: string | null
    generated_by?: {
      id: number
      username: string
    } | null
    created_at: string
    updated_at: string
  }

  const normalizeInput = (value: string) =>
    value
      .toUpperCase()
      .replace(/[^А-ЯЁ\s]/g, '')
      .replace(/\s+/g, ' ')
      .slice(0, 32)

  const encodeQueryText = (value: string) => encodeURIComponent(value).replace(/%20/g, '+')
  const normalizePublicSiteBaseUrl = (value: string): string => {
    const cleanValue = value.replace(/\/+$/, '')
    if (cleanValue === 'http://tambur.pub' || cleanValue === 'http://www.tambur.pub') {
      return cleanValue.replace('http://', 'https://')
    }
    return cleanValue
  }

  let inputText = 'КОМУНА'
  let rendered: RenderedLandname | null = null
  let loading = false
  let error = ''
  let copied = false

  let suggestionOpen = false
  let authMode: 'login' | 'register' = 'login'
  let authLoading = false
  let authError = ''
  let loginForm = {
    username: '',
    password: '',
  }
  let registerForm = {
    username: '',
    email: '',
    password: '',
    privacyAccepted: true,
  }
  let suggestionForm = {
    letter: '',
    mapUrl: '',
    coordinates: '',
    locationNote: '',
  }
  let suggestionLoading = false
  let suggestionError = ''
  let suggestionDone = false
  let adminLoadedForToken = ''
  let adminLetters: AdminLandnameItem[] = []
  let adminGenerations: AdminGeneratedPhrase[] = []
  let adminGenerationTotal = 0
  let adminGenerationSharedTotal = 0
  let adminPhrasesOpen = false
  let adminLoading = false
  let adminError = ''
  let adminDone = ''
  let adminForm = {
    letter: '',
    title: '',
    coordinates: '',
    mapUrl: '',
  }
  let adminImageFile: File | null = null
  let selectedSuggestion: AdminSuggestionItem | null = null
  let approvalForm = {
    title: '',
    coordinates: '',
    mapUrl: '',
  }
  let approvalImageFile: File | null = null

  $: pendingAdminCount = adminLetters.filter((item) => item.item_type === 'suggestion').length
  $: adminGenerationUnsharedTotal = Math.max(adminGenerationTotal - adminGenerationSharedTotal, 0)
  $: publicSiteBaseUrl = normalizePublicSiteBaseUrl(env.PUBLIC_SITE_URL || $page.url.origin)
  $: previewText = normalizeInput($page.url.searchParams.get('text') || rendered?.text || inputText || '').trim()
  $: previewTitleText = previewText || 'КОМУНА'
  $: landnamePageTitle = `${previewTitleText} — Имя на карте`
  $: landnameDescription = `Фраза «${previewTitleText}», собранная из спутниковых снимков.`
  $: landnameCanonicalUrl = `${publicSiteBaseUrl}/s/landname?text=${encodeQueryText(previewTitleText)}`
  $: landnamePreviewImageUrl = `${publicSiteBaseUrl}/api/special-projects/landname/preview.png?text=${encodeQueryText(previewTitleText)}`

  $: shareUrl =
    browser && rendered?.text
      ? `${window.location.origin}/s/landname?text=${encodeURIComponent(rendered.text)}`
      : ''
  $: if (browser && $siteUser?.is_staff && $siteToken && adminLoadedForToken !== $siteToken) {
    adminLoadedForToken = $siteToken
    loadAdminData()
  }

  const formatAdminDate = (value?: string | null) => {
    if (!value) return '—'
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(new Date(value))
    } catch {
      return value
    }
  }

  const loadLandname = async (options: { updateUrl?: boolean; track?: boolean } = {}) => {
    const text = normalizeInput(inputText)
    inputText = text
    error = ''
    copied = false
    if (!text) {
      rendered = null
      return
    }

    loading = true
    try {
      const response = await fetch(buildSpecialLandnameUrl(text, { track: options.track }), {
        cache: 'no-store',
        headers: $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {},
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось собрать слово')
      }
      rendered = data as RenderedLandname
      if (options.updateUrl && browser) {
        goto(`/s/landname?text=${encodeURIComponent(rendered.text)}`, {
          keepFocus: true,
          noScroll: true,
          replaceState: false,
        })
      }
      if (options.track && $siteUser?.is_staff) {
        loadAdminGenerations()
      }
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось собрать слово'
    } finally {
      loading = false
    }
  }

  const copyShareUrl = async () => {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      fetch(buildSpecialLandnameShareUrl(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...( $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}),
        },
        body: JSON.stringify({
          generation_id: rendered?.generation_id || null,
          text: rendered?.text || inputText,
        }),
      }).catch(() => undefined)
      if (rendered?.generation_id) {
        adminGenerations = adminGenerations.map((phrase) =>
          phrase.id === rendered?.generation_id
            ? {
                ...phrase,
                was_shared: true,
                share_clicks: phrase.share_clicks + 1,
                shared_at: new Date().toISOString(),
              }
            : phrase
        )
      }
      if ($siteUser?.is_staff) {
        loadAdminGenerations()
      }
      copied = true
    } catch {
      copied = false
    }
  }

  const handleLogin = async () => {
    authLoading = true
    authError = ''
    try {
      await siteLogin(loginForm.username, loginForm.password)
    } catch (err) {
      authError = err instanceof Error ? err.message : 'Не удалось войти'
    } finally {
      authLoading = false
    }
  }

  const handleRegister = async () => {
    authLoading = true
    authError = ''
    try {
      await siteRegister({
        username: registerForm.username,
        email: registerForm.email,
        password: registerForm.password,
        privacy_accepted: registerForm.privacyAccepted,
      })
    } catch (err) {
      authError = err instanceof Error ? err.message : 'Не удалось зарегистрироваться'
    } finally {
      authLoading = false
    }
  }

  const submitSuggestion = async () => {
    suggestionLoading = true
    suggestionError = ''
    suggestionDone = false
    try {
      const response = await fetch(buildSpecialLandnameSuggestionUrl(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...( $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}),
        },
        body: JSON.stringify({
          letter: suggestionForm.letter,
          map_url: suggestionForm.mapUrl,
          coordinates: suggestionForm.coordinates,
          location_note: suggestionForm.locationNote,
        }),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось отправить предложение')
      }
      suggestionDone = true
      suggestionForm = {
        letter: '',
        mapUrl: '',
        coordinates: '',
        locationNote: '',
      }
    } catch (err) {
      suggestionError = err instanceof Error ? err.message : 'Не удалось отправить предложение'
    } finally {
      suggestionLoading = false
    }
  }

  const loadAdminLetters = async () => {
    if (!$siteToken) return
    adminLoading = true
    adminError = ''
    try {
      const response = await fetch(buildSpecialLandnameAdminLettersUrl(), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось загрузить буквы')
      }
      adminLetters = data.letters || []
      if (selectedSuggestion && !adminLetters.some((item) => item.item_type === 'suggestion' && item.id === selectedSuggestion?.id)) {
        selectedSuggestion = null
      }
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось загрузить буквы'
    } finally {
      adminLoading = false
    }
  }

  const loadAdminGenerations = async () => {
    if (!$siteToken) return
    adminError = ''
    try {
      const response = await fetch(buildSpecialLandnameAdminGenerationsUrl(), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось загрузить статистику')
      }
      adminGenerations = data.generations || []
      adminGenerationTotal = data.total || 0
      adminGenerationSharedTotal = data.shared_total || 0
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось загрузить статистику'
    }
  }

  const loadAdminData = async () => {
    adminLoading = true
    try {
      await Promise.all([loadAdminLetters(), loadAdminGenerations()])
    } finally {
      adminLoading = false
    }
  }

  const createAdminLetter = async () => {
    if (!$siteToken) return
    if (!adminImageFile) {
      adminError = 'Загрузите картинку.'
      return
    }
    adminLoading = true
    adminError = ''
    adminDone = ''
    try {
      const formData = new FormData()
      formData.set('letter', adminForm.letter)
      formData.set('title', adminForm.title)
      formData.set('coordinates', adminForm.coordinates)
      formData.set('map_url', adminForm.mapUrl)
      formData.set('image', adminImageFile)
      const response = await fetch(buildSpecialLandnameAdminLettersUrl(), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
        body: formData,
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось добавить букву')
      }
      adminLetters = [...adminLetters, data.letter].sort((a, b) =>
        `${a.letter}-${a.id}`.localeCompare(`${b.letter}-${b.id}`)
      )
      adminForm = {
        letter: '',
        title: '',
        coordinates: '',
        mapUrl: '',
      }
      adminImageFile = null
      adminDone = 'Буква добавлена.'
      await loadLandname()
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось добавить букву'
    } finally {
      adminLoading = false
    }
  }

  const deleteAdminLetter = async (item: AdminLandnameItem) => {
    if (item.item_type === 'suggestion') return
    if (!$siteToken || typeof item.id !== 'number') return
    if (browser && !window.confirm(`Удалить букву ${item.letter}: ${item.title}?`)) return
    adminLoading = true
    adminError = ''
    adminDone = ''
    try {
      const response = await fetch(buildSpecialLandnameAdminLetterUrl(item.id), {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось удалить букву')
      }
      adminLetters = adminLetters.filter((letter) => letter.id !== item.id)
      adminDone = 'Буква удалена.'
      await loadLandname()
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось удалить букву'
    } finally {
      adminLoading = false
    }
  }

  const selectSuggestion = (item: AdminLandnameItem) => {
    if (item.item_type !== 'suggestion') return
    selectedSuggestion = item
    approvalForm = {
      title: item.location_name || '',
      coordinates:
        item.latitude && item.longitude
          ? `${item.latitude}, ${item.longitude}`
          : item.coordinates || '',
      mapUrl: item.map_url || '',
    }
    approvalImageFile = null
    adminDone = ''
    adminError = ''
  }

  const approveSelectedSuggestion = async () => {
    if (!$siteToken || !selectedSuggestion) return
    if (!approvalImageFile) {
      adminError = 'Загрузите картинку для одобрения.'
      return
    }
    adminLoading = true
    adminError = ''
    adminDone = ''
    try {
      const formData = new FormData()
      formData.set('title', approvalForm.title)
      formData.set('coordinates', approvalForm.coordinates)
      formData.set('map_url', approvalForm.mapUrl)
      formData.set('image', approvalImageFile)
      const response = await fetch(buildSpecialLandnameAdminSuggestionApproveUrl(selectedSuggestion.id), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
        body: formData,
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось одобрить предложение')
      }
      adminLetters = [
        ...adminLetters.filter(
          (item) => !(item.item_type === 'suggestion' && item.id === selectedSuggestion?.id)
        ),
        data.letter,
      ].sort((a, b) => `${a.letter}-${a.id}`.localeCompare(`${b.letter}-${b.id}`))
      selectedSuggestion = null
      approvalImageFile = null
      approvalForm = {
        title: '',
        coordinates: '',
        mapUrl: '',
      }
      adminDone = 'Предложение одобрено. Буква теперь видна пользователям.'
      await loadLandname()
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось одобрить предложение'
    } finally {
      adminLoading = false
    }
  }

  const deleteSelectedSuggestion = async () => {
    if (!$siteToken || !selectedSuggestion) return
    if (browser && !window.confirm(`Удалить предложение буквы ${selectedSuggestion.letter}?`)) return
    adminLoading = true
    adminError = ''
    adminDone = ''
    try {
      const response = await fetch(buildSpecialLandnameAdminSuggestionUrl(selectedSuggestion.id), {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось удалить предложение')
      }
      adminLetters = adminLetters.filter(
        (item) => !(item.item_type === 'suggestion' && item.id === selectedSuggestion?.id)
      )
      selectedSuggestion = null
      approvalImageFile = null
      approvalForm = {
        title: '',
        coordinates: '',
        mapUrl: '',
      }
      adminDone = 'Предложение удалено.'
    } catch (err) {
      adminError = err instanceof Error ? err.message : 'Не удалось удалить предложение'
    } finally {
      adminLoading = false
    }
  }

  onMount(() => {
    const fromQuery = $page.url.searchParams.get('text')
    inputText = normalizeInput(fromQuery || inputText)
    loadLandname()
    refreshSiteUser()
  })

  const onAdminImageChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement
    adminImageFile = input.files?.[0] || null
  }

  const onApprovalImageChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement
    approvalImageFile = input.files?.[0] || null
  }
</script>

<svelte:head>
  <title>{landnamePageTitle}</title>
  <meta name="description" content={landnameDescription} />
  <link rel="canonical" href={landnameCanonicalUrl} />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Tambur" />
  <meta property="og:title" content={landnamePageTitle} />
  <meta property="og:description" content={landnameDescription} />
  <meta property="og:url" content={landnameCanonicalUrl} />
  <meta property="og:image" content={landnamePreviewImageUrl} />
  <meta property="og:image:secure_url" content={landnamePreviewImageUrl} />
  <meta property="og:image:type" content="image/png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={landnamePageTitle} />
  <meta name="twitter:description" content={landnameDescription} />
  <meta name="twitter:image" content={landnamePreviewImageUrl} />
</svelte:head>

<section class="landname-page">
  <div class="hero">
    <div class="hero-copy">
      <h1>Имя на карте</h1>
      <p>
        Введите слово на русском, а мы соберём его из спутниковых снимков
      </p>
    </div>
  </div>

  {#if error}
    <div class="notice error">{error}</div>
  {/if}

  {#if rendered?.letters?.length}
    <div
      class="word-strip"
      aria-label={`Слово ${rendered.text}`}
      style={`grid-template-columns: repeat(${rendered.letters.length}, minmax(0, 1fr));`}
    >
      {#each rendered.letters as letter}
        {#if letter.type === 'space'}
          <div class="space-tile" aria-hidden="true"></div>
        {:else}
          <article class="letter-card">
            <div class="letter-image-wrap">
              <img src={letter.item.image_url} alt={`Буква ${letter.item.letter}: ${letter.item.location_name}`} />
            </div>
            <div class="letter-info">
              <h2>{letter.item.location_name || letter.item.title}</h2>
              <a href={letter.item.map_url} target="_blank" rel="noreferrer">
                <Icon src={MapPin} mini size="15" />
                {letter.item.latitude}, {letter.item.longitude}
              </a>
            </div>
          </article>
        {/if}
      {/each}
    </div>
  {/if}

  <form class="composer" on:submit|preventDefault={() => loadLandname({ updateUrl: true, track: true })}>
    <label for="landname-input">Слово кириллицей</label>
    <div class="input-row">
      <input
        id="landname-input"
        bind:value={inputText}
        maxlength="32"
        placeholder="КОМУНА"
        inputmode="text"
        on:input={() => (inputText = normalizeInput(inputText))}
      />
      <button class="primary-button compact-button" type="submit" disabled={loading || !inputText.trim()}>
        {#if loading}
          <Icon src={ArrowPath} mini size="16" />
        {:else}
          <Icon src={Sparkles} mini size="16" />
        {/if}
        Собрать
      </button>
    </div>
    <div class="actions">
      <button class="ghost-button compact-button" type="button" on:click={copyShareUrl} disabled={!shareUrl}>
        <Icon src={Share} mini size="15" />
        {copied ? 'Скопировано' : 'Поделиться'}
      </button>
      <button class="ghost-button compact-button" type="button" on:click={() => (suggestionOpen = !suggestionOpen)}>
        <Icon src={PlusCircle} mini size="15" />
        Добавить букву
      </button>
    </div>
  </form>

  {#if $siteUser?.is_staff}
    <section class="admin-panel">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">Админка</p>
          <h2>Буквы на карте</h2>
        </div>
        <button class="ghost-button compact" type="button" on:click={loadAdminData} disabled={adminLoading}>
          <Icon src={ListBullet} mini size="17" />
          Обновить
        </button>
      </div>

      <form class="admin-form" on:submit|preventDefault={createAdminLetter}>
        <div class="admin-form-grid">
          <label>
            Буква
            <input
              bind:value={adminForm.letter}
              maxlength="1"
              placeholder="А"
              required
              on:input={() => (adminForm.letter = normalizeInput(adminForm.letter).slice(0, 1))}
            />
          </label>
          <label>
            Название
            <input bind:value={adminForm.title} maxlength="160" placeholder="Дельта Лены" required />
          </label>
          <label>
            GPS
            <input bind:value={adminForm.coordinates} placeholder="72.000000, 128.500000" required />
          </label>
        </div>
        <label>
          Картинка
          <input type="file" accept="image/*" on:change={onAdminImageChange} required />
        </label>
        <label>
          Ссылка на карту
          <input bind:value={adminForm.mapUrl} placeholder="Необязательно, если GPS указан" />
        </label>
        <button class="primary-button" type="submit" disabled={adminLoading}>
          <Icon src={Photo} mini size="17" />
          Добавить букву
        </button>
      </form>

      {#if adminDone}
        <div class="notice success">{adminDone}</div>
      {/if}
      {#if adminError}
        <div class="notice error">{adminError}</div>
      {/if}

      <div class="admin-list-header">
        <h3>Все буквы</h3>
        <div class="admin-counters">
          {#if pendingAdminCount}
            <span class="pending-counter">{pendingAdminCount} на модерации</span>
          {/if}
          <span>{adminLetters.length}</span>
        </div>
      </div>
      {#if adminLetters.length}
        <div class="admin-letter-list">
          {#each adminLetters as item}
            <article
              class:admin-letter-row--pending={item.item_type === 'suggestion'}
              class="admin-letter-row"
            >
              {#if item.image_url}
                <img src={item.image_url} alt={`Буква ${item.letter}: ${item.title}`} />
              {:else}
                <div class="admin-letter-placeholder">
                  <Icon src={Photo} mini size="20" />
                </div>
              {/if}
              <div class="admin-letter-main">
                <div class="admin-letter-title">
                  {#if item.item_type === 'suggestion'}
                    <button class="admin-letter-badge-button" type="button" on:click={() => selectSuggestion(item)}>
                      {item.letter}
                    </button>
                  {:else}
                    <strong>{item.letter}</strong>
                  {/if}
                  <span>{item.title}</span>
                  {#if item.item_type === 'suggestion'}
                    <em>На модерации</em>
                  {/if}
                </div>
                {#if item.map_url}
                  <a href={item.map_url} target="_blank" rel="noreferrer">
                    {item.latitude && item.longitude ? `${item.latitude}, ${item.longitude}` : item.map_url}
                  </a>
                {:else if item.latitude && item.longitude}
                  <span class="admin-letter-muted">{item.latitude}, {item.longitude}</span>
                {/if}
                {#if item.item_type === 'suggestion' && item.submitted_by?.username}
                  <span class="admin-letter-muted">Предложил: @{item.submitted_by.username}</span>
                {/if}
              </div>
              {#if item.item_type === 'suggestion'}
                <button class="ghost-button compact-button" type="button" on:click|stopPropagation={() => selectSuggestion(item)} disabled={adminLoading}>
                  Открыть
                </button>
              {:else}
                <button class="danger-button" type="button" on:click|stopPropagation={() => deleteAdminLetter(item)} disabled={adminLoading}>
                  <Icon src={Trash} mini size="17" />
                  Удалить
                </button>
              {/if}
            </article>
          {/each}
        </div>
      {:else}
        <div class="empty-state">Пока нет добавленных вручную букв и предложений. Используются встроенные заглушки.</div>
      {/if}

      {#if selectedSuggestion}
        <form class="approval-panel" on:submit|preventDefault={approveSelectedSuggestion}>
          <div class="panel-heading">
            <div>
              <p class="eyebrow">Модерация</p>
              <h2>Буква {selectedSuggestion.letter}</h2>
            </div>
            <button class="icon-button" type="button" on:click={() => (selectedSuggestion = null)} aria-label="Закрыть">
              ×
            </button>
          </div>
          <div class="suggestion-details">
            <div>
              <span>Предложение</span>
              <strong>{selectedSuggestion.location_name || 'Без описания'}</strong>
            </div>
            {#if selectedSuggestion.submitted_by?.username}
              <div>
                <span>Автор</span>
                <strong>@{selectedSuggestion.submitted_by.username}</strong>
              </div>
            {/if}
            {#if selectedSuggestion.map_url}
              <a href={selectedSuggestion.map_url} target="_blank" rel="noreferrer">Открыть карту</a>
            {/if}
          </div>
          <div class="admin-form-grid">
            <label>
              Название
              <input bind:value={approvalForm.title} maxlength="160" placeholder="Правый приток Оби" required />
            </label>
            <label>
              GPS
              <input bind:value={approvalForm.coordinates} placeholder="72.000000, 128.500000" required />
            </label>
          </div>
          <label>
            Картинка
            <input type="file" accept="image/*" on:change={onApprovalImageChange} required />
          </label>
          <label>
            Ссылка на карту
            <input bind:value={approvalForm.mapUrl} placeholder="Необязательно, если GPS указан" />
          </label>
          <div class="approval-actions">
            <button class="primary-button" type="submit" disabled={adminLoading}>
              <Icon src={Photo} mini size="17" />
              Сохранить и опубликовать
            </button>
            <button class="danger-button" type="button" on:click={deleteSelectedSuggestion} disabled={adminLoading}>
              <Icon src={Trash} mini size="17" />
              Удалить
            </button>
          </div>
        </form>
      {/if}

      <section class="generation-panel">
        <div class="admin-list-header">
          <div>
            <h3>Сгенерированные фразы</h3>
            <p>{adminGenerationTotal} всего, {adminGenerationSharedTotal} поделились, {adminGenerationUnsharedTotal} без share</p>
          </div>
          <button class="ghost-button compact-button" type="button" on:click={() => (adminPhrasesOpen = !adminPhrasesOpen)}>
            <Icon src={ListBullet} mini size="16" />
            {adminPhrasesOpen ? 'Скрыть список' : 'Открыть список'}
          </button>
        </div>
        {#if adminPhrasesOpen}
          {#if adminGenerations.length}
            <div class="generation-list">
              {#each adminGenerations as phrase}
                <article class="generation-row">
                  <div class="generation-main">
                    <strong>{phrase.text}</strong>
                    <span>
                      {formatAdminDate(phrase.created_at)}
                      {#if phrase.generated_by?.username}
                        · @{phrase.generated_by.username}
                      {/if}
                    </span>
                  </div>
                  <div class="generation-share-status" class:generation-share-status--shared={phrase.was_shared}>
                    {phrase.was_shared ? 'Поделились' : 'Не делились'}
                    {#if phrase.share_clicks > 1}
                      · {phrase.share_clicks}
                    {/if}
                  </div>
                  <span class="generation-shared-at">{phrase.was_shared ? formatAdminDate(phrase.shared_at) : '—'}</span>
                </article>
              {/each}
            </div>
          {:else}
            <div class="empty-state">Пока нет сгенерированных фраз.</div>
          {/if}
        {/if}
      </section>
    </section>
  {/if}

  {#if suggestionOpen}
    <div class="modal-layer">
    <div class="suggestion-panel modal-panel" role="dialog" aria-modal="true" aria-labelledby="suggestion-modal-title">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">База букв</p>
          <h2 id="suggestion-modal-title">Предложить свою находку</h2>
        </div>
        <button class="icon-button" type="button" on:click={() => (suggestionOpen = false)} aria-label="Закрыть">
          ×
        </button>
      </div>

      {#if !$siteUser}
        <div class="auth-grid">
          <div class="auth-tabs">
            <button class:active={authMode === 'login'} type="button" on:click={() => (authMode = 'login')}>
              Войти
            </button>
            <button class:active={authMode === 'register'} type="button" on:click={() => (authMode = 'register')}>
              Регистрация
            </button>
          </div>

          {#if authMode === 'login'}
            <form class="stack-form" on:submit|preventDefault={handleLogin}>
              <input bind:value={loginForm.username} placeholder="Логин или email" autocomplete="username" required />
              <input bind:value={loginForm.password} placeholder="Пароль" type="password" autocomplete="current-password" required />
              <button class="primary-button" type="submit" disabled={authLoading}>
                <Icon src={ClipboardDocument} mini size="17" />
                Войти
              </button>
            </form>
          {:else}
            <form class="stack-form" on:submit|preventDefault={handleRegister}>
              <input bind:value={registerForm.username} placeholder="Имя пользователя" autocomplete="username" required />
              <input bind:value={registerForm.email} placeholder="Email" type="email" autocomplete="email" required />
              <input bind:value={registerForm.password} placeholder="Пароль" type="password" minlength="8" autocomplete="new-password" required />
              <label class="checkbox-row">
                <input type="checkbox" bind:checked={registerForm.privacyAccepted} />
                Согласен с обработкой данных
              </label>
              <button class="primary-button" type="submit" disabled={authLoading || !registerForm.privacyAccepted}>
                <Icon src={ClipboardDocument} mini size="17" />
                Зарегистрироваться
              </button>
            </form>
          {/if}

          {#if authError}
            <div class="notice error">{authError}</div>
          {/if}
        </div>
      {:else}
        <form class="suggestion-form" on:submit|preventDefault={submitSuggestion}>
          <div class="form-grid">
            <label>
              Буква
              <input
                bind:value={suggestionForm.letter}
                maxlength="1"
                placeholder="А"
                required
                on:input={() => (suggestionForm.letter = normalizeInput(suggestionForm.letter).slice(0, 1))}
              />
            </label>
            <label>
              GPS
              <input bind:value={suggestionForm.coordinates} placeholder="55.751244, 37.618423" />
            </label>
          </div>
          <label>
            Ссылка на карту
            <input bind:value={suggestionForm.mapUrl} placeholder="https://maps.google.com/..." />
          </label>
          <label>
            Что это за место
            <input bind:value={suggestionForm.locationNote} maxlength="280" placeholder="Например: Правый приток Оби \ Дорога в Лен. области" />
          </label>
          <button class="primary-button" type="submit" disabled={suggestionLoading}>
            <Icon src={PaperAirplane} mini size="17" />
            Отправить на модерацию
          </button>
          {#if suggestionDone}
            <div class="notice success">Спасибо. Предложение отправлено на модерацию.</div>
          {/if}
          {#if suggestionError}
            <div class="notice error">{suggestionError}</div>
          {/if}
        </form>
      {/if}
    </div>
    </div>
  {/if}
</section>

<style>
  .landname-page {
    min-height: 100vh;
    padding: 0.2rem 1rem 4rem;
    color: #0f172a;
    background-color: rgb(var(--c-s-50, 248 250 252) / 0.8);
  }

  :global(.dark) .landname-page {
    color: #f8fafc;
    background-color: #09090b;
  }

  .hero,
  .word-strip,
  .composer,
  .admin-panel,
  .suggestion-panel,
  .notice {
    width: min(1180px, 100%);
    margin: 0 auto;
  }

  .hero {
    display: block;
  }

  .hero-copy {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
    padding: 0 0.15rem;
    text-align: center;
  }

  .eyebrow {
    display: inline-flex;
    width: max-content;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
    color: #ea580c;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  :global(.dark) .eyebrow {
    color: #fdba74;
  }

  h1 {
    max-width: 720px;
    margin: 0;
    font-size: clamp(1.15rem, 2.04vw, 1.8rem);
    line-height: 1.12;
    letter-spacing: 0;
  }

  .hero-copy p {
    max-width: 560px;
    margin: 0;
    color: #64748b;
    font-size: 0.82rem;
    line-height: 1.45;
  }

  :global(.dark) .hero-copy p {
    color: #cbd5e1;
  }

  .composer,
  .admin-panel,
  .suggestion-panel {
    border: 1px solid rgba(148, 163, 184, 0.26);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 14px 45px rgba(15, 23, 42, 0.08);
    backdrop-filter: blur(18px);
  }

  :global(.dark) .composer,
  :global(.dark) .admin-panel,
  :global(.dark) .suggestion-panel {
    border-color: rgba(63, 63, 70, 0.7);
    background: rgba(24, 24, 27, 0.86);
    box-shadow: 0 14px 45px rgba(0, 0, 0, 0.28);
  }

  .composer {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    width: min(760px, 100%);
    margin-top: 0.85rem;
    padding: 0.75rem;
    border-radius: 8px;
  }

  .composer label,
  .admin-form label,
  .suggestion-form label {
    color: #475569;
    font-size: 0.82rem;
    font-weight: 800;
  }

  :global(.dark) .composer label,
  :global(.dark) .admin-form label,
  :global(.dark) .suggestion-form label {
    color: #a1a1aa;
  }

  .input-row,
  .actions {
    display: flex;
    gap: 0.45rem;
  }

  input {
    min-width: 0;
    width: 100%;
    height: 2.5rem;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 0 0.9rem;
    color: #0f172a;
    background: #f8fafc;
    font: inherit;
    outline: none;
  }

  input:focus {
    border-color: #f97316;
    box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.16);
  }

  :global(.dark) input {
    border-color: #3f3f46;
    color: #f8fafc;
    background: #09090b;
  }

  .primary-button,
  .ghost-button,
  .danger-button,
  .icon-button,
  .auth-tabs button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.45rem;
    min-height: 2.5rem;
    border: 0;
    border-radius: 8px;
    padding: 0 1rem;
    font: inherit;
    font-weight: 800;
    cursor: pointer;
    transition: transform 160ms ease, opacity 160ms ease, background 160ms ease;
  }

  .primary-button {
    flex: 0 0 auto;
    color: white;
    background: #ea580c;
  }

  .primary-button:hover:not(:disabled) {
    background: #c2410c;
  }

  .ghost-button,
  .auth-tabs button {
    color: #334155;
    border: 1px solid rgba(148, 163, 184, 0.25);
    background: rgba(241, 245, 249, 0.92);
  }

  :global(.dark) .ghost-button,
  :global(.dark) .auth-tabs button {
    color: #e4e4e7;
    border-color: rgba(63, 63, 70, 0.72);
    background: rgba(63, 63, 70, 0.72);
  }

  .danger-button {
    color: #991b1b;
    background: #fee2e2;
  }

  :global(.dark) .danger-button {
    color: #fecaca;
    background: rgba(127, 29, 29, 0.5);
  }

  .compact {
    min-height: 2.5rem;
  }

  .compact-button {
    min-height: 2.25rem;
    padding: 0 0.75rem;
    font-size: 0.84rem;
  }

  button:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.58;
  }

  .word-strip {
    display: grid;
    gap: clamp(0.18rem, 0.8vw, 0.75rem);
    margin-top: 1rem;
    padding: clamp(0.25rem, 0.8vw, 0.75rem);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.56);
    backdrop-filter: blur(14px);
    overflow: hidden;
  }

  :global(.dark) .word-strip {
    border-color: rgba(63, 63, 70, 0.6);
    background: rgba(9, 9, 11, 0.36);
  }

  .letter-card {
    overflow: hidden;
    min-width: 0;
    border: 1px solid rgba(148, 163, 184, 0.28);
    border-radius: 8px;
    background: white;
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
    transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
  }

  .letter-card:hover {
    border-color: rgba(249, 115, 22, 0.5);
    box-shadow: 0 14px 28px rgba(15, 23, 42, 0.1);
    transform: translateY(-2px);
  }

  :global(.dark) .letter-card {
    border-color: rgba(63, 63, 70, 0.72);
    background: #18181b;
  }

  .letter-image-wrap {
    position: relative;
    aspect-ratio: 5 / 8;
    background: #0f172a;
  }

  .letter-image-wrap img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .letter-info {
    display: flex;
    min-width: 0;
    min-height: clamp(3.2rem, 7vw, 5.45rem);
    flex-direction: column;
    gap: clamp(0.25rem, 0.55vw, 0.65rem);
    padding: clamp(0.28rem, 0.7vw, 0.65rem);
  }

  .letter-info h2 {
    margin: 0;
    overflow: hidden;
    color: #64748b;
    font-size: clamp(0.58rem, 0.92vw, 0.88rem);
    font-weight: 400;
    line-height: 1.25;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.dark) .letter-info h2 {
    color: #a1a1aa;
  }

  .letter-info a {
    display: inline-flex;
    min-width: 0;
    align-items: center;
    gap: 0.3rem;
    color: #0f172a;
    overflow: hidden;
    font-size: clamp(0.52rem, 0.82vw, 0.76rem);
    text-decoration: none;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .letter-info a :global(svg) {
    flex: 0 0 auto;
  }

  :global(.dark) .letter-info a {
    color: #f8fafc;
  }

  .space-tile {
    min-height: 1px;
  }

  .modal-layer {
    position: fixed;
    inset: 0;
    z-index: 1200;
    display: grid;
    place-items: center;
    padding: 1rem;
    background: rgba(15, 23, 42, 0.42);
    backdrop-filter: blur(8px);
  }

  :global(.dark) .modal-layer {
    background: rgba(0, 0, 0, 0.58);
  }

  .modal-layer .suggestion-panel {
    width: min(560px, 100%);
    max-height: min(720px, calc(100vh - 2rem));
    margin: 0;
    overflow: auto;
    box-shadow: 0 24px 80px rgba(15, 23, 42, 0.24);
  }

  .suggestion-panel,
  .admin-panel,
  .notice {
    margin-top: 1.1rem;
    border-radius: 8px;
  }

  .admin-panel,
  .suggestion-panel {
    padding: 1rem;
  }

  .panel-heading {
    display: flex;
    align-items: start;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1rem;
  }

  .panel-heading h2 {
    margin: 0.2rem 0 0;
    font-size: 1.5rem;
    letter-spacing: 0;
  }

  .icon-button {
    width: 2.5rem;
    min-height: 2.5rem;
    padding: 0;
    color: #475569;
    background: transparent;
    font-size: 1.8rem;
    line-height: 1;
  }

  .auth-grid,
  .stack-form,
  .admin-form,
  .suggestion-form {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }

  .auth-tabs {
    display: flex;
    width: max-content;
    gap: 0.35rem;
    padding: 0.25rem;
    border-radius: 8px;
    background: rgba(226, 232, 240, 0.62);
  }

  :global(.dark) .auth-tabs {
    background: rgba(39, 39, 42, 0.7);
  }

  .auth-tabs button.active {
    color: white;
    background: #ea580c;
  }

  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .checkbox-row input {
    width: 1rem;
    height: 1rem;
  }

  .form-grid {
    display: grid;
    grid-template-columns: minmax(90px, 0.28fr) minmax(0, 1fr);
    gap: 0.8rem;
  }

  .suggestion-form label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .admin-form label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .approval-panel label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    color: #475569;
    font-size: 0.82rem;
    font-weight: 800;
  }

  :global(.dark) .approval-panel label {
    color: #a1a1aa;
  }

  .admin-form-grid {
    display: grid;
    grid-template-columns: minmax(80px, 0.22fr) minmax(0, 1fr) minmax(220px, 0.8fr);
    gap: 0.8rem;
  }

  .admin-list-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(148, 163, 184, 0.24);
  }

  .admin-list-header h3 {
    margin: 0;
    font-size: 1rem;
  }

  .admin-list-header p {
    margin: 0.25rem 0 0;
    color: #64748b;
    font-size: 0.84rem;
    font-weight: 700;
  }

  :global(.dark) .admin-list-header p {
    color: #a1a1aa;
  }

  .admin-counters {
    display: flex;
    align-items: center;
    gap: 0.45rem;
  }

  .admin-list-header span {
    display: grid;
    place-items: center;
    min-width: 2rem;
    height: 2rem;
    border-radius: 8px;
    color: #9a3412;
    background: rgba(249, 115, 22, 0.12);
    font-weight: 900;
  }

  .admin-list-header .pending-counter {
    width: auto;
    padding: 0 0.65rem;
    color: #854d0e;
    background: #fef3c7;
    font-size: 0.78rem;
  }

  :global(.dark) .admin-list-header span {
    color: #fdba74;
    background: rgba(249, 115, 22, 0.16);
  }

  :global(.dark) .admin-list-header .pending-counter {
    color: #fde68a;
    background: rgba(113, 63, 18, 0.58);
  }

  .admin-letter-list {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    margin-top: 0.8rem;
  }

  .admin-letter-row {
    display: grid;
    grid-template-columns: 4.5rem minmax(0, 1fr) auto;
    gap: 0.8rem;
    align-items: center;
    padding: 0.55rem;
    border: 1px solid rgba(148, 163, 184, 0.26);
    border-radius: 8px;
    background: rgba(248, 250, 252, 0.72);
  }

  .admin-letter-row--pending {
    cursor: pointer;
    border-color: rgba(245, 158, 11, 0.45);
    background: rgba(255, 251, 235, 0.78);
  }

  .admin-letter-row--pending:hover {
    border-color: rgba(217, 119, 6, 0.72);
    box-shadow: 0 10px 24px rgba(120, 53, 15, 0.1);
  }

  :global(.dark) .admin-letter-row {
    border-color: rgba(63, 63, 70, 0.68);
    background: rgba(9, 9, 11, 0.45);
  }

  :global(.dark) .admin-letter-row--pending {
    border-color: rgba(245, 158, 11, 0.42);
    background: rgba(69, 26, 3, 0.42);
  }

  .admin-letter-row img {
    width: 4.5rem;
    aspect-ratio: 3 / 4;
    border-radius: 8px;
    object-fit: cover;
    background: #0f172a;
  }

  .admin-letter-placeholder {
    display: grid;
    place-items: center;
    width: 4.5rem;
    aspect-ratio: 3 / 4;
    border-radius: 8px;
    color: #92400e;
    background: #fef3c7;
  }

  :global(.dark) .admin-letter-placeholder {
    color: #fde68a;
    background: rgba(113, 63, 18, 0.5);
  }

  .admin-letter-main {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.25rem;
  }

  .admin-letter-title {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 0.5rem;
  }

  .admin-letter-title strong,
  .admin-letter-badge-button {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border: 0;
    border-radius: 8px;
    color: white;
    background: #ea580c;
    flex: 0 0 auto;
    font: inherit;
    font-weight: 800;
  }

  .admin-letter-badge-button {
    cursor: pointer;
  }

  .admin-letter-badge-button:hover {
    background: #c2410c;
  }

  .admin-letter-title span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 800;
  }

  .admin-letter-title em {
    flex: 0 0 auto;
    border-radius: 999px;
    padding: 0.18rem 0.45rem;
    color: #854d0e;
    background: #fef3c7;
    font-size: 0.72rem;
    font-style: normal;
    font-weight: 800;
  }

  :global(.dark) .admin-letter-title em {
    color: #fde68a;
    background: rgba(113, 63, 18, 0.58);
  }

  .admin-letter-main a {
    color: #ea580c;
    font-size: 0.86rem;
    text-decoration: none;
  }

  .admin-letter-muted {
    color: #64748b;
    font-size: 0.82rem;
  }

  :global(.dark) .admin-letter-main a {
    color: #fdba74;
  }

  :global(.dark) .admin-letter-muted {
    color: #a1a1aa;
  }

  .approval-panel {
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    margin-top: 1rem;
    padding: 1rem;
    border: 1px solid rgba(245, 158, 11, 0.42);
    border-radius: 8px;
    background: rgba(255, 251, 235, 0.62);
  }

  :global(.dark) .approval-panel {
    border-color: rgba(245, 158, 11, 0.34);
    background: rgba(69, 26, 3, 0.26);
  }

  .approval-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    align-items: center;
  }

  .generation-panel {
    margin-top: 1rem;
  }

  .generation-list {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.8rem;
  }

  .generation-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(8rem, auto);
    gap: 0.75rem;
    align-items: center;
    padding: 0.75rem;
    border: 1px solid rgba(148, 163, 184, 0.26);
    border-radius: 8px;
    background: rgba(248, 250, 252, 0.72);
  }

  :global(.dark) .generation-row {
    border-color: rgba(63, 63, 70, 0.68);
    background: rgba(9, 9, 11, 0.45);
  }

  .generation-main {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.18rem;
  }

  .generation-main strong {
    min-width: 0;
    overflow: hidden;
    color: #0f172a;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.dark) .generation-main strong {
    color: #f8fafc;
  }

  .generation-main span,
  .generation-shared-at {
    color: #64748b;
    font-size: 0.82rem;
    font-weight: 700;
  }

  :global(.dark) .generation-main span,
  :global(.dark) .generation-shared-at {
    color: #a1a1aa;
  }

  .generation-share-status {
    justify-self: end;
    border-radius: 999px;
    padding: 0.22rem 0.55rem;
    color: #475569;
    background: rgba(226, 232, 240, 0.84);
    font-size: 0.78rem;
    font-weight: 900;
    white-space: nowrap;
  }

  .generation-share-status--shared {
    color: #166534;
    background: #dcfce7;
  }

  :global(.dark) .generation-share-status {
    color: #d4d4d8;
    background: rgba(63, 63, 70, 0.72);
  }

  :global(.dark) .generation-share-status--shared {
    color: #bbf7d0;
    background: rgba(20, 83, 45, 0.58);
  }

  .suggestion-details {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 0.7rem;
    align-items: center;
    padding: 0.75rem;
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.68);
  }

  :global(.dark) .suggestion-details {
    background: rgba(9, 9, 11, 0.32);
  }

  .suggestion-details div {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.15rem;
  }

  .suggestion-details span {
    color: #64748b;
    font-size: 0.72rem;
    font-weight: 800;
    text-transform: uppercase;
  }

  .suggestion-details strong {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .suggestion-details a {
    color: #ea580c;
    font-weight: 800;
    text-decoration: none;
  }

  .empty-state {
    margin-top: 0.8rem;
    padding: 1rem;
    border: 1px dashed rgba(148, 163, 184, 0.5);
    border-radius: 8px;
    color: #64748b;
    font-weight: 700;
  }

  .notice {
    padding: 0.8rem 1rem;
    font-weight: 700;
  }

  .notice.error {
    color: #991b1b;
    background: #fee2e2;
  }

  .notice.success {
    color: #14532d;
    background: #dcfce7;
  }

  @media (max-width: 820px) {
    .landname-page {
      padding-top: 0.2rem;
    }

    .hero {
      grid-template-columns: 1fr;
    }

    .input-row,
    .actions {
      flex-direction: column;
    }

    .primary-button,
    .ghost-button,
    .danger-button {
      width: 100%;
    }

    .form-grid {
      grid-template-columns: 1fr;
    }

    .admin-form-grid,
    .admin-letter-row,
    .generation-row {
      grid-template-columns: 1fr;
    }

    .generation-share-status,
    .generation-shared-at {
      justify-self: start;
    }

    .admin-letter-row img {
      width: 100%;
      max-height: 18rem;
    }
  }
</style>
