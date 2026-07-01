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
    BUG_REPORT_BROWSER_OPTIONS,
    BUG_REPORT_PLATFORM_OPTIONS,
    MUSIC_RELEASE_STYLE_OPTIONS,
    MOVIE_REVIEW_GENRE_OPTIONS,
    MOVIE_REVIEW_KIND_OPTIONS,
    MOVIE_REVIEW_WATCH_PROVIDER_OPTIONS,
    POST_TEMPLATE_TYPE_OPTIONS,
    bugReportBrowserLabel,
    bugReportBrowserLabels,
    bugReportPlatformLabel,
    bugReportPlatformLabels,
    createEmptyBugReportTemplateData,
    createEmptyMusicReleaseTemplateData,
    createEmptyMovieReviewTemplateData,
    createEmptyPostVotePollTemplateData,
    formatPostVotePollDeadline,
    movieReviewGenreLabel,
    movieReviewKindLabel,
    musicReleaseStyleLabel,
    normalizeAllowedPostTemplateTypes,
    normalizeBugReportTemplateData,
    normalizePostTemplateTypeOptions,
    normalizeMusicReleaseTemplateData,
    normalizeMovieReviewTemplateData,
    normalizePostVotePollTemplateData,
    postVotePollOptionLabel,
    type BugReportTemplateData,
    type MusicReleaseTemplateData,
    type MovieReviewTemplateData,
    type PostTemplateType,
    type PostTemplateTypeOption,
    type PostVotePollTemplateData,
    type PostVotePollTemplateItem,
  } from '$lib/postTemplates'
  import { t } from '$lib/translations'

  export let templateType: '' | PostTemplateType = ''
  export let movieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
  export let postVotePollData: PostVotePollTemplateData = createEmptyPostVotePollTemplateData()
  export let musicReleaseData: MusicReleaseTemplateData = createEmptyMusicReleaseTemplateData()
  export let bugReportData: BugReportTemplateData = createEmptyBugReportTemplateData()
  export let allowedTemplateTypes: string[] | undefined = undefined
  export let templateTypeOptions: PostTemplateTypeOption[] = POST_TEMPLATE_TYPE_OPTIONS
  export let showTypeSelector = true

  let posterInput: HTMLInputElement | null = null
  let posterUploading = false
  let coverInput: HTMLInputElement | null = null
  let coverUploading = false
  let bugScreenshotInput: HTMLInputElement | null = null
  let bugScreenshotUploading = false
  let imdbAutofillLoading = false
  let watchProviderValues: string[] = []
  let watchProviderSet = new Set<string>()
  let watchProviderLabels: string[] = []
  let allowedTemplateTypeSet = new Set<string>()
  let normalizedTemplateTypeOptions = POST_TEMPLATE_TYPE_OPTIONS
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
  let bugPlatformValues: string[] = []
  let bugPlatformSet = new Set<string>()
  let bugPlatformLabelValues: string[] = []
  let bugBrowserValues: string[] = []
  let bugBrowserSet = new Set<string>()
  let bugBrowserLabelValues: string[] = []
  let templateMenuOpen = false
  let templateMenuRef: HTMLDivElement | null = null
  let hasTemplateTypeChoice = false
  let shouldRenderTemplateBlock = false
  let selectedTemplateOption = POST_TEMPLATE_TYPE_OPTIONS[0]

  const templateOptionKey = (value: string) => value || 'basic'
  const templateOptionLabel = (option: PostTemplateTypeOption) =>
    $t(`site.templateFields.types.${templateOptionKey(option.value)}.label`) || option.label
  const templateOptionDescription = (option: PostTemplateTypeOption) =>
    option.description
      ? $t(`site.templateFields.types.${templateOptionKey(option.value)}.description`) || option.description
      : ''

  $: allowedTemplateTypeSet = new Set(normalizeAllowedPostTemplateTypes(allowedTemplateTypes))
  $: normalizedTemplateTypeOptions = normalizePostTemplateTypeOptions(templateTypeOptions)
  $: availableTemplateTypeOptions = normalizedTemplateTypeOptions.filter((option) =>
    option.value ? allowedTemplateTypeSet.has(option.value) : allowedTemplateTypeSet.has('basic')
  )
  $: hasTemplateTypeChoice = availableTemplateTypeOptions.length > 1
  $: shouldRenderTemplateBlock = (showTypeSelector && hasTemplateTypeChoice) || Boolean(templateType)
  $: selectedTemplateOption =
    availableTemplateTypeOptions.find((option) => option.value === templateType) ??
    availableTemplateTypeOptions[0] ??
    normalizedTemplateTypeOptions[0] ??
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
      toast({ content: $t('site.templateFields.alreadyAdded'), type: 'error' })
      return
    }
    if (currentItems.length >= 10) {
      toast({ content: $t('site.templateFields.maxPosts'), type: 'error' })
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
        content: (error as Error)?.message ?? $t('site.templateFields.addByLinkError'),
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
      votePollSearchError = (error as Error)?.message ?? $t('site.templateFields.searchError')
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
  $: bugPlatformValues = normalizeBugReportTemplateData(bugReportData).platforms ?? []
  $: bugPlatformSet = new Set(bugPlatformValues)
  $: bugPlatformLabelValues = bugReportPlatformLabels(bugPlatformValues)
  $: bugBrowserValues = normalizeBugReportTemplateData(bugReportData).browsers ?? []
  $: bugBrowserSet = new Set(bugBrowserValues)
  $: bugBrowserLabelValues = bugReportBrowserLabels(bugBrowserValues)

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

  const toggleBugReportValue = (
    values: string[],
    selectedValue: string,
    enabled: boolean
  ): string[] => {
    const next = new Set(values)
    if (enabled) {
      next.add(selectedValue)
    } else {
      next.delete(selectedValue)
    }
    return Array.from(next)
  }

  const onBugPlatformChange = (platform: string, event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    bugReportData = normalizeBugReportTemplateData({
      ...bugReportData,
      platforms: toggleBugReportValue(bugPlatformValues, platform, Boolean(input?.checked)),
    })
  }

  const onBugBrowserChange = (browser: string, event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    bugReportData = normalizeBugReportTemplateData({
      ...bugReportData,
      browsers: toggleBugReportValue(bugBrowserValues, browser, Boolean(input?.checked)),
    })
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
        content: $t('site.templateFields.posterUploaded'),
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('site.templateFields.posterUploadError'),
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
        content: $t('site.templateFields.coverUploaded'),
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('site.templateFields.coverUploadError'),
        type: 'error',
      })
    } finally {
      coverUploading = false
      if (input) input.value = ''
    }
  }

  const pickBugScreenshot = () => {
    bugScreenshotInput?.click()
  }

  const removeBugScreenshot = () => {
    bugReportData = normalizeBugReportTemplateData({
      ...bugReportData,
      screenshot_url: '',
    })
  }

  const onBugScreenshotSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || bugScreenshotUploading) return
    bugScreenshotUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      bugReportData = normalizeBugReportTemplateData({
        ...bugReportData,
        screenshot_url: uploadedUrl,
      })
      toast({
        content: $t('site.templateFields.screenshotUploaded'),
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('site.templateFields.screenshotUploadError'),
        type: 'error',
      })
    } finally {
      bugScreenshotUploading = false
      if (input) input.value = ''
    }
  }

  const autofillFromImdb = async () => {
    const imdbUrl = (movieReviewData.imdb_url || '').trim()
    if (!imdbUrl) {
      toast({ content: $t('site.templateFields.imdbRequired'), type: 'error' })
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
      toast({ content: $t('site.templateFields.imdbFilled', { sources: sourcesSuffix }), type: 'success' })
      if (payload.warnings.length) {
        toast({ content: payload.warnings[0], type: 'success' })
      }
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('site.templateFields.fillError'),
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
            {$t('site.templateFields.publicationType')}: <span class="font-medium">{templateOptionLabel(selectedTemplateOption)}</span>
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
                <span class="flex-1 whitespace-normal">
                  <span class="block text-sm font-medium text-slate-800 dark:text-zinc-100">
                    {templateOptionLabel(option)}
                  </span>
                  {#if templateOptionDescription(option)}
                    <span class="mt-1 block text-xs leading-snug text-slate-500 dark:text-zinc-400">
                      {templateOptionDescription(option)}
                    </span>
                  {/if}
                </span>
              </button>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    {#if templateType === 'movie_review'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <TextInput label={$t('site.templateFields.title')} bind:value={movieReviewData.title} placeholder={$t('site.templateFields.titlePlaceholder')} />
      <TextInput
        label={$t('site.templateFields.originalTitle')}
        bind:value={movieReviewData.original_title}
        placeholder={$t('site.templateFields.originalTitlePlaceholder')}
      />
      <TextInput
        label={$t('site.templateFields.imdbUrl')}
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
          {imdbAutofillLoading ? $t('site.templateFields.autofilling') : $t('site.templateFields.autofillImdb')}
        </button>
      </div>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.poster')}</span>
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
              <img src={movieReviewData.poster_url} alt={$t('site.templateFields.poster')} class="h-full w-full object-cover" />
            {:else}
              <div class="h-full w-full grid place-items-center text-[10px] text-slate-400 dark:text-zinc-500 text-center px-1">
                {$t('site.templateFields.noPoster')}
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-700 dark:text-zinc-300">
              {#if posterUploading}
                {$t('site.templateFields.posterUploading')}
              {:else if movieReviewData.poster_url}
                {$t('site.templateFields.posterUploaded')}
              {:else}
                {$t('site.templateFields.uploadPoster')}
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
              {movieReviewData.poster_url ? $t('site.templateFields.replace') : $t('site.templateFields.upload')}
            </button>
            {#if movieReviewData.poster_url}
              <button
                type="button"
                class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                on:click={removePoster}
                disabled={posterUploading}
              >
                {$t('site.templateFields.remove')}
              </button>
            {/if}
          </div>
        </div>
      </div>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.genre')}</span>
        <select
          bind:value={movieReviewData.genre}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          <option value="">{$t('site.templateFields.notSelected')}</option>
          {#each MOVIE_REVIEW_GENRE_OPTIONS as option}
            <option value={option.value}>{movieReviewGenreLabel(option.value)}</option>
          {/each}
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.type')}</span>
        <select
          bind:value={movieReviewData.content_kind}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          {#each MOVIE_REVIEW_KIND_OPTIONS as option}
            <option value={option.value}>{movieReviewKindLabel(option.value)}</option>
          {/each}
        </select>
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.releaseYear')}</span>
        <input
          type="text"
          inputmode="numeric"
          maxlength="4"
          pattern="(18|19|20)[0-9]{2}"
          bind:value={movieReviewData.release_date}
          placeholder={$t('site.templateFields.releaseYearPlaceholder')}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.authorRating')}</span>
        <input
          type="text"
          inputmode="decimal"
          bind:value={movieReviewData.author_rating}
          placeholder={$t('site.templateFields.authorRatingPlaceholder')}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.watchWhere')}</span>
        <details class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900">
          <summary class="list-none cursor-pointer px-3 py-2 text-sm text-slate-900 dark:text-zinc-100 flex items-center justify-between gap-3">
            <span class="truncate">
              {watchProviderLabels.length ? watchProviderLabels.join(', ') : $t('site.templateFields.chooseCinemas')}
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
                <span class="text-sm text-slate-700 dark:text-zinc-200">{bugReportPlatformLabel(option.value)}</span>
              </label>
            {/each}
          </div>
        </details>
      </div>
    </div>
    {:else if templateType === 'music_release'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <TextInput
        label={$t('site.templateFields.bandName')}
        bind:value={musicReleaseData.artist_name}
        placeholder={$t('site.templateFields.bandPlaceholder')}
      />
      <TextInput
        label={$t('site.templateFields.releaseTitle')}
        bind:value={musicReleaseData.release_title}
        placeholder={$t('site.templateFields.releaseTitlePlaceholder')}
      />

      <TextInput
        label={$t('site.templateFields.albumLink')}
        bind:value={musicReleaseData.album_url}
        placeholder="https://open.spotify.com/album/..."
      />

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.releaseDate')}</span>
        <input
          type="date"
          bind:value={musicReleaseData.release_date}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <TextInput
        label={$t('site.templateFields.bandCountry')}
        bind:value={musicReleaseData.country}
        placeholder={$t('site.templateFields.countryPlaceholder')}
      />
      <TextInput
        label={$t('site.templateFields.bandCity')}
        bind:value={musicReleaseData.city}
        placeholder={$t('site.templateFields.cityPlaceholder')}
      />

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.musicStyle')}</span>
        <select
          bind:value={musicReleaseData.style}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          <option value="">{$t('site.templateFields.notSelected')}</option>
          {#each MUSIC_RELEASE_STYLE_OPTIONS as option}
            <option value={option.value}>{musicReleaseStyleLabel(option.value)}</option>
          {/each}
        </select>
      </label>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.coverPhoto')}</span>
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
                alt={$t('site.templateFields.coverAlt')}
                class="h-full w-full object-cover"
              />
            {:else}
              <div class="h-full w-full grid place-items-center text-[10px] text-slate-400 dark:text-zinc-500 text-center px-1">
                {$t('site.templateFields.noCover')}
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-700 dark:text-zinc-300">
              {#if coverUploading}
                {$t('site.templateFields.coverUploading')}
              {:else if musicReleaseData.cover_image_url}
                {$t('site.templateFields.coverUploaded')}
              {:else}
                {$t('site.templateFields.uploadCover')}
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
              {musicReleaseData.cover_image_url ? $t('site.templateFields.replace') : $t('site.templateFields.upload')}
            </button>
            {#if musicReleaseData.cover_image_url}
              <button
                type="button"
                class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                on:click={removeCover}
                disabled={coverUploading}
              >
                {$t('site.templateFields.remove')}
              </button>
            {/if}
          </div>
        </div>
      </div>
    </div>
    {:else if templateType === 'post_vote_poll'}
    <div class="flex flex-col gap-4">
      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.pollQuestion')}</span>
        <input
          type="text"
          value={postVotePollData.question || ''}
          on:input={onVotePollQuestionInput}
          placeholder={$t('site.templateFields.pollQuestionPlaceholder')}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>

      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.pollDeadline')}</span>
        <input
          type="datetime-local"
          value={votePollDeadlineInput}
          on:change={onVotePollDeadlineChange}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
        {#if postVotePollData.ends_at}
          <span class="text-xs text-slate-500 dark:text-zinc-400">
            {$t('site.templateFields.pollEnds', { date: formatPostVotePollDeadline(postVotePollData.ends_at) })}
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
            {$t('site.templateFields.multipleVoting')}
          </span>
          <span class="block text-xs text-slate-500 dark:text-zinc-400">
            {$t('site.templateFields.multipleVotingHint')}
          </span>
        </span>
      </label>

      <div class="flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.addPostByLink')}</span>
        <div class="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            bind:value={votePollReference}
            placeholder={$t('site.templateFields.addPostPlaceholder')}
            class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
          />
          <button
            type="button"
            on:click={addVotePollItemByReference}
            disabled={votePollReferenceLoading}
            class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-2 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
          >
            {votePollReferenceLoading ? $t('site.templateFields.addingPost') : $t('site.templateFields.add')}
          </button>
        </div>
      </div>

      <div class="flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.searchPosts')}</span>
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
            placeholder={$t('site.templateFields.searchPlaceholder')}
            class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
          />
          <button
            type="button"
            on:click={searchVotePoll}
            disabled={votePollSearchLoading}
            class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-2 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
          >
            {votePollSearchLoading ? $t('site.templateFields.searching') : $t('site.templateFields.find')}
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
                    {result.title || $t('site.templateFields.postNumber', { id: result.post_id })}
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
                  {votePollItemIds.has(result.post_id) ? $t('site.templateFields.added') : $t('site.templateFields.add')}
                </button>
              </div>
            {/each}
          </div>
        {/if}
      </div>

      <div class="flex flex-col gap-2">
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.selectedPosts')}</span>
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
                  {$t('site.templateFields.remove')}
                </button>
              </div>
            {/each}
          </div>
        {:else}
          <div class="rounded-xl border border-dashed border-slate-300 dark:border-zinc-700 px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
            {$t('site.templateFields.noPosts')}
          </div>
        {/if}
        <p class="text-xs text-slate-500 dark:text-zinc-400">
          {$t('site.templateFields.pollRequirement')}
        </p>
      </div>
    </div>
    {:else if templateType === 'bug_report'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.platforms')}</span>
        <details class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900">
          <summary class="list-none cursor-pointer px-3 py-2 text-sm text-slate-900 dark:text-zinc-100 flex items-center justify-between gap-3">
            <span class="truncate">
              {bugPlatformLabelValues.length ? bugPlatformLabelValues.join(', ') : $t('site.templateFields.choosePlatforms')}
            </span>
            <span class="text-xs text-slate-500 dark:text-zinc-400">▼</span>
          </summary>
          <div class="p-2 border-t border-slate-200 dark:border-zinc-800 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {#each BUG_REPORT_PLATFORM_OPTIONS as option}
              <label class="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/40 px-3 py-2 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/70">
                <input
                  type="checkbox"
                  class="accent-slate-900 dark:accent-zinc-200"
                  checked={bugPlatformSet.has(option.value)}
                  on:change={(event) => onBugPlatformChange(option.value, event)}
                />
                <span class="text-sm text-slate-700 dark:text-zinc-200">{bugReportBrowserLabel(option.value)}</span>
              </label>
            {/each}
          </div>
        </details>
      </div>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.browsers')}</span>
        <details class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900">
          <summary class="list-none cursor-pointer px-3 py-2 text-sm text-slate-900 dark:text-zinc-100 flex items-center justify-between gap-3">
            <span class="truncate">
              {bugBrowserLabelValues.length ? bugBrowserLabelValues.join(', ') : $t('site.templateFields.chooseBrowsers')}
            </span>
            <span class="text-xs text-slate-500 dark:text-zinc-400">▼</span>
          </summary>
          <div class="p-2 border-t border-slate-200 dark:border-zinc-800 grid grid-cols-1 sm:grid-cols-2 gap-2">
            {#each BUG_REPORT_BROWSER_OPTIONS as option}
              <label class="flex items-center gap-2 rounded-lg border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/40 px-3 py-2 cursor-pointer hover:bg-slate-100 dark:hover:bg-zinc-800/70">
                <input
                  type="checkbox"
                  class="accent-slate-900 dark:accent-zinc-200"
                  checked={bugBrowserSet.has(option.value)}
                  on:change={(event) => onBugBrowserChange(option.value, event)}
                />
                <span class="text-sm text-slate-700 dark:text-zinc-200">{option.label}</span>
              </label>
            {/each}
          </div>
        </details>
      </div>

      <label class="md:col-span-2 flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.errorCode')}</span>
        <textarea
          bind:value={bugReportData.error_code}
          rows="4"
          placeholder={$t('site.templateFields.errorPlaceholder')}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm font-mono text-slate-900 dark:text-zinc-100"
        ></textarea>
      </label>

      <div class="md:col-span-2 flex flex-col gap-2">
        <span class="text-sm text-slate-700 dark:text-zinc-300">{$t('site.templateFields.screenshot')}</span>
        <input
          bind:this={bugScreenshotInput}
          type="file"
          accept="image/*"
          class="hidden"
          on:change={onBugScreenshotSelected}
        />
        <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
          <div class="h-20 w-28 rounded-lg overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if bugReportData.screenshot_url}
              <img src={bugReportData.screenshot_url} alt={$t('site.templateFields.bugScreenshotAlt')} class="h-full w-full object-cover" />
            {:else}
              <div class="h-full w-full grid place-items-center text-[10px] text-slate-400 dark:text-zinc-500 text-center px-1">
                {$t('site.templateFields.noScreenshot')}
              </div>
            {/if}
          </div>
          <div class="min-w-0 flex-1">
            <div class="text-sm text-slate-700 dark:text-zinc-300">
              {#if bugScreenshotUploading}
                {$t('site.templateFields.screenshotUploading')}
              {:else if bugReportData.screenshot_url}
                {$t('site.templateFields.screenshotUploaded')}
              {:else}
                {$t('site.templateFields.attachScreenshot')}
              {/if}
            </div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">PNG, JPG, WEBP, GIF</div>
          </div>
          <div class="flex flex-wrap gap-2 justify-end">
            <button
              type="button"
              class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
              on:click={pickBugScreenshot}
              disabled={bugScreenshotUploading}
            >
              {bugReportData.screenshot_url ? $t('site.templateFields.replace') : $t('site.templateFields.upload')}
            </button>
            {#if bugReportData.screenshot_url}
              <button
                type="button"
                class="rounded-lg border border-slate-300 dark:border-zinc-700 px-3 py-1.5 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-50 dark:hover:bg-zinc-800 disabled:opacity-50"
                on:click={removeBugScreenshot}
                disabled={bugScreenshotUploading}
              >
                {$t('site.templateFields.remove')}
              </button>
            {/if}
          </div>
        </div>
      </div>
    </div>
    {:else if templateType === 'tweet'}
    <div class="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-300">
      <div class="font-medium text-slate-900 dark:text-zinc-100">{$t('site.templateFields.tweetTemplate')}</div>
      <div class="mt-1">
        {$t('site.templateFields.tweetHint')}
      </div>
    </div>
    {/if}
  </div>
{/if}
