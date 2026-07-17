<script lang="ts">
  import { onDestroy } from 'svelte'
  import { Button, Modal, Spinner, toast } from 'mono-svelte'
  import { Clipboard, Icon, MagnifyingGlass, Trash, UserPlus } from 'svelte-hero-icons'
  import {
    fetchDraftAccess,
    grantDraftAccess,
    revokeDraftAccess,
    type DraftShareUser,
  } from '$lib/siteAuth'
  import { t } from '$lib/translations'

  export let open = false
  export let postId = 0
  export let shareUrl = ''

  let wasOpen = false
  let searchQuery = ''
  let viewers: DraftShareUser[] = []
  let users: DraftShareUser[] = []
  let loading = false
  let searching = false
  let changingUserId: number | null = null
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  let requestId = 0

  const displayName = (user: DraftShareUser) => user.display_name || user.username
  const initial = (user: DraftShareUser) => displayName(user).slice(0, 1).toUpperCase()

  const loadAccess = async (query = '') => {
    if (!postId) return
    const currentRequestId = ++requestId
    if (query) searching = true
    else loading = true
    try {
      const data = await fetchDraftAccess(postId, query)
      if (currentRequestId !== requestId) return
      viewers = data.viewers
      users = data.users
    } catch (error) {
      if (currentRequestId !== requestId) return
      toast({
        content: (error as Error)?.message || $t('site.draftShare.loadError'),
        type: 'error',
      })
    } finally {
      if (currentRequestId === requestId) {
        loading = false
        searching = false
      }
    }
  }

  const queueSearch = () => {
    if (searchTimer) clearTimeout(searchTimer)
    const query = searchQuery.trim()
    if (query.length < 2) {
      users = []
      searching = false
      return
    }
    searching = true
    searchTimer = setTimeout(() => void loadAccess(query), 300)
  }

  const grant = async (user: DraftShareUser) => {
    if (!postId || changingUserId) return
    changingUserId = user.id
    try {
      const grantedUser = await grantDraftAccess(postId, user.id)
      viewers = [...viewers.filter((item) => item.id !== user.id), grantedUser].sort((a, b) =>
        displayName(a).localeCompare(displayName(b))
      )
      users = users.map((item) =>
        item.id === user.id ? { ...item, has_access: true } : item
      )
      toast({ content: $t('site.draftShare.grantSuccess'), type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message || $t('site.draftShare.changeError'),
        type: 'error',
      })
    } finally {
      changingUserId = null
    }
  }

  const revoke = async (user: DraftShareUser) => {
    if (!postId || changingUserId) return
    changingUserId = user.id
    try {
      await revokeDraftAccess(postId, user.id)
      viewers = viewers.filter((item) => item.id !== user.id)
      users = users.map((item) =>
        item.id === user.id ? { ...item, has_access: false } : item
      )
      toast({ content: $t('site.draftShare.revokeSuccess'), type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message || $t('site.draftShare.changeError'),
        type: 'error',
      })
    } finally {
      changingUserId = null
    }
  }

  const copyLink = async () => {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      toast({ content: $t('site.draftShare.linkCopied'), type: 'success' })
    } catch {
      toast({ content: $t('site.draftShare.copyError'), type: 'error' })
    }
  }

  const reset = () => {
    requestId += 1
    searchQuery = ''
    viewers = []
    users = []
    loading = false
    searching = false
    changingUserId = null
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = null
  }

  $: if (open && !wasOpen) {
    wasOpen = true
    void loadAccess()
  }
  $: if (!open && wasOpen) {
    wasOpen = false
    reset()
  }

  onDestroy(reset)
</script>

<Modal bind:open dismissable title={$t('site.draftShare.title')}>
  <div class="grid w-full min-w-0 gap-5 sm:min-w-[30rem]">
    <p class="text-sm leading-6 text-slate-600 dark:text-zinc-300">
      {$t('site.draftShare.description')}
    </p>

    <label class="grid gap-1.5">
      <span class="text-sm font-medium text-slate-800 dark:text-zinc-100">
        {$t('site.draftShare.searchLabel')}
      </span>
      <div class="relative">
        <Icon
          src={MagnifyingGlass}
          size="18"
          mini
          class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
        />
        <input
          bind:value={searchQuery}
          type="search"
          autocomplete="off"
          placeholder={$t('site.draftShare.placeholder')}
          class="w-full rounded-lg border border-slate-300 bg-white py-2.5 pl-10 pr-3 text-sm text-slate-950 outline-none focus:border-slate-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50 dark:focus:border-zinc-500"
          on:input={queueSearch}
        />
      </div>
    </label>

    {#if searchQuery.trim().length >= 2}
      <div class="grid gap-2">
        {#if searching}
          <div class="flex min-h-16 items-center justify-center"><Spinner /></div>
        {:else if users.length}
          {#each users as user (user.id)}
            <div class="flex min-w-0 items-center gap-3 rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
              {#if user.avatar_url}
                <img src={user.avatar_url} alt="" class="h-10 w-10 shrink-0 rounded-full object-cover" />
              {:else}
                <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-600 dark:bg-zinc-800 dark:text-zinc-200">
                  {initial(user)}
                </span>
              {/if}
              <div class="min-w-0 flex-1">
                <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-50">{displayName(user)}</div>
                <div class="truncate text-xs text-slate-500 dark:text-zinc-400">@{user.username}</div>
              </div>
              <Button
                color={user.has_access ? 'ghost' : 'primary'}
                size="sm"
                disabled={user.has_access || changingUserId !== null}
                loading={changingUserId === user.id}
                on:click={() => grant(user)}
              >
                <Icon src={UserPlus} size="16" mini slot="prefix" />
                {user.has_access ? $t('site.draftShare.hasAccess') : $t('site.draftShare.grant')}
              </Button>
            </div>
          {/each}
        {:else}
          <p class="py-3 text-sm text-slate-500 dark:text-zinc-400">
            {$t('site.draftShare.noResults')}
          </p>
        {/if}
      </div>
    {/if}

    <div class="grid gap-2">
      <h3 class="text-sm font-semibold text-slate-900 dark:text-zinc-50">
        {$t('site.draftShare.viewersTitle')}
      </h3>
      {#if loading}
        <div class="flex min-h-16 items-center justify-center"><Spinner /></div>
      {:else if viewers.length}
        {#each viewers as user (user.id)}
          <div class="flex min-w-0 items-center gap-3 py-2">
            {#if user.avatar_url}
              <img src={user.avatar_url} alt="" class="h-9 w-9 shrink-0 rounded-full object-cover" />
            {:else}
              <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-semibold text-slate-600 dark:bg-zinc-800 dark:text-zinc-200">
                {initial(user)}
              </span>
            {/if}
            <div class="min-w-0 flex-1">
              <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-50">{displayName(user)}</div>
              <div class="truncate text-xs text-slate-500 dark:text-zinc-400">@{user.username}</div>
            </div>
            <Button
              color="ghost"
              size="sm"
              title={$t('site.draftShare.revoke')}
              disabled={changingUserId !== null}
              loading={changingUserId === user.id}
              on:click={() => revoke(user)}
            >
              <Icon src={Trash} size="16" mini />
            </Button>
          </div>
        {/each}
      {:else}
        <p class="text-sm text-slate-500 dark:text-zinc-400">{$t('site.draftShare.noViewers')}</p>
      {/if}
    </div>

    <div class="border-t border-slate-200 pt-4 dark:border-zinc-800">
      <Button color="secondary" on:click={copyLink} disabled={!shareUrl}>
        <Icon src={Clipboard} size="16" mini slot="prefix" />
        {$t('site.draftShare.copyLink')}
      </Button>
    </div>
  </div>
</Modal>
