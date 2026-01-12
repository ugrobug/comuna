<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal, Spinner, TextInput } from 'mono-svelte'
  import {
    fetchUserPosts,
    fetchVerificationCode,
    logout,
    refreshSiteUser,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import { onMount, tick } from 'svelte'
  import { buildBackendPostPath } from '$lib/api/backend'

  let code = ''
  let loading = false
  let error = ''
  let postsLoading = false
  let postsError = ''
  let postsTotal = 0
  let posts: SiteUserPost[] = []

  let editOpen = false
  let editing: SiteUserPost | null = null
  let editTitle = ''
  let editContent = ''
  let editMedia = ''
  let saving = false
  let saveError = ''
  let editorElement: HTMLDivElement | null = null
  let showLinkInput = false
  let linkUrl = ''

  const loadCode = async () => {
    loading = true
    error = ''
    try {
      code = await fetchVerificationCode()
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось получить код'
    }
    loading = false
  }

  const splitContentForEdit = (content: string) => {
    if (!content) {
      return { media: '', text: '' }
    }
    let remaining = content.trim()
    const mediaParts: string[] = []
    const patterns = [
      /^\s*(<div class="post-gallery">[\s\S]*?<\/div>)/i,
      /^\s*(<div class="post-embed">[\s\S]*?<\/div>)/i,
      /^\s*(<img[^>]*>)/i,
    ]
    let matched = true
    while (matched) {
      matched = false
      for (const pattern of patterns) {
        const match = remaining.match(pattern)
        if (match) {
          mediaParts.push(match[1])
          remaining = remaining.replace(match[0], '')
          remaining = remaining.replace(/^(<br\s*\/?>\s*)+/gi, '').trim()
          matched = true
          break
        }
      }
    }
    return { media: mediaParts.join(''), text: remaining }
  }

  const loadPosts = async () => {
    postsLoading = true
    postsError = ''
    try {
      const data = await fetchUserPosts(50, 0)
      posts = data.posts
      postsTotal = data.total
    } catch (err) {
      postsError = (err as Error)?.message ?? 'Не удалось загрузить посты'
    } finally {
      postsLoading = false
    }
  }

  const openEdit = async (post: SiteUserPost) => {
    editing = post
    editTitle = post.title || ''
    const { media, text } = splitContentForEdit(post.content || '')
    editMedia = media
    editContent = text
    saveError = ''
    showLinkInput = false
    linkUrl = ''
    editOpen = true
    await tick()
    if (editorElement) {
      editorElement.innerHTML = editContent || ''
    }
  }

  const normalizeLink = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return ''
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      return trimmed
    }
    return `https://${trimmed}`
  }

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()

  const applyCommand = (command: string, value?: string) => {
    if (!editorElement) return
    editorElement.focus()
    document.execCommand(command, false, value)
    editContent = editorElement.innerHTML
  }

  const insertLink = () => {
    if (!editorElement) return
    const url = normalizeLink(linkUrl)
    if (!url) return
    editorElement.focus()
    const selection = window.getSelection()
    const selectedText = selection?.toString() ?? ''
    const label = selectedText || url
    document.execCommand(
      'insertHTML',
      false,
      `<a href="${url}" target="_blank" rel="noopener noreferrer">${label}</a>`
    )
    editContent = editorElement.innerHTML
    linkUrl = ''
    showLinkInput = false
  }

  const saveEdit = async () => {
    if (!editing) return
    saving = true
    saveError = ''
    try {
      const trimmedHtml = editContent.trim()
      const hasText = stripHtml(trimmedHtml).length > 0
      if (!hasText && !editMedia) {
        saveError = 'Текст поста не может быть пустым'
        saving = false
        return
      }
      const combined = [editMedia, trimmedHtml].filter(Boolean).join('<br><br>')
      const updated = await updateUserPost(editing.id, {
        title: editTitle,
        content: combined,
      })
      posts = posts.map((post) => (post.id === updated.id ? updated : post))
      editOpen = false
      editing = null
    } catch (err) {
      saveError = (err as Error)?.message ?? 'Не удалось сохранить изменения'
    } finally {
      saving = false
    }
  }

  onMount(() => {
    refreshSiteUser().then((user) => {
      if (user) {
        loadPosts()
      }
    })
  })
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Личный кабинет</h1>
  </Header>

  {#if $siteUser}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <div class="text-sm text-slate-500 dark:text-zinc-400">Вы вошли как</div>
      <div class="text-lg font-semibold">@{$siteUser.username}</div>
      {#if $siteUser.email}
        <div class="text-sm text-slate-500 dark:text-zinc-400">{$siteUser.email}</div>
      {/if}
    </div>

    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <h2 class="text-lg font-semibold mb-2">Подтверждение админа канала</h2>
      <p class="text-sm text-slate-500 dark:text-zinc-400">
        Получите код и отправьте его в бота. Бот подтвердит, что вы администратор канала.
      </p>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <Button size="sm" color="primary" on:click={loadCode} loading={loading} disabled={loading}>
          Получить код
        </Button>
        {#if code}
          <div class="rounded-lg bg-slate-100 dark:bg-zinc-900 px-4 py-2 text-sm font-mono">
            {code}
          </div>
        {/if}
      </div>
      {#if error}
        <p class="text-sm text-red-600 mt-3">{error}</p>
      {/if}
      <p class="text-sm text-slate-500 dark:text-zinc-400 mt-4">
        Отправьте код боту в Telegram — @comuna_tg_bot.
      </p>
    </div>

    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <h2 class="text-lg font-semibold mb-2">Ваши подтверждённые каналы</h2>
      {#if $siteUser.is_author && $siteUser.authors.length}
        <ul class="flex flex-col gap-2 text-sm">
          {#each $siteUser.authors as author}
            <li>
              @{author.username}
              {#if author.title}
                <span class="text-slate-500 dark:text-zinc-400">— {author.title}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {:else}
        <p class="text-sm text-slate-500 dark:text-zinc-400">Пока нет подтверждённых каналов.</p>
      {/if}
    </div>

    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 class="text-lg font-semibold">Ваши посты</h2>
        {#if postsTotal}
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            Всего: {postsTotal}
          </div>
        {/if}
      </div>
      {#if postsLoading}
        <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
          <Spinner size="sm" />
          Загрузка...
        </div>
      {:else if postsError}
        <p class="text-sm text-red-600">{postsError}</p>
      {:else if posts.length === 0}
        <p class="text-sm text-slate-500 dark:text-zinc-400">
          Пока нет постов. Они появятся после публикации в вашем канале.
        </p>
      {:else}
        <div class="flex flex-col gap-4">
          {#each posts as post}
            <div class="rounded-lg border border-slate-200 dark:border-zinc-800 p-4">
              <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <div class="min-w-0">
                  <a
                    class="text-base font-semibold text-slate-900 dark:text-white hover:underline"
                    href={buildBackendPostPath({ id: post.id, title: post.title })}
                  >
                    {post.title}
                  </a>
                  <div class="text-xs text-slate-500 dark:text-zinc-400 mt-1">
                    @{post.author.username}
                    <span class="mx-1">•</span>
                    {new Date(post.created_at).toLocaleDateString('ru-RU')}
                    {#if post.is_pending}
                      <span class="ml-2 text-amber-600">На согласовании</span>
                    {/if}
                  </div>
                </div>
                <div class="sm:justify-self-end">
                  <Button
                    size="sm"
                    color="secondary"
                    class="w-full sm:w-auto"
                    on:click={() => openEdit(post)}
                  >
                    Редактировать
                  </Button>
                </div>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <div>
      <Button color="ghost" on:click={logout}>Выйти</Button>
    </div>
  {:else}
    <p class="text-sm text-slate-500 dark:text-zinc-400">
      Войдите, чтобы управлять своим профилем.
    </p>
  {/if}
</div>

{#if editOpen}
  <Modal bind:open={editOpen} title="Редактирование поста">
    <div class="flex flex-col gap-4">
      <TextInput label="Заголовок" bind:value={editTitle} />
      <div class="flex flex-col gap-2">
        <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2">
          <button class="editor-btn" type="button" title="Полужирный" on:click={() => applyCommand('bold')}>Ж</button>
          <button class="editor-btn" type="button" title="Курсив" on:click={() => applyCommand('italic')}>К</button>
          <button class="editor-btn" type="button" title="Заголовок 2" on:click={() => applyCommand('formatBlock', 'h2')}>H2</button>
          <button class="editor-btn" type="button" title="Заголовок 3" on:click={() => applyCommand('formatBlock', 'h3')}>H3</button>
          <button class="editor-btn" type="button" title="Маркированный список" on:click={() => applyCommand('insertUnorderedList')}>•</button>
          <button class="editor-btn" type="button" title="Нумерованный список" on:click={() => applyCommand('insertOrderedList')}>1.</button>
          <button class="editor-btn" type="button" title="Цитата" on:click={() => applyCommand('formatBlock', 'blockquote')}>"</button>
          <button class="editor-btn" type="button" title="Блок кода" on:click={() => applyCommand('formatBlock', 'pre')}>{`</>`}</button>
          <button class="editor-btn" type="button" title="Добавить ссылку" on:click={() => (showLinkInput = !showLinkInput)}>🔗</button>
        </div>
        {#if showLinkInput}
          <div class="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-2">
            <input
              type="url"
              class="flex-1 min-w-[180px] px-3 py-2 rounded-md border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm text-slate-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="Ссылка"
              bind:value={linkUrl}
              on:keydown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault()
                  insertLink()
                }
              }}
            />
            <Button size="sm" color="primary" on:click={insertLink}>Вставить</Button>
          </div>
        {/if}
        <div
          class="rich-editor min-h-[200px] rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3 text-sm text-slate-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          contenteditable="true"
          role="textbox"
          aria-multiline="true"
          data-placeholder="Текст поста"
          bind:this={editorElement}
          on:input={() => {
            if (editorElement) {
              editContent = editorElement.innerHTML
            }
          }}
        />
        <p class="text-xs text-slate-500 dark:text-zinc-400">
          Картинки и галереи сохраняются автоматически.
        </p>
      </div>
      {#if saveError}
        <p class="text-sm text-red-600">{saveError}</p>
      {/if}
      <div class="flex flex-wrap gap-2">
        <Button color="primary" on:click={saveEdit} loading={saving} disabled={saving}>
          Сохранить
        </Button>
        <Button color="ghost" on:click={() => (editOpen = false)} disabled={saving}>
          Отмена
        </Button>
      </div>
    </div>
  </Modal>
{/if}

<style lang="postcss">
  .editor-btn {
    @apply h-8 min-w-[32px] px-2 rounded-md border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-sm font-semibold text-slate-700 dark:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition;
  }

  .rich-editor:empty:before {
    content: attr(data-placeholder);
    @apply text-slate-400 dark:text-zinc-500;
  }
</style>
