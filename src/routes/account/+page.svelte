<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal, Spinner, TextInput, Select } from 'mono-svelte'
  import TipTapEditor from '$lib/components/editor/TipTapEditor.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import {
    fetchUserPosts,
    fetchVerificationCode,
    createUserPost,
    logout,
    refreshSiteUser,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import { deserializeEditorModel } from '$lib/util'
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
  let isJsonContent = true
  let saving = false
  let saveError = ''
  let createTitle = ''
  let createContent = ''
  let createAuthor = ''
  let creating = false
  let createError = ''

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

  const detectContentType = (content: string): boolean => {
    if (!content || content.trim() === '') {
      return true
    }
    if (content.trim().startsWith('<') && content.trim().endsWith('>')) {
      return false
    }
    try {
      const parsed = JSON.parse(content)
      return parsed && typeof parsed === 'object' && 'blocks' in parsed
    } catch {
      try {
        const isBase64 = /^[A-Za-z0-9+/]*={0,2}$/.test(content)
        if (!isBase64) {
          return false
        }
        const decoded = deserializeEditorModel(content)
        return decoded && typeof decoded === 'object' && 'blocks' in decoded
      } catch {
        return false
      }
    }
  }

  const openEdit = (post: SiteUserPost) => {
    editing = post
    editTitle = post.title || ''
    editContent = post.content || ''
    isJsonContent = detectContentType(editContent)
    saveError = ''
    editOpen = true
  }

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const data = deserializeEditorModel(value)
      return !data?.blocks || data.blocks.length === 0
    } catch {
      return true
    }
  }

  const saveEdit = async () => {
    if (!editing) return
    saving = true
    saveError = ''
    try {
      const trimmedHtml = editContent.trim()
      if (isJsonContent) {
        if (!trimmedHtml) {
          saveError = 'Текст поста не может быть пустым'
          saving = false
          return
        }
      } else {
        const hasText = stripHtml(trimmedHtml).length > 0
        if (!hasText) {
          saveError = 'Текст поста не может быть пустым'
          saving = false
          return
        }
      }
      const updated = await updateUserPost(editing.id, {
        title: editTitle,
        content: trimmedHtml,
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

  $: if ($siteUser?.authors?.length && !createAuthor) {
    createAuthor = $siteUser.authors[0]?.username || ''
  }

  const createPost = async () => {
    if (!$siteUser) return
    createError = ''
    if (!$siteUser.authors.length) {
      createError = 'Подтвердите канал, чтобы публиковать посты.'
      return
    }
    if (!createTitle.trim()) {
      createError = 'Укажите заголовок поста.'
      return
    }
    if (isEditorContentEmpty(createContent)) {
      createError = 'Текст поста не может быть пустым.'
      return
    }
    if ($siteUser.authors.length > 1 && !createAuthor) {
      createError = 'Выберите канал для публикации.'
      return
    }
    creating = true
    try {
      const post = await createUserPost({
        title: createTitle.trim(),
        content: createContent.trim(),
        author_username: createAuthor || undefined,
      })
      posts = [post, ...posts]
      postsTotal += 1
      createTitle = ''
      createContent = ''
    } catch (err) {
      createError = (err as Error)?.message ?? 'Не удалось создать пост'
    } finally {
      creating = false
    }
  }
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

    <div id="new-post" class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <h2 class="text-lg font-semibold mb-2">Новый пост</h2>
      {#if !$siteUser.authors.length}
        <p class="text-sm text-slate-500 dark:text-zinc-400">
          Чтобы публиковать посты, сначала подтвердите свой канал через бота.
        </p>
      {:else}
        <div class="flex flex-col gap-4">
          {#if $siteUser.authors.length > 1}
            <Select bind:value={createAuthor} class="max-w-xs">
              <option value="" disabled>Выберите канал</option>
              {#each $siteUser.authors as author}
                <option value={author.username}>@{author.username}</option>
              {/each}
            </Select>
          {/if}
          <TextInput label="Заголовок" bind:value={createTitle} />
          <EditorJS
            bind:value={createContent}
            placeholder="Текст поста"
            enableAutosave={false}
            postId={null}
          />
          {#if createError}
            <p class="text-sm text-red-600">{createError}</p>
          {/if}
          <div class="flex flex-wrap gap-2">
            <Button color="primary" on:click={createPost} loading={creating} disabled={creating}>
              Опубликовать
            </Button>
            <Button
              color="ghost"
              on:click={() => {
                createTitle = ''
                createContent = ''
                createError = ''
              }}
              disabled={creating}
            >
              Очистить
            </Button>
          </div>
        </div>
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
        {#if isJsonContent}
          <EditorJS
            bind:value={editContent}
            placeholder="Текст поста"
            enableAutosave={false}
            postId={editing?.id ?? null}
          />
        {:else}
          <TipTapEditor
            bind:value={editContent}
            placeholder="Текст поста"
            includeMetaTags={false}
            allowMedia={false}
          />
        {/if}
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
