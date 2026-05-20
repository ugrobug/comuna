<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildSpecialBookAdminBlockedWordUrl,
    buildSpecialBookAdminBlockedWordsUrl,
    buildSpecialBookAdminSettingsUrl,
    buildSpecialBookAdminStatsUrl,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { ArrowPath, Check, Icon, Trash } from 'svelte-hero-icons'

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

  type BookSettings = {
    ok: boolean
    rules_text: string
    final_pdf?: {
      available: boolean
      url?: string | null
      uploaded_at?: string | null
      announced_at?: string | null
    }
  }

  type BlockedWord = {
    id: number
    word: string
    normalized_word: string
    is_active: boolean
    note: string
    created_at: string
    updated_at: string
  }

  let loading = true
  let savingRules = false
  let uploadingPdf = false
  let savingBlocked = false
  let error = ''
  let stats: BookAdminStats | null = null
  let settings: BookSettings | null = null
  let rulesDraft = ''
  let finalPdfFile: File | null = null
  let blockedWords: BlockedWord[] = []
  let blockedDraft = {
    word: '',
    note: '',
    is_active: true,
  }
  let rowSaving: Record<number, boolean> = {}

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  const formatNumber = (value?: number | null) =>
    new Intl.NumberFormat('ru-RU').format(value ?? 0)

  const formatDate = (value?: string | null) => {
    if (!value) return 'не загружен'
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
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

  async function fetchJson<T>(url: string, options: RequestInit = {}) {
    const response = await fetch(url, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.headers || {}),
        ...authHeaders(),
      },
    })
    const data = (await response.json()) as T & { ok?: boolean; error?: string }
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || 'Не удалось загрузить данные')
    }
    return data
  }

  async function loadAdmin() {
    loading = true
    error = ''
    try {
      const [statsData, settingsData, blockedData] = await Promise.all([
        fetchJson<BookAdminStats>(buildSpecialBookAdminStatsUrl()),
        fetchJson<BookSettings>(buildSpecialBookAdminSettingsUrl()),
        fetchJson<{ ok: boolean; blocked_words: BlockedWord[] }>(buildSpecialBookAdminBlockedWordsUrl()),
      ])
      stats = statsData
      settings = settingsData
      rulesDraft = settingsData.rules_text || ''
      blockedWords = blockedData.blocked_words || []
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить управление книгой'
    } finally {
      loading = false
    }
  }

  async function saveRules() {
    savingRules = true
    error = ''
    try {
      const data = await fetchJson<BookSettings>(buildSpecialBookAdminSettingsUrl(), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rules_text: rulesDraft }),
      })
      settings = data
      rulesDraft = data.rules_text || ''
      toast({ content: 'Правила сохранены', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить правила'
    } finally {
      savingRules = false
    }
  }

  function setFinalPdfFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    finalPdfFile = input.files?.[0] ?? null
  }

  async function uploadFinalPdf() {
    if (!finalPdfFile) {
      toast({ content: 'Выберите PDF-файл', type: 'info' })
      return
    }
    uploadingPdf = true
    error = ''
    try {
      const form = new FormData()
      form.set('rules_text', rulesDraft)
      form.set('final_pdf', finalPdfFile)
      const data = await fetchJson<BookSettings>(buildSpecialBookAdminSettingsUrl(), {
        method: 'PATCH',
        body: form,
      })
      settings = data
      finalPdfFile = null
      toast({ content: 'Финальный PDF загружен', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить PDF'
    } finally {
      uploadingPdf = false
    }
  }

  async function createBlockedWord() {
    savingBlocked = true
    error = ''
    try {
      const data = await fetchJson<{ ok: boolean; blocked_word: BlockedWord }>(
        buildSpecialBookAdminBlockedWordsUrl(),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(blockedDraft),
        },
      )
      blockedWords = [
        data.blocked_word,
        ...blockedWords.filter((item) => item.id !== data.blocked_word.id),
      ]
      blockedDraft = { word: '', note: '', is_active: true }
      toast({ content: 'Запрещенное выражение сохранено', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить запрещенное выражение'
    } finally {
      savingBlocked = false
    }
  }

  async function saveBlockedWord(item: BlockedWord) {
    rowSaving = { ...rowSaving, [item.id]: true }
    error = ''
    try {
      const data = await fetchJson<{ ok: boolean; blocked_word: BlockedWord }>(
        buildSpecialBookAdminBlockedWordUrl(item.id),
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(item),
        },
      )
      blockedWords = blockedWords.map((row) => (row.id === item.id ? data.blocked_word : row))
      toast({ content: 'Строка сохранена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить строку'
    } finally {
      rowSaving = { ...rowSaving, [item.id]: false }
    }
  }

  async function deleteBlockedWord(item: BlockedWord) {
    if (!window.confirm('Удалить запрещенное выражение?')) return
    rowSaving = { ...rowSaving, [item.id]: true }
    error = ''
    try {
      await fetchJson<{ ok: boolean }>(buildSpecialBookAdminBlockedWordUrl(item.id), {
        method: 'DELETE',
      })
      blockedWords = blockedWords.filter((row) => row.id !== item.id)
      toast({ content: 'Строка удалена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось удалить строку'
    } finally {
      rowSaving = { ...rowSaving, [item.id]: false }
    }
  }

  onMount(async () => {
    if (!browser) return
    const currentUser = $siteUser || (await refreshSiteUser())
    if (!currentUser) {
      goto(`/login?next=${encodeURIComponent('/s/book/admin')}`)
      return
    }
    if (!currentUser.is_staff) {
      goto('/s/book')
      return
    }
    await loadAdmin()
  })
</script>

<svelte:head>
  <title>Книга сообщества интернет: управление</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<main class="book-admin-page">
  <header class="admin-header">
    <div>
      <a class="back-link" href="/s/book">к книге</a>
      <h1>Книга сообщества интернет</h1>
      <p>Управление проектом</p>
    </div>
    <Button on:click={loadAdmin} disabled={loading}>
      <Icon src={ArrowPath} size="18" mini slot="prefix" />
      Обновить
    </Button>
  </header>

  {#if error}
    <div class="notice">{error}</div>
  {/if}

  {#if loading}
    <section class="panel">Загрузка...</section>
  {:else}
    {#if stats}
      <section class="stats-grid" aria-label="Статистика книги">
        <article>
          <span>Всего слов</span>
          <strong>{formatNumber(stats.total_words)}</strong>
        </article>
        <article>
          <span>Пользователей внесли слова</span>
          <strong>{formatNumber(stats.contributors_count)}</strong>
        </article>
        <article>
          <span>В среднем слов на пользователя</span>
          <strong>{formatNumber(stats.average_words_per_user)}</strong>
        </article>
        <article>
          <span>Регистраций со страницы</span>
          <strong>{formatNumber(stats.registrations_from_page_count)}</strong>
        </article>
      </section>

      <section class="panel">
        <div class="section-heading">
          <h2>Первая тройка</h2>
          <span>{formatNumber(stats.top_three_words)} слов</span>
        </div>
        {#if stats.top_users.length}
          <div class="top-users">
            {#each stats.top_users as item}
              <div>
                <a href={`/id${item.user.id}`}>{displayUserName(item.user)}</a>
                <span>@{item.user.username}</span>
                <strong>{formatNumber(item.words_count)}</strong>
              </div>
            {/each}
          </div>
        {:else}
          <p class="muted">Пока нет добавленных слов.</p>
        {/if}
      </section>
    {/if}

    <section class="panel">
      <div class="section-heading">
        <h2>Правила</h2>
      </div>
      <textarea class="rules-textarea" bind:value={rulesDraft} rows="8"></textarea>
      <div class="actions-row">
        <Button loading={savingRules} disabled={savingRules} on:click={saveRules}>
          <Icon src={Check} size="18" mini slot="prefix" />
          Сохранить правила
        </Button>
      </div>
    </section>

    <section class="panel">
      <div class="section-heading">
        <h2>Финальный PDF</h2>
        <span>{settings?.final_pdf?.available ? 'загружен' : 'не загружен'}</span>
      </div>
      <div class="pdf-grid">
        <div>
          <span>Дата загрузки</span>
          <strong>{formatDate(settings?.final_pdf?.uploaded_at)}</strong>
        </div>
        <div>
          <span>Дата рассылки</span>
          <strong>{formatDate(settings?.final_pdf?.announced_at)}</strong>
        </div>
        {#if settings?.final_pdf?.url}
          <a href={settings.final_pdf.url} target="_blank" rel="noreferrer">Открыть текущий PDF</a>
        {/if}
      </div>
      <div class="file-row">
        <input type="file" accept="application/pdf,.pdf" on:change={setFinalPdfFile} />
        <Button loading={uploadingPdf} disabled={uploadingPdf || !finalPdfFile} on:click={uploadFinalPdf}>
          Загрузить PDF
        </Button>
      </div>
    </section>

    <section class="panel">
      <div class="section-heading">
        <h2>Запрещенные выражения</h2>
        <span>{formatNumber(blockedWords.length)} строк</span>
      </div>

      <form class="blocked-form" on:submit|preventDefault={createBlockedWord}>
        <input bind:value={blockedDraft.word} placeholder="Слово или выражение" required />
        <input bind:value={blockedDraft.note} placeholder="Заметка" />
        <label class="checkbox-row">
          <input type="checkbox" bind:checked={blockedDraft.is_active} />
          <span>Активно</span>
        </label>
        <Button submit loading={savingBlocked} disabled={savingBlocked}>Добавить</Button>
      </form>

      <div class="blocked-list">
        {#each blockedWords as item (item.id)}
          <article class:inactive={!item.is_active}>
            <input bind:value={item.word} aria-label="Слово или выражение" />
            <input bind:value={item.note} aria-label="Заметка" placeholder="Заметка" />
            <code>{item.normalized_word}</code>
            <label class="checkbox-row">
              <input type="checkbox" bind:checked={item.is_active} />
              <span>Активно</span>
            </label>
            <div class="row-actions">
              <Button size="sm" disabled={rowSaving[item.id]} on:click={() => saveBlockedWord(item)}>
                Сохранить
              </Button>
              <button
                class="icon-button"
                type="button"
                aria-label="Удалить"
                disabled={rowSaving[item.id]}
                on:click={() => deleteBlockedWord(item)}
              >
                <Icon src={Trash} size="18" mini />
              </button>
            </div>
          </article>
        {/each}
      </div>
    </section>
  {/if}
</main>

<style>
  .book-admin-page {
    min-height: 100vh;
    background: #f6f1e9;
    color: #1f2933;
    padding: 36px min(32px, 5vw) 72px;
  }

  .admin-header,
  .panel,
  .stats-grid {
    width: min(1120px, 100%);
    margin: 0 auto;
  }

  .admin-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 24px;
  }

  .back-link {
    color: #2f6f59;
    font-size: 14px;
    font-weight: 700;
    text-decoration: none;
  }

  h1,
  h2,
  p {
    margin: 0;
  }

  h1 {
    margin-top: 8px;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: clamp(34px, 5vw, 56px);
    line-height: 1;
    letter-spacing: 0;
  }

  .admin-header p {
    margin-top: 10px;
    color: #6b5f51;
  }

  .notice {
    width: min(1120px, 100%);
    margin: 0 auto 16px;
    border: 1px solid #f3b4ad;
    border-radius: 8px;
    background: #fff3f1;
    color: #b42318;
    padding: 12px 14px;
  }

  .panel {
    margin-top: 18px;
    border: 1px solid #d8cbb9;
    border-radius: 8px;
    background: #fffdf8;
    padding: 22px;
  }

  .stats-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 12px;
  }

  .stats-grid article,
  .pdf-grid > div {
    border: 1px solid #eadfce;
    border-radius: 8px;
    background: #fbf8f2;
    padding: 14px;
  }

  .stats-grid span,
  .pdf-grid span,
  .section-heading span,
  .muted {
    color: #6b5f51;
    font-size: 13px;
  }

  .stats-grid strong,
  .pdf-grid strong {
    display: block;
    margin-top: 8px;
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 30px;
    line-height: 1;
  }

  .pdf-grid strong {
    font-family: inherit;
    font-size: 16px;
  }

  .section-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .section-heading h2 {
    font-family: Georgia, 'Times New Roman', serif;
    font-size: 28px;
    line-height: 1.1;
  }

  .top-users,
  .blocked-list {
    display: grid;
    gap: 10px;
  }

  .top-users div,
  .blocked-list article {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto auto auto;
    gap: 10px;
    align-items: center;
    border: 1px solid #eadfce;
    border-radius: 8px;
    background: #ffffff;
    padding: 10px;
  }

  .top-users div {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  }

  .top-users a {
    color: #1f2933;
    font-weight: 700;
    overflow-wrap: anywhere;
  }

  input,
  textarea {
    width: 100%;
    border: 1px solid #d8cbb9;
    border-radius: 8px;
    background: #fffdf8;
    color: #1f2933;
    font: inherit;
    padding: 10px 12px;
  }

  .rules-textarea {
    min-height: 190px;
    line-height: 1.55;
  }

  .actions-row,
  .file-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    justify-content: flex-end;
    margin-top: 14px;
  }

  .file-row {
    justify-content: space-between;
  }

  .file-row input {
    width: min(520px, 100%);
  }

  .pdf-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 10px;
  }

  .pdf-grid a {
    display: inline-flex;
    min-height: 48px;
    align-items: center;
    justify-content: center;
    border: 1px solid #2f6f59;
    border-radius: 8px;
    color: #2f6f59;
    font-weight: 700;
    text-decoration: none;
  }

  .blocked-form {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) auto auto;
    gap: 10px;
    align-items: center;
    margin-bottom: 16px;
  }

  .checkbox-row {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: #475569;
    font-size: 14px;
    white-space: nowrap;
  }

  .checkbox-row input {
    width: auto;
  }

  code {
    color: #2f6f59;
    font-size: 13px;
    overflow-wrap: anywhere;
  }

  .inactive {
    opacity: 0.62;
  }

  .row-actions {
    display: inline-flex;
    gap: 8px;
    justify-content: flex-end;
  }

  .icon-button {
    display: inline-flex;
    width: 36px;
    height: 36px;
    align-items: center;
    justify-content: center;
    border: 1px solid #d8cbb9;
    border-radius: 999px;
    background: #fffdf8;
    color: #9f2a22;
  }

  .icon-button:disabled {
    opacity: 0.5;
  }

  @media (max-width: 880px) {
    .admin-header,
    .section-heading {
      display: grid;
    }

    .stats-grid,
    .pdf-grid,
    .blocked-form,
    .blocked-list article,
    .top-users div {
      grid-template-columns: 1fr;
    }

    .actions-row,
    .file-row {
      justify-content: flex-start;
    }
  }
</style>
