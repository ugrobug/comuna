<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { profile } from '$lib/auth'
  import { isAdmin } from '$lib/components/lemmy/moderation/moderation'
  import { Button, toast } from 'mono-svelte'
  import { onMount } from 'svelte'
  import { refreshSiteUser, siteUser, updateStaticPageContent } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'

  export let data

  const title = `Авторам — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Публикуйте посты Telegram-канала на сайте, чтобы их находили в Google и Яндексе и подписывались на ваш канал.'
  let isEditing = false
  let isSaving = false
  let loginModalOpen = false
  let pageContent = data?.pageContent ?? ''
  let editorValue = pageContent
  $: canEdit = !!$siteUser?.is_staff
  $: canManagePage = canEdit || !!($profile?.user && isAdmin($profile.user))
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  onMount(() => {
    refreshSiteUser().catch(() => null)
  })

  const startEditing = () => {
    if (!canEdit) {
      loginModalOpen = true
      toast({
        content: 'Для редактирования этой страницы нужен вход в аккаунт сайта.',
        type: 'info',
      })
      return
    }
    editorValue = pageContent
    isEditing = true
  }

  const cancelEditing = () => {
    editorValue = pageContent
    isEditing = false
  }

  const savePage = async () => {
    if (!canEdit) return
    isSaving = true
    try {
      const updated = await updateStaticPageContent('authors', {
        title: 'Авторам',
        content: editorValue,
      })
      pageContent = updated.content ?? ''
      editorValue = pageContent
      isEditing = false
      toast({ content: 'Страница сохранена', type: 'success' })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось сохранить страницу',
        type: 'error',
      })
    } finally {
      isSaving = false
    }
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <div class="flex w-full items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">Авторам</h1>
      {#if canManagePage && !isEditing}
        <Button size="sm" color="secondary" on:click={startEditing}>
          {#if canEdit}
            Редактировать
          {:else}
            Войти для редактирования
          {/if}
        </Button>
      {/if}
    </div>
  </Header>

  {#if isEditing}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
      <EditorJS bind:value={editorValue} showPostSettings={false} />
      <div class="mt-4 flex items-center gap-2">
        <Button on:click={savePage} disabled={isSaving}>
          {#if isSaving}
            Сохранение...
          {:else}
            Сохранить
          {/if}
        </Button>
        <Button color="secondary" on:click={cancelEditing} disabled={isSaving}>
          Отмена
        </Button>
      </div>
    </div>
  {:else}
    <div class="text-base leading-relaxed">
      <PostBody body={pageContent} showFullBody={true} />
    </div>
  {/if}
</div>

<LoginModal bind:open={loginModalOpen} />

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
