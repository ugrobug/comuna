<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import { TextInput, toast } from 'mono-svelte'
  import {
    autofillMovieReviewTemplateByImdb,
    resolveVotePollPostByReference,
    searchPostsForVotePoll,
    uploadSiteImage,
    type VotePollPostCandidate,
  } from '$lib/siteAuth'
  import {
    MUSIC_RELEASE_STYLE_OPTIONS,
    MOVIE_REVIEW_GENRE_OPTIONS,
    MOVIE_REVIEW_KIND_OPTIONS,
    MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS,
    POST_TEMPLATE_TYPE_OPTIONS,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    formatPostVotePollDeadline,
    normalizeAllowedPostTemplateTypes,
    normalizeMusicReleaseTemplateData,
    normalizeMovieReviewTemplateData,
    normalizePostVotePollTemplateData,
    postVotePollOptionLabel,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostTemplateType,
    type PostVotePollTemplateData,
    type PostVotePollTemplateItem,
  } from '$lib/postTemplates'

  export let templateType: '' | PostTemplateType = ''
  export let movieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  export let postVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  export let musicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  export let allowedTemplateTypes: string[] | undefined = undefined
  export let showTypeSelector = true

  let posterInput: HTMLInputElement | null = null
  let posterUploading = false
  let coverInput: HTMLInputElement | null = null
  let coverUploading = false
  let imdbAutofillLoading = false
  let watchProviderValues: string[] = []
  let watchProviderSet = new Set<string>()
  let watchProviderLabels: string[] = []
  let allowedTemplateTypeSet = new Set<string>()
  let availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS

  let votePollReference = ''
  let votePollReferenceLoading = false
  let votePollSearchQuery = ''
  let votePollSearchLoading = false
  let votePollSearchError = ''
  let votePollSearchResults: VotePollPostCandidate[] = []
  let votePollItems: PostVotePollTemplateItem[] = []
  let votePollItemIds = new Set<number>()
  let votePollDeadlineInput = ''
  let templateMenuOpen = false
  let templateMenuRef: HTMLDivElement | null = null
  let hasTemplateTypeChoice = false
  let shouldRenderTemplateBlock = false
  let selectedTemplateOption = POST_TEMPLATE_TYPE_OPTIONS[0]

  $: allowedTemplateTypeSet = new Set(normalizeAllowedPostTemplateTypes(allowedTemplateTypes))
  $: availableTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS.filter((option) =>
    option.value ? allowedTemplateTypeSet.has(option.value) : allowedTemplateTypeSet.has('basic')
  )
  $: hasTemplateTypeChoice = availableTemplateTypeOptions.length > 1
  $: shouldRenderTemplateBlock = (showTypeSelector && hasTemplateTypeChoice) || Boolean(templateType)
  $: selectedTemplateOption =
    availableTemplateTypeOptions.find((option) => option.value === templateType) ??
    availableTemplateTypeOptions[0] ??
    POST_TEMPLATE_TYPE_OPTIONS[0]
  $: if (!availableTemplateTypeOptions.some((option) => option.value === templateType)) {
    templateType = availableTemplateTypeOptions[0]?.value ?? ''
  }

  const selectedWatchProviders = (value: unknown): string[] => {
    if (!Array.isArray(value)) return []
    const seen = new Set<string>()
    const values: string[] = []
    for (const item of value) {
      const provider = typeof item === 'string' ? item.trim() : ''
      if (!provider) continue
      const dedupeKey = provider.toLowerCase()
      if (seen.has(dedupeKey)) continue
      seen.add(dedupeKey)
      values.push(provider)
    }
    return values
  }

  const formatDateTimeLocalValue = (value: string | undefined): string => {
    const raw = (value || '').trim()
    if (!raw) return ''
    const timestamp = Date.parse(raw)
    if (!Number.isFinite(timestamp)) return ''
    const date = new Date(timestamp)
    const year = String(date.getFullYear())
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day}T${hour}:${minute}`
  }

  const normalizeVotePollData = (value: Partial<PostVotePollTemplateData>) => {
    postVotePollData = normalizePostVotePollTemplateData({
      ...postVotePollData,
      ...value,
    })
  }

  const addVotePollItem = (item: VotePollPostCandidate) => {
    const normalized = normalizePostVotePollTemplateData(postVotePollData)
    const currentItems = normalized.items ?? []
    if (currentItems.some((entry) => entry.post_id === item.post_id)) {
      toast({ content: 'Этот пост уже добавлен', type: 'error' })
      return
    }
    if (currentItems.length >= 10) {
      toast({ content: 'Можно добавить не более 10 постов', type: 'error' })
      return
    }

    normalizeVotePollData({
      items: [
        ...currentItems,
        {
          post_id: item.post_id,
          title: item.title,
          path: item.path,
          author_username: item.author_username,
        },
      ],
    })
  }

  const removeVotePollItem = (postId: number) => {
    const normalized = normalizePostVotePollTemplateData(postVotePollData)
    const currentItems = normalized.items ?? []
    normalizeVotePollData({
      items: currentItems.filter((item) => item.post_id !== postId),
    })
  }

  const addVotePollItemByReference = async () => {
    const reference = votePollReference.trim()
    if (!reference || votePollReferenceLoading) return

    votePollReferenceLoading = true
    try {
      const candidate = await resolveVotePollPostByReference(reference)
      addVotePollItem(candidate)
      votePollReference = ''
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось добавить пост по ссылке',
        type: 'error',
      })
    } finally {
      votePollReferenceLoading = false
    }
  }

  const searchVotePoll = async () => {
    const query = votePollSearchQuery.trim()
    if (!query) {
      votePollSearchResults = []
      votePollSearchError = ''
      return
    }
    if (votePollSearchLoading) return

    votePollSearchLoading = true
    votePollSearchError = ''
    try {
      votePollSearchResults = await searchPostsForVotePoll(query, 10)
    } catch (error) {
      votePollSearchResults = []
      votePollSearchError = (error as Error)?.message ?? 'Не удалось выполнить поиск'
    } finally {
      votePollSearchLoading = false
    }
  }

  const onVotePollDeadlineChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    normalizeVotePollData({ ends_at: input?.value || '' })
  }

  const onVotePollMultipleChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    normalizeVotePollData({ allows_multiple_answers: Boolean(input?.checked) })
  }

  const onVotePollQuestionInput = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    normalizeVotePollData({ question: input?.value || '' })
  }

  const selectTemplateType = (value: '' | PostTemplateType) => {
    templateType = value
    templateMenuOpen = false
  }

  $: watchProviderValues = selectedWatchProviders(movieReviewData.watch_where)
  $: watchProviderSet = new Set(watchProviderValues)
  $: watchProviderLabels = MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS
    .filter((option) => watchProviderSet.has(option.value))
    .map((option) => option.label)

  $: votePollItems = normalizePostVotePollTemplateData(postVotePollData).items ?? []
  $: votePollItemIds = new Set(votePollItems.map((item) => item.post_id))
  $: votePollDeadlineInput = formatDateTimeLocalValue(postVotePollData.ends_at)

  const toggleWatchProvider = (provider: string, enabled: boolean) => {
    const next = new Set(watchProviderValues)
    if (enabled) {
      next.add(provider)
    } else {
      next.delete(provider)
    }
    movieReviewData = {
      ...movieReviewData,
      watch_where: Array.from(next),
    }
  }

  const onWatchProviderChange = (provider: string, event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    toggleWatchProvider(provider, Boolean(input?.checked))
  }

  const pickPoster = () => {
    posterInput?.click()
  }

  const removePoster = () => {
    movieReviewData = {
      ...movieReviewData,
      poster_url: '',
    }
  }

  const onPosterSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || posterUploading) return
    posterUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      movieReviewData = {
        ...movieReviewData,
        poster_url: uploadedUrl,
      }
      toast({
        content: 'Постер загружен',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось загрузить постер',
        type: 'error',
      })
    } finally {
      posterUploading = false
      if (input) input.value = ''
    }
  }

  const pickCover = () => {
    coverInput?.click()
  }

  const removeCover = () => {
    musicReleaseData = {
      ...musicReleaseData,
      cover_image_url: '',
    }
  }

  const onCoverSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || coverUploading) return
    coverUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      musicReleaseData = normalizeMusicReleaseTemplateData({
        ...musicReleaseData,
        cover_image_url: uploadedUrl,
      })
      toast({
        content: 'Обложка загружена',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось загрузить обложку',
        type: 'error',
      })
    } finally {
      coverUploading = false
      if (input) input.value = ''
    }
  }

  const autofillFromImdb = async () => {
    const imdbUrl = (movieReviewData.imdb_url || '').trim()
    if (!imdbUrl) {
      toast({ content: 'Сначала укажите ссылку IMDb', type: 'error' })
      return
    }
    if (imdbAutofillLoading) return

    imdbAutofillLoading = true
    try {
      const payload = await autofillMovieReviewTemplateByImdb(imdbUrl)
      const merged = normalizeMovieReviewTemplateData({
        ...movieReviewData,
        ...payload.data,
        imdb_url: payload.data.imdb_url || imdbUrl,
      })
      movieReviewData = {
        ...movieReviewData,
        ...merged,
      }
      const sourcesSuffix = payload.sources.length ? ` (${payload.sources.join(', ')})` : ''
      toast({ content: `Поля заполнены по IMDb${sourcesSuffix}`, type: 'success' })
      if (payload.warnings.length) {
        toast({ content: payload.warnings[0], type: 'success' })
      }
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось заполнить поля',
        type: 'error',
      })
    } finally {
      imdbAutofillLoading = false
    }
  }

  onMount(() => {
    const closeOnOutsideClick = (event: MouseEvent) => {
      if (!templateMenuOpen || !templateMenuRef) return
      const target = event.target as Node | null
      if (target && !templateMenuRef.contains(target)) {
        templateMenuOpen = false
      }
    }
    document.addEventListener('click', closeOnOutsideClick)
    return () => {
      document.removeEventListener('click', closeOnOutsideClick)
    }
  })

  onDestroy(() => {
    templateMenuOpen = false
  })
</script>

{#if shouldRenderTemplateBlock}
  <div class="template-fields rounded-xl bg-slate-50/70 dark:bg-zinc-900/50 p-4 sm:p-5 flex flex-col gap-4">
    {#if showTypeSelector && hasTemplateTypeChoice}
      <div class="relative w-full" bind:this={templateMenuRef}>
        <button
          type="button"
          class="flex max-w-full items-center gap-2 text-left text-sm font-medium leading-tight text-slate-800 dark:text-zinc-200"
          aria-haspopup="listbox"
          aria-expanded={templateMenuOpen}
          on:click={() => (templateMenuOpen = !templateMenuOpen)}
        >
          <span class="min-w-0 text-sm text-slate-700 dark:text-zinc-200 whitespace-normal break-words">
            Тип публикации: <span class="font-medium">{selectedTemplateOption.label}</span>
          </span>
          <svg
            class="h-4 w-4 text-slate-500 dark:text-zinc-400 flex-shrink-0"
            viewBox="0 0 20 20"
            fill="currentColor"
            aria-hidden="true"
          >
            <path
              fill-rule="evenodd"
              d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.24 4.5a.75.75 0 01-1.08 0l-4.24-4.5a.75.75 0 01.02-1.06z"
              clip-rule="evenodd"
            />
          </svg>
        </button>

        {#if templateMenuOpen}
          <div
            class="absolute z-20 mt-2 w-full rounded-lg border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-lg max-h-72 overflow-auto"
            role="listbox"
          >
            {#each availableTemplateTypeOptions as option}
              <button
                type="button"
                class={`flex w-full items-center px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-zinc-800 ${
                  templateType === option.value ? 'bg-slate-100 dark:bg-zinc-800' : ''
                }`}
                on:click={() => selectTemplateType(option.value)}
              >
                <span class="flex-1 whitespace-normal text-slate-700 dark:text-zinc-200">
                  {option.label}
                </span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    {#if templateType === 'movie_review'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <TextInput label="Название" bind:value={movieReviewData.title} placeholder="Например, Дюна: Часть вторая" />
      <TextInput
        label="Оригинальное название"
        bind:value={movieReviewData.original_title}
        placeholder="Например, Dune: Part Two"
      />
      <TextInput
        label="Ссылка на IMDb"
        bind:value={movieReviewData.imdb_url}
        placeholder="https://www.imdb.com/title/..."
      />
      <div class="md:col-span-2 flex justify-start">
        <button
          type="button"
          class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
          on:click={autofillFromImdb}
          disabled={imdbAutofillLoading}
        >
          {imdbAutofillLoading ? 'Заполняем...' : 'Заполнить автоматически по IMDb'}
        </button>
      </div>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Постер</span>
        <input
          bind:this={posterInput}
          type="file"
          accept="image/*"
          class="hidden"
          on:change={onPosterSelected}
        />
        <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
          <div class="h-20 w-14 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if movieReviewData.poster_url}
              <img src={movieReviewData.poster_url} alt="Постер" class="h-full w-full object-cover" />
            {:else}
              <div class="h-full w-full grid place-items-center text-[10px] text-slate-400 dark:text-zinc-500 text-center px-1">
                Нет постера
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-700 dark:text-zinc-300">
              {#if posterUploading}
                Загрузка постера...
              {:else if movieReviewData.poster_url}
                Постер загружен
              {:else}
                Загрузите файл постера
              {/if}
            </div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">PNG, JPG, WEBP, GIF</div>
          </div>
          <div class="flex flex-wrap gap-2 justify-end">
            <button
              type="button"
              class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
              on:click={pickPoster}
              disabled={posterUploading}
            >
              {movieReviewData.poster_url ? 'Заменить' : 'Загрузить'}
            </button>
            {#if movieReviewData.poster_url}
              <button
                type="button"
                class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                on:click={removePoster}
                disabled={posterUploading}
              >
                Убрать
              </button>
            {/if}
          </div>
        </div>
      </div>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Жанр</span>
        <select
          bind:value={movieReviewData.genre}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          <option value="">Не выбран</option>
          {#each MOVIE_REVIEW_GENRE_OPTIONS as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Тип</span>
        <select
          bind:value={movieReviewData.content_kind}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          {#each MOVIE_REVIEW_KIND_OPTIONS as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Дата премьеры</span>
        <input
          type="date"
          bind:value={movieReviewData.release_date}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Оценка автора (0-10)</span>
        <input
          type="text"
          inputmode="decimal"
          bind:value={movieReviewData.author_rating}
          placeholder="Например, 8.5"
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Где посмотреть</span>
        <details class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900">
          <summary class="list-none cursor-pointer px-3 py-2 text-sm text-slate-900 dark:text-zinc-100 flex items-center justify-between gap-3">
            <span class="truncate">
              {watchProviderLabels.length ? watchProviderLabels.join(', ') : 'Выберите онлайн-кинотеатры'}
            </span>
            <span class="text-xs text-slate-500 dark:text-zinc-400">▼</span>
          </summary>
          <div class="p-2 border-t border-slate-200 dark:border-zinc-800 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {#each MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS as option}
              <label class="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/40 px-3 py-2 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/70">
                <input
                  type="checkbox"
                  class="accent-slate-900 dark:accent-zinc-200"
                  checked={watchProviderSet.has(option.value)}
                  on:change={(event) => onWatchProviderChange(option.value, event)}
                />
                <span class="text-sm text-slate-700 dark:text-zinc-200">{option.label}</span>
              </label>
            {/each}
          </div>
        </details>
      </div>
    </div>
    {:else if templateType === 'music_release'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <TextInput
        label="Название группы"
        bind:value={musicReleaseData.artist_name}
        placeholder="Например, Radiohead"
      />
      <TextInput
        label="Название альбома/сингла"
        bind:value={musicReleaseData.release_title}
        placeholder="Например, OK Computer"
      />

      <TextInput
        label="Ссылка на альбом"
        bind:value={musicReleaseData.album_url}
        placeholder="https://open.spotify.com/album/..."
      />

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Дата релиза</span>
        <input
          type="date"
          bind:value={musicReleaseData.release_date}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <TextInput
        label="Страна группы"
        bind:value={musicReleaseData.country}
        placeholder="Например, Великобритания"
      />
      <TextInput
        label="Город группы"
        bind:value={musicReleaseData.city}
        placeholder="Например, Лондон"
      />

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Музыкальный стиль</span>
        <select
          bind:value={musicReleaseData.style}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          <option value="">Не выбран</option>
          {#each MUSIC_RELEASE_STYLE_OPTIONS as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Фото обложки</span>
        <input
          bind:this={coverInput}
          type="file"
          accept="image/*"
          class="hidden"
          on:change={onCoverSelected}
        />
        <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
          <div class="h-16 w-16 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if musicReleaseData.cover_image_url}
              <img
                src={musicReleaseData.cover_image_url}
                alt="Обложка релиза"
                class="h-full w-full object-cover"
              />
            {:else}
              <div class="h-full w-full grid place-items-center text-[10px] text-slate-400 dark:text-zinc-500 text-center px-1">
                Нет обложки
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-700 dark:text-zinc-300">
              {#if coverUploading}
                Загрузка обложки...
              {:else if musicReleaseData.cover_image_url}
                Обложка загружена
              {:else}
                Загрузите файл обложки
              {/if}
            </div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">PNG, JPG, WEBP, GIF</div>
          </div>
          <div class="flex flex-wrap gap-2 justify-end">
            <button
              type="button"
              class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
              on:click={pickCover}
              disabled={coverUploading}
            >
              {musicReleaseData.cover_image_url ? 'Заменить' : 'Загрузить'}
            </button>
            {#if musicReleaseData.cover_image_url}
              <button
                type="button"
                class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                on:click={removeCover}
                disabled={coverUploading}
              >
                Убрать
              </button>
            {/if}
          </div>
        </div>
      </div>
    </div>
    {:else if templateType === 'post_vote_poll'}
    <div class="flex flex-col gap-4">
      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Вопрос голосования (необязательно)</span>
        <input
          type="text"
          value={postVotePollData.question || ''}
          on:input={onVotePollQuestionInput}
          placeholder="Например, Какой пост лучший в этом месяце?"
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Срок голосования</span>
        <input
          type="datetime-local"
          value={votePollDeadlineInput}
          on:change={onVotePollDeadlineChange}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
        {#if postVotePollData.ends_at}
          <span class="text-xs text-slate-500 dark:text-zinc-400">
            Завершится: {formatPostVotePollDeadline(postVotePollData.ends_at)}
          </span>
        {/if}
      </label>

      <label class="flex items-start gap-2 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 cursor-pointer">
        <input
          type="checkbox"
          class="mt-0.5 accent-slate-900 dark:accent-zinc-200"
          checked={Boolean(postVotePollData.allows_multiple_answers)}
          on:change={onVotePollMultipleChange}
        />
        <span class="min-w-0">
          <span class="block text-sm text-slate-900 dark:text-zinc-100">
            Голосование за несколько вариантов
          </span>
          <span class="block text-xs text-slate-500 dark:text-zinc-400">
            Если включено, пользователь может выбрать несколько постов в одном голосовании.
          </span>
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Добавить пост по ссылке</span>
        <div class="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            bind:value={votePollReference}
            placeholder="/b/post/123 или https://.../b/post/123"
            class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
          />
          <button
            type="button"
            on:click={addVotePollItemByReference}
            disabled={votePollReferenceLoading}
            class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-2 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
          >
            {votePollReferenceLoading ? 'Добавляем...' : 'Добавить'}
          </button>
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Поиск постов</span>
        <div class="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            bind:value={votePollSearchQuery}
            on:keydown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault()
                searchVotePoll()
              }
            }}
            placeholder="Название поста или автор"
            class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
          />
          <button
            type="button"
            on:click={searchVotePoll}
            disabled={votePollSearchLoading}
            class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-2 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
          >
            {votePollSearchLoading ? 'Ищем...' : 'Найти'}
          </button>
        </div>
        {#if votePollSearchError}
          <p class="text-xs text-red-600">{votePollSearchError}</p>
        {/if}
        {#if votePollSearchResults.length}
          <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 divide-y divide-slate-100 dark:divide-zinc-800">
            {#each votePollSearchResults as result (result.post_id)}
              <div class="px-3 py-2 flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <a
                    href={result.path || `/b/post/${result.post_id}`}
                    target="_blank"
                    rel="noopener"
                    class="text-sm text-slate-800 dark:text-zinc-100 hover:underline"
                  >
                    {result.title || `Пост #${result.post_id}`}
                  </a>
                  {#if result.author_username}
                    <div class="text-xs text-slate-500 dark:text-zinc-400">@{result.author_username}</div>
                  {/if}
                </div>
                <button
                  type="button"
                  class="rounded-md border border-slate-300 dark:border-zinc-700 px-2.5 py-1 text-xs text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                  disabled={votePollItemIds.has(result.post_id)}
                  on:click={() => addVotePollItem(result)}
                >
                  {votePollItemIds.has(result.post_id) ? 'Добавлен' : 'Добавить'}
                </button>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Выбранные посты</span>
          <span class="text-xs text-slate-500 dark:text-zinc-400">{votePollItems.length}/10</span>
        </div>
        {#if votePollItems.length}
          <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 divide-y divide-slate-100 dark:divide-zinc-800">
            {#each votePollItems as item (item.post_id)}
              <div class="px-3 py-2 flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <a
                    href={item.path || `/b/post/${item.post_id}`}
                    target="_blank"
                    rel="noopener"
                    class="text-sm text-slate-800 dark:text-zinc-100 hover:underline"
                  >
                    {postVotePollOptionLabel(item)}
                  </a>
                  {#if item.author_username}
                    <div class="text-xs text-slate-500 dark:text-zinc-400">@{item.author_username}</div>
                  {/if}
                </div>
                <button
                  type="button"
                  class="rounded-md border border-slate-300 dark:border-zinc-700 px-2.5 py-1 text-xs text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800"
                  on:click={() => removeVotePollItem(item.post_id)}
                >
                  Удалить
                </button>
              </div>
            {/each}
          </div>
        {:else}
          <div class="rounded-xl border border-dashed border-slate-300 dark:border-zinc-700 px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
            Пока не добавлено ни одного поста.
          </div>
        {/if}
        <p class="text-xs text-slate-500 dark:text-zinc-400">
          Для публикации голосования добавьте минимум 2 поста и укажите срок голосования.
        </p>
      </div>
    </div>
    {/if}
  </div>
{/if}
