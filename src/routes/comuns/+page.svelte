<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import { buildComunsUrl, type BackendComun } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { goto } from '$app/navigation'

  export let data

  const COMMUNITY_CREATION_MIN_AUTHOR_RATING = 5
  const COMMUNITIES_FAQ_HREF = '/faq'
  const COMMUNITIES_LANDING_HREF = '/lp/communities'

  let comuns: BackendComun[] = data.comuns ?? []
  let createOpen = false
  let insufficientOpen = false
  let creating = false
  let createIntentHandled = false

  let name = ''
  let slug = ''
  let websiteUrl = ''
  let logoUrl = ''
  let logoUploading = false
  let productDescription = ''
  let targetAudience = ''
  let createLogoInput: HTMLInputElement | null = null

  const hashString = (value?: string | null) => {
    const source = (value ?? '').trim() || 'comuna'
    let hash = 0
    for (let i = 0; i < source.length; i += 1) {
      hash = (hash * 31 + source.charCodeAt(i)) % 360
    }
    return Math.abs(hash)
  }

  const comunPlaceholderStyle = (name?: string | null) => `--comun-h:${hashString(name)}`

  const comunInitial = (name?: string | null) =>
    (name ?? '').trim().slice(0, 1).toUpperCase() || 'C'

  const formatRatingValue = (value?: number | null) => {
    const numeric = Math.max(Number(value ?? 0) || 0, 0)
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.?0+$/, '')
  }

  const currentUserMaxAuthorRating = (user = $siteUser) => {
    const authorRatings = (user?.authors ?? []).map((author) => Math.max(Number(author.author_rating ?? 0) || 0, 0))
    const explicitRating = Math.max(Number(user?.max_author_rating ?? 0) || 0, 0)
    return Math.max(explicitRating, ...authorRatings, 0)
  }

  const canCreate = (user = $siteUser) =>
    Boolean(
      $siteToken &&
        (user?.can_create_comun ??
          currentUserMaxAuthorRating(user) >= Number(user?.create_comun_min_author_rating ?? COMMUNITY_CREATION_MIN_AUTHOR_RATING))
    )

  const resetForm = () => {
    name = ''
    slug = ''
    websiteUrl = ''
    logoUrl = ''
    logoUploading = false
    productDescription = ''
    targetAudience = ''
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const openCreate = async () => {
    if (!canCreate()) {
      if (!$siteToken) {
        goto('/account?next=/comuns?create=1')
        return
      }

      const user = $siteUser ?? (await refreshSiteUser())
      if (!user) {
        goto('/account?next=/comuns?create=1')
        return
      }
      if (!canCreate(user)) {
        insufficientOpen = true
        return
      }
    }
    createOpen = true
  }

  $: if (browser && $page.url.searchParams.get('create') === '1' && !createIntentHandled) {
    createIntentHandled = true
    void openCreate()
  }

  $: if (browser && $page.url.searchParams.get('create') !== '1') {
    createIntentHandled = false
  }

  const pickCreateLogo = () => {
    if (!canCreate()) {
      void openCreate()
      return
    }
    createLogoInput?.click()
  }

  const onCreateLogoSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file) return

    logoUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      logoUrl = uploadedUrl
      toast({ content: 'Логотип загружен', type: 'success' })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось загрузить логотип', type: 'error' })
    } finally {
      logoUploading = false
      if (input) input.value = ''
    }
  }

  const createComun = async () => {
    if (!name.trim()) {
      toast({ content: 'Введите название сообщества', type: 'warning' })
      return
    }
    creating = true
    try {
      const response = await fetch(buildComunsUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          name,
          slug,
          website_url: websiteUrl,
          logo_url: logoUrl,
          product_description: productDescription,
          target_audience: targetAudience,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.comun?.slug) {
        if (payload?.reason === 'insufficient_author_rating') {
          insufficientOpen = true
          throw new Error('У вас недостаточно рейтинга для создания сообщества')
        }
        throw new Error(payload?.error || 'Не удалось создать сообщество')
      }
      createOpen = false
      resetForm()
      toast({ content: 'Сообщество создано', type: 'success' })
      goto(`/comuns/${payload.comun.slug}/settings`)
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка создания', type: 'error' })
    } finally {
      creating = false
    }
  }
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="min-w-0">
        <Header noMargin>Сообщества</Header>
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          Пространства вокруг продукта: отдельная страница, обсуждения, категории постов, беклог и дорожная карта.
        </div>
      </div>
      <Button on:click={() => void openCreate()}>
        {#if $siteUser}
          Создать сообщество
        {:else}
          Войти и создать
        {/if}
      </Button>
    </div>
  </section>

  {#if comuns.length}
    <div class="grid gap-4 sm:grid-cols-2">
      {#each comuns as comun}
        <a
          href={`/comuns/${comun.slug}`}
          class="group rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-sm transition-all min-w-0"
        >
          <div class="flex items-start gap-4 min-w-0">
            <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
              {#if comun.logo_url}
                <img src={comun.logo_url} alt={comun.name} class="h-full w-full object-cover" />
              {:else}
                <div
                  class="comun-logo-fallback h-full w-full grid place-items-center text-xl font-bold"
                  style={comunPlaceholderStyle(comun.name)}
                >
                  {comunInitial(comun.name)}
                </div>
              {/if}
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2 min-w-0">
                <div class="text-base font-semibold text-slate-900 dark:text-zinc-100 truncate">
                  {comun.name}
                </div>
                {#if comun.product_tag}
                  <span class="shrink-0 rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 text-xs text-slate-600 dark:text-zinc-300">
                    #{comun.product_tag.name}
                  </span>
                {/if}
              </div>
              {#if comun.product_description}
                <div class="mt-1 text-sm text-slate-600 dark:text-zinc-400 line-clamp-3">
                  {comun.product_description}
                </div>
              {/if}
              {#if comun.target_audience}
                <div class="mt-2 text-xs text-slate-500 dark:text-zinc-400">
                  ЦА: {comun.target_audience}
                </div>
              {/if}
              <div class="mt-2 flex flex-wrap gap-2 text-xs text-slate-500 dark:text-zinc-400">
                {#if comun.website_url}
                  <span class="truncate max-w-full">{comun.website_url}</span>
                {/if}
                <span>{comun.categories_count ?? comun.categories?.length ?? 0} категорий</span>
                <span>{comun.moderators_count ?? comun.moderators?.length ?? 0} модераторов</span>
              </div>
            </div>
          </div>
        </a>
      {/each}
    </div>
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      Пока нет созданных сообществ.
    </div>
  {/if}
</div>

<Modal bind:open={createOpen} on:close={resetForm}>
  <div class="w-full max-w-2xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Создать сообщество</div>
    <div class="text-sm text-slate-600 dark:text-zinc-400">
      После создания откроется страница сообщества, где можно выбрать тег продукта, внутренние категории и приветственный пост.
    </div>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Название</span>
      <input bind:value={name} class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Slug (необязательно)</span>
      <input bind:value={slug} placeholder="my-startup" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Веб-сайт</span>
      <input bind:value={websiteUrl} type="url" placeholder="https://..." class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
    </label>

    <div class="flex flex-col gap-2">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Логотип</span>
      <input
        bind:this={createLogoInput}
        type="file"
        accept="image/*"
        class="hidden"
        on:change={onCreateLogoSelected}
      />
      <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
        <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
          {#if logoUrl}
            <img src={logoUrl} alt="Предпросмотр логотипа" class="h-full w-full object-cover" />
          {:else}
            <div class="h-full w-full grid place-items-center text-slate-400 dark:text-zinc-500 text-xs text-center px-1">
              Нет лого
            </div>
          {/if}
        </div>
        <div class="min-w-0 flex-1 flex flex-col gap-1">
          <div class="text-sm text-slate-700 dark:text-zinc-300">
            {#if logoUploading}
              Загрузка логотипа...
            {:else if logoUrl}
              Логотип загружен
            {:else}
              Загрузите файл изображения
            {/if}
          </div>
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            PNG, JPG, WEBP, GIF
          </div>
        </div>
        <div class="flex flex-wrap gap-2 justify-end">
          <Button on:click={pickCreateLogo} disabled={creating || logoUploading} size="sm">
            {logoUrl ? 'Заменить' : 'Выбрать файл'}
          </Button>
          {#if logoUrl}
            <Button color="ghost" size="sm" on:click={() => (logoUrl = '')} disabled={creating || logoUploading}>
              Убрать
            </Button>
          {/if}
        </div>
      </div>
    </div>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Описание продукта</span>
      <textarea bind:value={productDescription} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
    </label>

    <label class="flex flex-col gap-1">
      <span class="text-sm text-slate-700 dark:text-zinc-300">Целевая аудитория</span>
      <textarea bind:value={targetAudience} rows="2" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
    </label>

    <div class="flex justify-end gap-2 pt-2">
      <Button color="ghost" on:click={() => (createOpen = false)} disabled={creating}>Отмена</Button>
      <Button on:click={createComun} disabled={creating || logoUploading}>
        {creating ? 'Создаем...' : 'Создать сообщество'}
      </Button>
    </div>
  </div>
</Modal>

<Modal bind:open={insufficientOpen}>
  <div class="w-full max-w-xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Недостаточно рейтинга</div>
    <div class="text-sm leading-6 text-slate-600 dark:text-zinc-400">
      У вас недостаточно рейтинга для создания сообщества. Сейчас ваш максимальный рейтинг автора:
      <span class="font-semibold text-slate-900 dark:text-zinc-100">{formatRatingValue(currentUserMaxAuthorRating())}</span>.
      Для создания нужен рейтинг от
      <span class="font-semibold text-slate-900 dark:text-zinc-100">{formatRatingValue($siteUser?.create_comun_min_author_rating ?? COMMUNITY_CREATION_MIN_AUTHOR_RATING)}</span>.
    </div>
    <div class="grid gap-3 sm:grid-cols-2">
      <a
        href={COMMUNITIES_FAQ_HREF}
        class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900 px-4 py-4 text-sm font-medium text-slate-900 dark:text-zinc-100 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
      >
        Открыть FAQ
      </a>
      <a
        href={COMMUNITIES_LANDING_HREF}
        class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900 px-4 py-4 text-sm font-medium text-slate-900 dark:text-zinc-100 hover:border-slate-300 dark:hover:border-zinc-700 transition-colors"
      >
        Что такое сообщества
      </a>
    </div>
    <div class="flex justify-end gap-2 pt-1">
      <Button color="ghost" on:click={() => (insufficientOpen = false)}>Закрыть</Button>
    </div>
  </div>
</Modal>

<style>
  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }
</style>
