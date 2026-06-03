<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildLandingPageAdminImageUrl,
    buildLandingPageAdminImagesUrl,
    buildLandingPageAdminUrl,
    buildLandingPagesAdminUrl,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { ArrowPath, Eye, Icon, Plus, Trash } from 'svelte-hero-icons'

  type LandingImage = {
    id: number
    slot: string
    title: string
    alt_text: string
    image_url: string
    is_active: boolean
    sort_order: number
  }

  type LandingPage = {
    id: number
    slug: string
    title: string
    description: string
    template_slug: string
    is_published: boolean
    sort_order: number
    url: string
    images: LandingImage[]
  }

  let loading = true
  let saving = false
  let imageSaving = false
  let error = ''
  let pages: LandingPage[] = []
  let selectedSlug = ''
  let draft = {
    title: '',
    description: '',
    template_slug: 'community-platform',
    is_published: true,
    sort_order: 100,
  }
  let newPage = {
    slug: '',
    title: '',
    description: '',
    template_slug: 'community-platform',
    is_published: true,
    sort_order: 100,
  }
  let imageDraft = {
    slot: 'hero',
    title: 'Главный скриншот',
    alt_text: '',
    image_url: '',
    is_active: true,
    sort_order: 10,
  }
  let imageFile: File | null = null

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  $: selectedPage = pages.find((page) => page.slug === selectedSlug) || null

  async function fetchJson<T>(url: string, options: RequestInit = {}) {
    const response = await fetch(url, {
      credentials: 'include',
      ...options,
      headers: {
        ...(options.headers || {}),
        ...authHeaders(),
      },
    })
    const data = (await response.json().catch(() => null)) as T & { ok?: boolean; error?: string }
    if (!response.ok || !data?.ok) {
      throw new Error(data?.error || 'Не удалось загрузить данные')
    }
    return data
  }

  function syncDraft(page: LandingPage | null) {
    if (!page) return
    draft = {
      title: page.title,
      description: page.description || '',
      template_slug: page.template_slug || 'community-platform',
      is_published: page.is_published,
      sort_order: page.sort_order,
    }
  }

  async function loadAdmin() {
    loading = true
    error = ''
    try {
      const data = await fetchJson<{ ok: boolean; pages: LandingPage[] }>(buildLandingPagesAdminUrl())
      pages = data.pages || []
      if (!selectedSlug && pages[0]) {
        selectedSlug = pages[0].slug
      }
      syncDraft(pages.find((page) => page.slug === selectedSlug) || pages[0] || null)
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить посадочные страницы'
    } finally {
      loading = false
    }
  }

  async function createPage() {
    saving = true
    error = ''
    try {
      const data = await fetchJson<{ ok: boolean; page: LandingPage }>(buildLandingPagesAdminUrl(), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newPage),
      })
      pages = [...pages, data.page].sort((a, b) => a.sort_order - b.sort_order)
      selectedSlug = data.page.slug
      syncDraft(data.page)
      newPage = {
        slug: '',
        title: '',
        description: '',
        template_slug: 'community-platform',
        is_published: true,
        sort_order: 100,
      }
      toast({ content: 'Посадочная страница создана', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось создать страницу'
    } finally {
      saving = false
    }
  }

  async function savePage() {
    if (!selectedPage) return
    saving = true
    error = ''
    try {
      const data = await fetchJson<{ ok: boolean; page: LandingPage }>(
        buildLandingPageAdminUrl(selectedPage.slug),
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(draft),
        },
      )
      pages = pages.map((page) => (page.slug === data.page.slug ? data.page : page))
      toast({ content: 'Страница сохранена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось сохранить страницу'
    } finally {
      saving = false
    }
  }

  function setImageFile(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    imageFile = input.files?.[0] ?? null
  }

  async function uploadImage() {
    if (!selectedPage) return
    imageSaving = true
    error = ''
    try {
      const form = new FormData()
      Object.entries(imageDraft).forEach(([key, value]) => form.set(key, String(value)))
      if (imageFile) {
        form.set('image', imageFile)
      }
      const data = await fetchJson<{ ok: boolean; image: LandingImage }>(
        buildLandingPageAdminImagesUrl(selectedPage.slug),
        {
          method: 'POST',
          body: form,
        },
      )
      pages = pages.map((page) =>
        page.slug === selectedPage.slug
          ? { ...page, images: [...page.images, data.image].sort((a, b) => a.sort_order - b.sort_order) }
          : page
      )
      imageFile = null
      imageDraft = {
        slot: 'hero',
        title: 'Главный скриншот',
        alt_text: '',
        image_url: '',
        is_active: true,
        sort_order: 10,
      }
      toast({ content: 'Картинка добавлена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось добавить картинку'
    } finally {
      imageSaving = false
    }
  }

  async function deleteImage(image: LandingImage) {
    if (!window.confirm('Удалить картинку?')) return
    error = ''
    try {
      await fetchJson<{ ok: boolean }>(buildLandingPageAdminImageUrl(image.id), {
        method: 'DELETE',
      })
      pages = pages.map((page) =>
        page.slug === selectedSlug
          ? { ...page, images: page.images.filter((item) => item.id !== image.id) }
          : page
      )
      toast({ content: 'Картинка удалена', type: 'success' })
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось удалить картинку'
    }
  }

  onMount(async () => {
    if (!browser) return
    const currentUser = $siteUser || (await refreshSiteUser())
    if (!currentUser) {
      goto(`/login?next=${encodeURIComponent('/l/admin')}`)
      return
    }
    if (!currentUser.is_staff) {
      goto('/l/communities')
      return
    }
    await loadAdmin()
  })

  $: if (selectedPage) {
    const isDifferent =
      draft.title === '' ||
      (selectedSlug &&
        selectedPage.slug === selectedSlug &&
        draft.title !== selectedPage.title &&
        !saving)
    if (isDifferent && draft.title === '') {
      syncDraft(selectedPage)
    }
  }
</script>

<svelte:head>
  <title>Посадочные страницы: управление</title>
  <meta name="robots" content="noindex,nofollow" />
</svelte:head>

<main class="admin-page">
  <header class="admin-header">
    <div>
      <a class="back-link" href="/l/communities">к первой посадочной</a>
      <h1>Посадочные страницы</h1>
      <p>Публикуются по адресу /l/имя_страницы. Картинки можно загрузить здесь или указать внешней ссылкой.</p>
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
    <div class="admin-grid">
      <aside class="panel page-list">
        <h2>Список</h2>
        {#each pages as item}
          <button
            class:active={selectedSlug === item.slug}
            type="button"
            on:click={() => {
              selectedSlug = item.slug
              syncDraft(item)
            }}
          >
            <strong>{item.title}</strong>
            <span>/l/{item.slug}</span>
          </button>
        {/each}
      </aside>

      <section class="panel editor-panel">
        {#if selectedPage}
          <div class="panel-head">
            <h2>Редактирование</h2>
            <a class="view-link" href={selectedPage.url} target="_blank" rel="noreferrer">
              <Icon src={Eye} size="18" mini />
              Открыть
            </a>
          </div>

          <div class="form-grid">
            <label>
              Заголовок
              <input bind:value={draft.title} />
            </label>
            <label>
              Шаблон
              <input bind:value={draft.template_slug} />
            </label>
            <label>
              Порядок
              <input type="number" min="0" bind:value={draft.sort_order} />
            </label>
            <label class="checkbox-row">
              <input type="checkbox" bind:checked={draft.is_published} />
              Опубликована
            </label>
            <label class="wide">
              Description
              <textarea rows="3" bind:value={draft.description}></textarea>
            </label>
          </div>
          <Button on:click={savePage} disabled={saving}>{saving ? 'Сохраняем...' : 'Сохранить страницу'}</Button>

          <div class="images-section">
            <h3>Картинки страницы</h3>
            <div class="image-list">
              {#each selectedPage.images as image}
                <article>
                  {#if image.image_url}
                    <img src={image.image_url} alt={image.alt_text || image.title} />
                  {:else}
                    <div class="empty-image">нет картинки</div>
                  {/if}
                  <div>
                    <strong>{image.title}</strong>
                    <span>slot: {image.slot}</span>
                    <span>{image.is_active ? 'активна' : 'скрыта'} · порядок {image.sort_order}</span>
                  </div>
                  <button type="button" class="icon-button" aria-label="Удалить" on:click={() => deleteImage(image)}>
                    <Icon src={Trash} size="18" mini />
                  </button>
                </article>
              {/each}
              {#if selectedPage.images.length === 0}
                <p class="muted-text">Картинок пока нет. На странице будет показана интерфейсная заглушка.</p>
              {/if}
            </div>
          </div>

          <form class="upload-form" on:submit|preventDefault={uploadImage}>
            <h3>Добавить картинку</h3>
            <div class="form-grid">
              <label>
                Slot
                <input bind:value={imageDraft.slot} placeholder="hero" />
              </label>
              <label>
                Название
                <input bind:value={imageDraft.title} />
              </label>
              <label>
                Порядок
                <input type="number" min="0" bind:value={imageDraft.sort_order} />
              </label>
              <label class="checkbox-row">
                <input type="checkbox" bind:checked={imageDraft.is_active} />
                Активна
              </label>
              <label class="wide">
                Alt text
                <input bind:value={imageDraft.alt_text} />
              </label>
              <label class="wide">
                Внешняя ссылка, если не загружаете файл
                <input bind:value={imageDraft.image_url} placeholder="https://..." />
              </label>
              <label class="wide">
                Файл
                <input type="file" accept="image/*" on:change={setImageFile} />
              </label>
            </div>
            <Button type="submit" disabled={imageSaving}>
              <Icon src={Plus} size="18" mini slot="prefix" />
              {imageSaving ? 'Добавляем...' : 'Добавить картинку'}
            </Button>
          </form>
        {:else}
          <p>Выберите страницу из списка.</p>
        {/if}
      </section>

      <section class="panel create-panel">
        <h2>Новая страница</h2>
        <form class="stack-form" on:submit|preventDefault={createPage}>
          <label>
            Slug
            <input bind:value={newPage.slug} required placeholder="my-page" />
          </label>
          <label>
            Заголовок
            <input bind:value={newPage.title} required />
          </label>
          <label>
            Description
            <textarea rows="4" bind:value={newPage.description}></textarea>
          </label>
          <Button type="submit" disabled={saving}>Создать</Button>
        </form>
      </section>
    </div>
  {/if}
</main>

<style>
  .admin-page {
    width: min(1280px, calc(100% - 32px));
    margin: 0 auto;
    padding: 104px 0 48px;
    color: #111827;
  }

  .admin-header,
  .panel-head {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    justify-content: space-between;
  }

  h1,
  h2,
  h3,
  p {
    letter-spacing: 0;
  }

  h1 {
    margin: 4px 0 8px;
    font-size: clamp(34px, 5vw, 56px);
    line-height: 1;
    font-weight: 900;
  }

  h2 {
    margin: 0 0 16px;
    font-size: 24px;
    font-weight: 900;
  }

  h3 {
    margin: 0 0 14px;
    font-size: 18px;
    font-weight: 900;
  }

  p,
  .muted-text {
    color: #64748b;
  }

  .back-link,
  .view-link {
    color: #2563eb;
    font-weight: 800;
    text-decoration: none;
  }

  .view-link {
    display: inline-flex;
    gap: 8px;
    align-items: center;
  }

  .notice {
    border: 1px solid #fecaca;
    border-radius: 8px;
    background: #fef2f2;
    color: #991b1b;
    margin: 18px 0;
    padding: 12px 14px;
  }

  .admin-grid {
    display: grid;
    grid-template-columns: 260px minmax(0, 1fr) 300px;
    gap: 16px;
    margin-top: 24px;
  }

  .panel {
    border: 1px solid #d8dee8;
    border-radius: 8px;
    background: #ffffff;
    padding: 18px;
  }

  .page-list {
    align-self: start;
    display: grid;
    gap: 10px;
  }

  .page-list button {
    display: grid;
    gap: 4px;
    width: 100%;
    border: 1px solid #d8dee8;
    border-radius: 8px;
    background: #f8fafc;
    cursor: pointer;
    padding: 12px;
    text-align: left;
  }

  .page-list button.active {
    border-color: #2563eb;
    background: #dbeafe;
  }

  .page-list span,
  .image-list span {
    color: #64748b;
    font-size: 13px;
  }

  .form-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }

  .wide {
    grid-column: 1 / -1;
  }

  label,
  .stack-form {
    display: grid;
    gap: 7px;
    color: #374151;
    font-weight: 800;
  }

  .stack-form {
    gap: 14px;
  }

  input,
  textarea {
    width: 100%;
    border: 1px solid #d8dee8;
    border-radius: 8px;
    color: #111827;
    font: inherit;
    padding: 10px 12px;
  }

  .checkbox-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .checkbox-row input {
    width: auto;
  }

  .images-section,
  .upload-form {
    border-top: 1px solid #e5e7eb;
    margin-top: 22px;
    padding-top: 22px;
  }

  .image-list {
    display: grid;
    gap: 10px;
  }

  .image-list article {
    display: grid;
    grid-template-columns: 108px minmax(0, 1fr) 38px;
    gap: 12px;
    align-items: center;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px;
  }

  .image-list img,
  .empty-image {
    width: 108px;
    aspect-ratio: 16 / 10;
    border-radius: 8px;
    background: #f1f5f9;
    object-fit: cover;
  }

  .empty-image {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #64748b;
    font-size: 12px;
  }

  .image-list article > div {
    display: grid;
    gap: 3px;
    min-width: 0;
  }

  .icon-button {
    display: inline-flex;
    width: 34px;
    height: 34px;
    align-items: center;
    justify-content: center;
    border: 1px solid #fecaca;
    border-radius: 8px;
    background: #fff1f2;
    color: #b91c1c;
    cursor: pointer;
  }

  .create-panel {
    align-self: start;
  }

  @media (max-width: 1100px) {
    .admin-grid {
      grid-template-columns: 1fr;
    }
  }

  @media (max-width: 680px) {
    .admin-header,
    .panel-head {
      display: grid;
    }

    .form-grid,
    .image-list article {
      grid-template-columns: 1fr;
    }
  }
</style>
