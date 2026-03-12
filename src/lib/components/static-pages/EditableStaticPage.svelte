<script>
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import { isAdmin } from '$lib/components/lemmy/moderation/moderation'
  import TipTapEditor from '$lib/components/editor/TipTapEditor.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { profile } from '$lib/auth'
  import { normalizeStaticPageEditorValue } from '$lib/staticPageEditor'
  import { refreshSiteUser, siteUser, updateStaticPageContent } from '$lib/siteAuth'
  import { Button, toast } from 'mono-svelte'
  import { onMount } from 'svelte'

  export let data
  export let slug
  export let heading
  export let description
  export let seoTitle

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

  const startEditing = async () => {
    if (!canEdit) {
      const refreshedUser = await refreshSiteUser().catch(() => null)
      if (!refreshedUser?.is_staff) {
        loginModalOpen = true
        toast({
          content: 'Редактирование доступно только администраторам сайта.',
          type: 'info',
        })
        return
      }
    }

    editorValue = normalizeStaticPageEditorValue(pageContent)
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
      const updated = await updateStaticPageContent(slug, {
        title: heading,
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

<div class="flex max-w-3xl flex-col gap-6">
  <Header pageHeader>
    <div class="flex w-full items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">{heading}</h1>
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

  <article class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
    {#if isEditing}
      <div class="flex flex-col gap-4">
        <TipTapEditor
          bind:value={editorValue}
          placeholder="Введите содержимое страницы"
          includeMetaTags={false}
        />
        <div class="flex items-center gap-2">
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
      <div class="post static-page-post relative max-w-full min-w-0 w-full">
        <div class="mb-5 border-b border-slate-100 pb-4 dark:border-zinc-800">
          <div class="text-xs font-medium uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
            Служебная страница
          </div>
          <h2 class="mt-2 text-2xl font-medium text-black dark:text-white">{heading}</h2>
        </div>
        <div class="text-base leading-relaxed">
          <PostBody body={pageContent} showFullBody={true} />
        </div>
      </div>
    {/if}
  </article>
</div>

<LoginModal bind:open={loginModalOpen} />

<svelte:head>
  <title>{seoTitle}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={seoTitle} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
