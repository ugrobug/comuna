<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, Select } from 'mono-svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { onMount } from 'svelte'
  import { deserializeEditorModel } from '$lib/util'
  import {
    createUserPost,
    refreshSiteUser,
    siteUser,
  } from '$lib/siteAuth'

  let loadingUser = true
  let createTitle = ''
  let createContent = ''
  let createAuthor = ''
  let creating = false
  let createError = ''

  const isEditorContentEmpty = (value: string) => {
    if (!value || value.trim() === '') return true
    try {
      const data = deserializeEditorModel(value)
      return !data?.blocks || data.blocks.length === 0
    } catch {
      return true
    }
  }

  onMount(() => {
    refreshSiteUser().finally(() => {
      loadingUser = false
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
      await createUserPost({
        title: createTitle.trim(),
        content: createContent.trim(),
        author_username: createAuthor || undefined,
      })
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
    <h1 class="text-2xl font-bold">Новый пост</h1>
  </Header>

  {#if loadingUser}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if !$siteUser}
    <p class="text-sm text-slate-500 dark:text-zinc-400">
      Войдите, чтобы создавать посты.
    </p>
  {:else}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
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
            showPostSettings={false}
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
  {/if}
</div>
