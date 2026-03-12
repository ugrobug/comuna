<script>
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import TipTapEditor from '$lib/components/editor/TipTapEditor.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { normalizeStaticPageEditorValue } from '$lib/staticPageEditor'
  import { refreshSiteUser, siteUser, updateStaticPageContent } from '$lib/siteAuth'
  import { Button, toast } from 'mono-svelte'
  import { onMount } from 'svelte'

  export let data

  let isCheckingAccess = true
  let isSaving = false
  let loginModalOpen = false
  let pageContent = data?.pageContent ?? ''
  let editorValue = normalizeStaticPageEditorValue(pageContent)

  $: canEdit = !!$siteUser?.is_staff
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  $: seoTitle = `Редактирование: ${data.heading} — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`

  onMount(async () => {
    await refreshSiteUser().catch(() => null)
    isCheckingAccess = false
  })

  const savePage = async () => {
    if (!canEdit) return

    isSaving = true
    try {
      const updated = await updateStaticPageContent(data.slug, {
        title: data.heading,
        content: editorValue,
      })
      pageContent = updated.content ?? ''
      editorValue = normalizeStaticPageEditorValue(pageContent)
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

  const openPublicPage = () => {
    void goto(data.slug === 'about' ? '/about' : `/${data.slug}`)
  }
</script>

<div class="flex max-w-4xl flex-col gap-6">
  <Header pageHeader>
    <div class="flex w-full items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">Редактирование: {data.heading}</h1>
      <Button color="secondary" on:click={openPublicPage}>Открыть страницу</Button>
    </div>
  </Header>

  {#if isCheckingAccess}
    <article class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-6 text-base dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900">
      Проверяю доступ...
    </article>
  {:else if canEdit}
    <article class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
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
          <Button color="secondary" on:click={openPublicPage} disabled={isSaving}>
            Отмена
          </Button>
        </div>
      </div>
    </article>
  {:else}
    <article class="rounded-xl border border-amber-300 bg-amber-50 p-6 text-base text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/20 dark:text-amber-100">
      <div class="flex flex-col gap-4">
        <p>Редактирование доступно только администраторам сайта.</p>
        <div class="flex items-center gap-2">
          <Button on:click={() => (loginModalOpen = true)}>Войти</Button>
          <Button color="secondary" on:click={openPublicPage}>К странице</Button>
        </div>
      </div>
    </article>
  {/if}
</div>

<LoginModal bind:open={loginModalOpen} />

<svelte:head>
  <title>{seoTitle}</title>
  <meta name="description" content={`Редактирование страницы ${data.heading}`} />
  <meta name="robots" content="noindex,nofollow" />
  <meta property="og:title" content={seoTitle} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
