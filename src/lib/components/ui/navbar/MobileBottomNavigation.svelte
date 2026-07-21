<script lang="ts">
  import { page } from '$app/stores'
  import { profile } from '$lib/auth'
  import { siteUser } from '$lib/siteAuth'
  import { t } from '$lib/translations'
  import {
    Bell,
    Fire,
    Icon,
    PencilSquare,
    Plus,
    Squares2x2,
    UserCircle,
    UserGroup,
    XMark,
  } from 'svelte-hero-icons'

  let createMenuOpen = false
  let lastPath = ''

  $: path = $page.url.pathname
  $: if (path !== lastPath) {
    lastPath = path
    createMenuOpen = false
  }
  $: profilePath = $siteUser?.id
    ? `/id${$siteUser.id}`
    : $profile?.jwt
      ? '/profile'
      : '/account'
  $: notificationsPath = $siteUser
    ? '/notifications'
    : $profile?.jwt
      ? '/inbox'
      : '/account?next=%2Fnotifications'
  $: createPostPath = $siteUser ? '/account/new-post?new=1' : '/account?next=%2Faccount%2Fnew-post%3Fnew%3D1'
  $: createCommunityPath = $siteUser ? '/comuns?create=1' : '/account?next=%2Fcomuns%3Fcreate%3D1'

  const isActive = (item: 'feed' | 'communities' | 'notifications' | 'profile') => {
    if (item === 'feed') return path === '/'
    if (item === 'communities') return path === '/comuns' || path.startsWith('/comuns/')
    if (item === 'notifications') return path === '/notifications' || path.startsWith('/inbox')
    return /^\/id\d+/.test(path) || path.startsWith('/profile') || path === '/settings'
  }

  const closeOnEscape = (event: KeyboardEvent) => {
    if (event.key === 'Escape') createMenuOpen = false
  }
</script>

<svelte:window on:keydown={closeOnEscape} />

{#if createMenuOpen}
  <button
    type="button"
    class="fixed inset-0 z-[890] block bg-slate-950/20 md:hidden"
    aria-label={$t('site.nav.closeMenu')}
    on:click={() => (createMenuOpen = false)}
  ></button>
{/if}

<nav
  class="mobile-bottom-nav fixed inset-x-0 bottom-0 z-[900] border-t border-slate-200 bg-white/95 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-950/95 md:hidden"
  aria-label={$t('nav.menu.label')}
>
  {#if createMenuOpen}
    <div
      class="absolute bottom-[calc(100%+0.75rem)] left-1/2 w-64 -translate-x-1/2 overflow-hidden rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
    >
      <a
        href={createPostPath}
        class="flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-100 dark:text-zinc-100 dark:hover:bg-zinc-800"
      >
        <Icon src={PencilSquare} size="19" class="text-blue-600 dark:text-blue-400" />
        {$t('nav.create.post')}
      </a>
      <a
        href={createCommunityPath}
        class="flex items-center gap-3 rounded-md px-3 py-3 text-sm font-medium text-slate-800 transition-colors hover:bg-slate-100 dark:text-zinc-100 dark:hover:bg-zinc-800"
      >
        <Icon src={UserGroup} size="19" class="text-blue-600 dark:text-blue-400" />
        {$t('nav.create.community')}
      </a>
    </div>
  {/if}

  <div class="relative grid h-[4.5rem] grid-cols-5 items-end px-1 pb-1.5">
    <a
      href="/"
      class:active={isActive('feed')}
      class="mobile-tab"
      aria-current={isActive('feed') ? 'page' : undefined}
    >
      <Icon src={Fire} size="23" />
      <span>{$t('nav.feed')}</span>
    </a>

    <a
      href="/comuns"
      class:active={isActive('communities')}
      class="mobile-tab"
      aria-current={isActive('communities') ? 'page' : undefined}
    >
      <Icon src={Squares2x2} size="23" />
      <span>{$t('nav.communities')}</span>
    </a>

    <div aria-hidden="true"></div>

    <a
      href={notificationsPath}
      class:active={isActive('notifications')}
      class="mobile-tab"
      aria-current={isActive('notifications') ? 'page' : undefined}
    >
      <Icon src={Bell} size="23" />
      <span>{$t('settings.notifications.title')}</span>
    </a>

    <a
      href={profilePath}
      class:active={isActive('profile')}
      class="mobile-tab"
      aria-current={isActive('profile') ? 'page' : undefined}
    >
      {#if $siteUser?.avatar_url}
        <img
          src={$siteUser.avatar_url}
          alt=""
          class="h-6 w-6 rounded-full border border-current object-cover"
        />
      {:else}
        <Icon src={UserCircle} size="24" />
      {/if}
      <span>{$t('site.nav.profile')}</span>
    </a>

    <button
      type="button"
      class="create-button absolute left-1/2 top-0 grid h-14 w-14 -translate-x-1/2 -translate-y-4 place-items-center rounded-full border-4 border-white bg-blue-600 text-white shadow-lg transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:border-zinc-950 dark:bg-blue-600 dark:hover:bg-blue-500 dark:focus-visible:ring-offset-zinc-950"
      aria-label={$t('nav.create.label')}
      aria-expanded={createMenuOpen}
      on:click={() => (createMenuOpen = !createMenuOpen)}
    >
      <Icon src={createMenuOpen ? XMark : Plus} size="28" />
    </button>
  </div>
</nav>

<style>
  .mobile-bottom-nav {
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }

  .mobile-tab {
    display: flex;
    min-width: 0;
    min-height: 3.5rem;
    flex-direction: column;
    align-items: center;
    justify-content: flex-end;
    gap: 0.125rem;
    padding: 0.25rem 0.125rem;
    color: rgb(100 116 139);
    font-size: 0.6875rem;
    font-weight: 600;
    line-height: 1rem;
    text-align: center;
  }

  .mobile-tab span {
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .mobile-tab.active {
    color: rgb(37 99 235);
  }

  :global(.dark) .mobile-tab {
    color: rgb(161 161 170);
  }

  :global(.dark) .mobile-tab.active {
    color: rgb(96 165 250);
  }
</style>
