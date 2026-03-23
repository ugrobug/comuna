<script lang="ts">
  import { browser } from '$app/environment'
  import {
    buildPostDetailUrl,
    buildPostPollVoteUrl,
    type BackendPoll,
    type BackendPollOption,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { toast } from 'mono-svelte'
  import { onMount } from 'svelte'
  import {
    formatPostVotePollDeadline,
    postVotePollOptionLabel,
    type PostVotePollTemplate,
    type PostVotePollTemplateItem,
  } from '$lib/postTemplates'

  export let template: PostVotePollTemplate
  export let fallbackTitle = ''
  export let poll: BackendPoll | null = null
  export let pollPostId: number | null = null
  export let allowPollVoting = false

  let voting = false
  let localPoll: BackendPoll | null = null
  let lastPollRef: BackendPoll | null = null
  let restoreInFlight = false
  let restoredToken: string | null = null

  const clonePoll = (value: BackendPoll | null | undefined): BackendPoll | null =>
    value
      ? {
          ...value,
          options: Array.isArray(value.options) ? value.options.map((option) => ({ ...option })) : [],
          user_selection: Array.isArray(value.user_selection) ? [...value.user_selection] : [],
        }
      : null

  const normalizeSelection = (selection: number[]): number[] =>
    Array.from(
      new Set(
        selection
          .map((value) => Number(value))
          .filter((value) => Number.isInteger(value) && value >= 0)
      )
    ).sort((a, b) => a - b)

  const applyOptimisticPollSelection = (
    source: BackendPoll | null,
    nextSelection: number[]
  ): BackendPoll | null => {
    if (!source) return null

    const nextPoll = clonePoll(source)
    if (!nextPoll) return null

    const previousSelection = new Set(normalizeSelection(source.user_selection ?? []))
    const nextSelectionSet = new Set(normalizeSelection(nextSelection))

    nextPoll.options = nextPoll.options.map((option, index) => {
      let voterCount = Math.max(Number(option.voter_count || 0), 0)
      if (previousSelection.has(index) && !nextSelectionSet.has(index)) {
        voterCount = Math.max(0, voterCount - 1)
      }
      if (!previousSelection.has(index) && nextSelectionSet.has(index)) {
        voterCount += 1
      }
      return {
        ...option,
        voter_count: voterCount,
      }
    })

    let totalVoterCount = Math.max(Number(nextPoll.total_voter_count || 0), 0)
    if (!previousSelection.size && nextSelectionSet.size) {
      totalVoterCount += 1
    } else if (previousSelection.size && !nextSelectionSet.size) {
      totalVoterCount = Math.max(0, totalVoterCount - 1)
    }

    nextPoll.total_voter_count = totalVoterCount
    nextPoll.user_selection = Array.from(nextSelectionSet).sort((a, b) => a - b)
    return nextPoll
  }

  const formatVoteCount = (count: number): string => {
    const safeCount = Math.max(0, Math.floor(count))
    const mod10 = safeCount % 10
    const mod100 = safeCount % 100
    if (mod10 === 1 && mod100 !== 11) return `${safeCount} голос`
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
      return `${safeCount} голоса`
    }
    return `${safeCount} голосов`
  }

  const storageKeyForPoll = (postId: number | null): string => {
    if (!Number.isInteger(postId) || Number(postId) <= 0) return ''
    return `comuna:template-poll:${postId}`
  }

  const getPollIdentity = (value: BackendPoll | null | undefined): string => {
    const pollId = String(value?.id || '').trim()
    if (pollId) return pollId
    const questionValue = String(value?.question || '').trim()
    const optionsValue = Array.isArray(value?.options)
      ? value.options.map((option) => String(option?.text || '').trim()).join('|')
      : ''
    return `${questionValue}::${optionsValue}`
  }

  const mergePollWithFallback = (
    primary: BackendPoll | null | undefined,
    fallback: BackendPoll | null | undefined
  ): BackendPoll | null => {
    const next = clonePoll(primary) ?? clonePoll(fallback)
    if (!next) return null

    const fallbackPoll = clonePoll(fallback)
    if (!fallbackPoll) return next

    const nextSelection = normalizeSelection(next.user_selection ?? [])
    const fallbackSelection = normalizeSelection(fallbackPoll.user_selection ?? [])
    if (!nextSelection.length && fallbackSelection.length) {
      next.user_selection = fallbackSelection
    }

    return next
  }

  const readStoredPoll = (): BackendPoll | null => {
    if (!browser) return null
    const storageKey = storageKeyForPoll(pollPostId)
    if (!storageKey) return null
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.poll || typeof parsed.poll !== 'object') {
        return null
      }
      const storedPoll = clonePoll(parsed.poll as BackendPoll)
      if (!storedPoll) return null
      const currentIdentity = getPollIdentity(poll)
      const storedIdentity = getPollIdentity(storedPoll)
      if (currentIdentity && storedIdentity && currentIdentity !== storedIdentity) {
        localStorage.removeItem(storageKey)
        return null
      }
      return storedPoll
    } catch (error) {
      console.error('Failed to read stored poll state:', error)
      return null
    }
  }

  const persistPoll = (value: BackendPoll | null | undefined) => {
    if (!browser) return
    const storageKey = storageKeyForPoll(pollPostId)
    if (!storageKey) return
    if (!value) {
      localStorage.removeItem(storageKey)
      return
    }
    try {
      localStorage.setItem(storageKey, JSON.stringify({ poll: clonePoll(value) }))
    } catch (error) {
      console.error('Failed to persist poll state:', error)
    }
  }

  const applyPollState = (
    value: BackendPoll | null | undefined,
    fallback: BackendPoll | null | undefined = localPoll
  ) => {
    localPoll = mergePollWithFallback(value, fallback)
    persistPoll(localPoll)
  }

  const refreshPollState = async (tokenOverride?: string | null) => {
    if (!browser || !allowPollVoting || !pollPostId || restoreInFlight) return
    const token = tokenOverride ?? $siteToken
    if (!token) return

    restoreInFlight = true
    try {
      const response = await fetch(buildPostDetailUrl(pollPostId), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const payload = await response.json().catch(() => null)
      if (response.ok && payload?.post?.poll && typeof payload.post.poll === 'object') {
        applyPollState(payload.post.poll as BackendPoll)
      }
    } catch (error) {
      console.error('Failed to restore poll state:', error)
    } finally {
      restoreInFlight = false
    }
  }

  const restoreCurrentUserPollState = async () => {
    if (!browser || !allowPollVoting || !pollPostId) return
    const storedPoll = readStoredPoll()
    if (storedPoll) {
      applyPollState(storedPoll, poll)
    }
    const token = $siteToken
    if (!token || restoredToken === token) return

    restoredToken = token
    await refreshPollState(token)
  }

  $: data = template.data
  $: items = Array.isArray(data.items) ? data.items : []
  $: templateItemsByPostId = new Map(
    items
      .map((item) => [Number(item.post_id), item] as const)
      .filter(([postId]) => Number.isInteger(postId) && postId > 0)
  )
  $: question = (data.question || fallbackTitle || 'Голосование за посты').trim()

  $: if (poll !== lastPollRef) {
    lastPollRef = poll
    restoredToken = null
    applyPollState(poll, readStoredPoll())
  }

  $: fallbackOptions = items.map((item, index) => ({
    index,
    text: postVotePollOptionLabel(item),
    voter_count: 0,
    post_id: item.post_id,
    post_path: item.path,
  }))
  $: pollOptions = localPoll?.options?.length ? localPoll.options : fallbackOptions
  $: totalVotes = Math.max(Number(localPoll?.total_voter_count ?? 0), 0)
  $: selectedSet = new Set(
    (localPoll?.user_selection ?? [])
      .map((value) => Number(value))
      .filter((value) => Number.isInteger(value) && value >= 0)
  )
  $: hasUserVote = selectedSet.size > 0
  $: allowsMultiple = Boolean(localPoll?.allows_multiple_answers ?? data.allows_multiple_answers)
  $: deadlineValue = localPoll?.close_at || data.ends_at
  $: deadlineLabel = formatPostVotePollDeadline(deadlineValue)
  $: deadlineTimestamp = Date.parse(deadlineValue || '')
  $: isClosed =
    Boolean(localPoll?.is_closed) ||
    (Number.isFinite(deadlineTimestamp) ? deadlineTimestamp <= Date.now() : false)
  $: showResults = hasUserVote || isClosed
  $: if (browser && allowPollVoting && pollPostId && $siteToken && !hasUserVote) {
    void restoreCurrentUserPollState()
  }

  onMount(() => {
    void restoreCurrentUserPollState()
  })

  const looksSerializedTitle = (value: string): boolean => {
    const raw = (value || '').trim()
    return raw.length >= 48 && !/\s/.test(raw) && /^[A-Za-z0-9_+/=-]+$/.test(raw)
  }

  const templateItemForOption = (option: BackendPollOption): PostVotePollTemplateItem | null => {
    const postId = Number(option?.post_id ?? 0)
    if (Number.isInteger(postId) && postId > 0) {
      return templateItemsByPostId.get(postId) ?? null
    }
    const optionIndex = Number(option?.index ?? -1)
    if (Number.isInteger(optionIndex) && optionIndex >= 0) {
      return items[optionIndex] ?? null
    }
    return null
  }

  const optionTitle = (option: BackendPollOption): string => {
    const raw = String(option?.text || '').trim()
    const templateItem = templateItemForOption(option)
    if (raw && !looksSerializedTitle(raw)) {
      return raw
    }
    if (templateItem) {
      return postVotePollOptionLabel(templateItem)
    }
    const postId = Number(option?.post_id ?? 0)
    if (Number.isInteger(postId) && postId > 0) {
      return `Пост #${postId}`
    }
    return 'Пост'
  }

  const optionPath = (option: BackendPollOption): string => {
    const pollPath = String(option?.post_path || '').trim()
    if (pollPath.startsWith('/')) return pollPath
    const templateItem = templateItemForOption(option)
    const templatePath = String(templateItem?.path || '').trim()
    if (templatePath.startsWith('/')) return templatePath
    const postId = Number(option?.post_id ?? templateItem?.post_id ?? 0)
    if (Number.isInteger(postId) && postId > 0) return `/b/post/${postId}`
    return '#'
  }

  const optionAuthor = (option: BackendPollOption): string => {
    const templateItem = templateItemForOption(option)
    const username = String(templateItem?.author_username || '').trim()
    return username
  }

  const submitVote = async (selection: number[]) => {
    if (!allowPollVoting || !pollPostId) {
      toast({ content: 'Голосовать можно только в посте на сайте', type: 'warning' })
      return
    }
    const token = $siteToken
    if (!token) {
      toast({ content: 'Необходимо зарегистрироваться', type: 'warning' })
      return
    }

    const previousPoll = clonePoll(localPoll ?? poll)
    const optimisticPoll = applyOptimisticPollSelection(previousPoll, selection)
    if (optimisticPoll) {
      localPoll = optimisticPoll
      persistPoll(localPoll)
    }

    voting = true
    let payload: any = null
    try {
      const response = await fetch(buildPostPollVoteUrl(pollPostId), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ options: selection }),
      })
      payload = await response.json().catch(() => ({}))
      if (payload?.poll && typeof payload.poll === 'object') {
        applyPollState(payload.poll as BackendPoll, optimisticPoll ?? previousPoll)
      }
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || 'Не удалось проголосовать')
      }
      await refreshPollState(token)
    } catch (error) {
      if (!payload?.poll) {
        localPoll = previousPoll
        persistPoll(localPoll)
      }
      toast({
        content: (error as Error)?.message ?? 'Не удалось проголосовать',
        type: 'error',
      })
    } finally {
      voting = false
    }
  }

  const toggleOptionVote = async (optionIndex: number) => {
    if (!Number.isInteger(optionIndex) || optionIndex < 0) return
    if (isClosed) {
      toast({ content: 'Голосование завершено', type: 'warning' })
      return
    }
    if (voting || hasUserVote) return

    const next = new Set(
      (localPoll?.user_selection ?? [])
        .map((value) => Number(value))
        .filter((value) => Number.isInteger(value) && value >= 0)
    )
    if (allowsMultiple) {
      if (next.has(optionIndex)) next.delete(optionIndex)
      else next.add(optionIndex)
    } else if (next.has(optionIndex) && next.size === 1) {
      next.clear()
    } else {
      next.clear()
      next.add(optionIndex)
    }
    await submitVote(Array.from(next).sort((a, b) => a - b))
  }
</script>

<section class="vote-poll-hero overflow-hidden rounded-2xl border border-slate-200 dark:border-zinc-800">
  <div class="vote-poll-hero__bg"></div>
  <div class="vote-poll-hero__body">
    <div class="vote-poll-hero__head">
      <div class="vote-poll-hero__badge">Голосование за посты</div>
      {#if deadlineLabel}
        <div class={`vote-poll-hero__deadline ${isClosed ? 'is-closed' : ''}`}>
          {#if isClosed}
            Завершено: {deadlineLabel}
          {:else}
            До: {deadlineLabel}
          {/if}
        </div>
      {/if}
    </div>

    {#if question}
      <h2 class="vote-poll-hero__title">{question}</h2>
    {/if}

    <div class="vote-poll-hero__meta">
      {#if showResults}
        <span>{formatVoteCount(totalVotes)}</span>
      {/if}
      <span>
        {#if isClosed}
          Опрос завершен
        {:else if showResults}
          Вы уже проголосовали
        {:else}
          {allowsMultiple ? 'Можно выбрать несколько вариантов' : 'Один вариант ответа'}
        {/if}
      </span>
    </div>

    {#if pollOptions.length}
      <div class="vote-poll-hero__items">
        {#each pollOptions as option (option.index)}
          {@const optionIndex = Number(option.index)}
          {@const selected = selectedSet.has(optionIndex)}
          {@const count = Math.max(Number(option.voter_count || 0), 0)}
          {@const percent = totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0}
          <div class={`vote-poll-item ${showResults ? 'vote-poll-item--result' : 'vote-poll-item--choice'} ${selected ? 'is-selected' : ''}`}>
            <div class="vote-poll-item__main">
              {#if showResults}
                <div class={`vote-poll-item__check ${selected ? 'is-selected' : ''}`} aria-hidden="true">
                  {#if selected}✓{/if}
                </div>
              {:else}
                <span class="vote-poll-item__index">#{optionIndex + 1}</span>
              {/if}
              <div class="vote-poll-item__content">
                <div class="vote-poll-item__title">{optionTitle(option)}</div>
                {#if optionAuthor(option)}
                  <div class="vote-poll-item__author">@{optionAuthor(option)}</div>
                {/if}
              </div>
              {#if showResults}
                <div class="vote-poll-item__stats">{percent}%</div>
              {/if}
            </div>
            {#if showResults}
              <div class="vote-poll-item__progress">
                <span class={`vote-poll-item__progress-fill ${selected ? 'is-selected' : ''}`} style={`width: ${percent}%`}></span>
              </div>
              <div class="vote-poll-item__result-meta">
                <span>{formatVoteCount(count)}</span>
                {#if selected}
                  <span class="vote-poll-item__badge">Ваш голос</span>
                {/if}
              </div>
            {:else}
              <div class="vote-poll-item__actions">
                <a
                  href={optionPath(option)}
                  target="_blank"
                  rel="noopener"
                  class="vote-poll-item__link"
                >
                  Открыть пост
                </a>
                <button
                  type="button"
                  class="vote-poll-item__vote-btn"
                  disabled={voting || isClosed || !allowPollVoting || !pollPostId || restoreInFlight}
                  on:click|preventDefault|stopPropagation={() => toggleOptionVote(optionIndex)}
                >
                  Голосовать
                </button>
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    <div class="vote-poll-hero__status">
      {#if restoreInFlight && !showResults}
        Проверяем ваш голос...
      {:else if isClosed}
        Опрос завершен
      {:else if showResults}
        Результаты обновлены
      {:else}
        Выберите вариант, чтобы проголосовать
      {/if}
    </div>
  </div>
</section>

<style lang="postcss">
  .vote-poll-hero {
    position: relative;
    background:
      radial-gradient(120% 130% at 5% 0%, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0) 56%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
  }

  .vote-poll-hero__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .vote-poll-hero__bg::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0.3;
    background-image:
      radial-gradient(circle at 15% 15%, rgba(148, 163, 184, 0.16) 0, transparent 38%),
      radial-gradient(circle at 80% 20%, rgba(16, 185, 129, 0.16) 0, transparent 34%);
  }

  .vote-poll-hero__body {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    padding: 1rem;
    color: #e2e8f0;
  }

  .vote-poll-hero__head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    justify-content: space-between;
  }

  .vote-poll-hero__badge {
    border-radius: 9999px;
    border: 1px solid rgba(16, 185, 129, 0.45);
    background: rgba(15, 23, 42, 0.5);
    color: #6ee7b7;
    font-size: 0.72rem;
    line-height: 1.2;
    padding: 0.26rem 0.62rem;
    font-weight: 600;
  }

  .vote-poll-hero__deadline {
    border-radius: 9999px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(15, 23, 42, 0.45);
    color: #cbd5e1;
    font-size: 0.72rem;
    line-height: 1.2;
    padding: 0.26rem 0.62rem;
  }

  .vote-poll-hero__deadline.is-closed {
    border-color: rgba(251, 191, 36, 0.5);
    color: #fde68a;
  }

  .vote-poll-hero__title {
    margin: 0;
    color: #fff;
    font-size: clamp(1.1rem, 1.9vw, 1.5rem);
    line-height: 1.22;
    font-weight: 700;
    text-wrap: balance;
  }

  .vote-poll-hero__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.8rem;
    font-size: 0.76rem;
    line-height: 1.2;
    color: #cbd5e1;
  }

  .vote-poll-hero__items {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .vote-poll-item {
    border-radius: 0.72rem;
    border: 1px solid rgba(148, 163, 184, 0.24);
    background: rgba(15, 23, 42, 0.4);
    padding: 0.58rem 0.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .vote-poll-item.is-selected {
    border-color: rgba(52, 211, 153, 0.5);
    background: rgba(16, 185, 129, 0.14);
  }

  .vote-poll-item--choice {
    cursor: default;
  }

  .vote-poll-item--result {
    gap: 0.7rem;
  }

  .vote-poll-item__main {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    gap: 0.45rem 0.6rem;
    align-items: start;
  }

  .vote-poll-item__index {
    color: #6ee7b7;
    font-size: 0.75rem;
    line-height: 1.2;
    font-weight: 700;
    min-width: 2.1rem;
  }

  .vote-poll-item__check {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 9999px;
    border: 1px solid rgba(148, 163, 184, 0.4);
    color: transparent;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.92rem;
    line-height: 1;
    font-weight: 700;
    background: rgba(15, 23, 42, 0.48);
  }

  .vote-poll-item__check.is-selected {
    border-color: rgba(52, 211, 153, 0.62);
    background: rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
  }

  .vote-poll-item__content {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .vote-poll-item__title {
    min-width: 0;
    color: #f8fafc;
    font-size: 0.9rem;
    line-height: 1.28;
    font-weight: 600;
  }

  .vote-poll-item__author {
    color: #94a3b8;
    font-size: 0.76rem;
    line-height: 1.2;
  }

  .vote-poll-item__stats {
    color: #e2e8f0;
    font-size: 0.8rem;
    line-height: 1.2;
    font-weight: 600;
    text-align: right;
    white-space: nowrap;
  }

  .vote-poll-item__progress {
    width: 100%;
    height: 0.72rem;
    border-radius: 9999px;
    overflow: hidden;
    background: rgba(100, 116, 139, 0.5);
  }

  .vote-poll-item__progress-fill {
    display: block;
    height: 100%;
    width: 0;
    border-radius: inherit;
    background: rgba(100, 116, 139, 0.95);
    transition: width 180ms ease;
  }

  .vote-poll-item__progress-fill.is-selected {
    background: linear-gradient(90deg, rgba(52, 211, 153, 0.92), rgba(16, 185, 129, 0.95));
  }

  .vote-poll-item__actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .vote-poll-item__link,
  .vote-poll-item__vote-btn {
    border-radius: 0.55rem;
    border: 1px solid rgba(148, 163, 184, 0.32);
    background: rgba(15, 23, 42, 0.44);
    color: #e2e8f0;
    font-size: 0.76rem;
    line-height: 1.2;
    font-weight: 600;
    padding: 0.28rem 0.56rem;
    text-decoration: none;
  }

  .vote-poll-item__link:hover,
  .vote-poll-item__vote-btn:hover {
    border-color: rgba(52, 211, 153, 0.56);
    background: rgba(15, 23, 42, 0.62);
  }

  .vote-poll-item__vote-btn[disabled] {
    opacity: 0.58;
    cursor: default;
  }

  .vote-poll-item__result-meta {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.45rem 0.6rem;
    font-size: 0.78rem;
    line-height: 1.2;
    color: #cbd5e1;
  }

  .vote-poll-item__badge {
    border-radius: 9999px;
    border: 1px solid rgba(52, 211, 153, 0.45);
    background: rgba(16, 185, 129, 0.14);
    color: #86efac;
    padding: 0.16rem 0.48rem;
    font-size: 0.72rem;
    font-weight: 700;
  }

  .vote-poll-hero__status {
    color: #94a3b8;
    font-size: 0.78rem;
    line-height: 1.25;
  }

  @media (max-width: 640px) {
    .vote-poll-item__main {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .vote-poll-item__stats {
      grid-column: 2;
      text-align: left;
    }
  }
</style>
