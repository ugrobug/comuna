<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import { profile } from '$lib/auth'
  import { normalizeInterfaceLanguage, originalPostLanguage } from '$lib/postLanguages'
  import { logout as siteLogout, siteUser } from '$lib/siteAuth'
  import { locale, t } from '$lib/translations'
  import {
    ArrowLeftOnRectangle,
    Bell,
    Bookmark,
    ChatBubbleLeftRight,
    ClipboardDocumentList,
    Cog6Tooth,
    DocumentText,
    Fire,
    Icon,
    Inbox,
    InformationCircle,
    Megaphone,
    PencilSquare,
    Plus,
    Squares2x2,
    UserCircle,
    UserGroup,
    XMark,
  } from 'svelte-hero-icons'

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about'
  const PUBLIC_PROJECT_ADVERTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement'
  const PUBLIC_PROJECT_APPS = env.PUBLIC_PROJECT_APPS || '/apps'
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors'
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules'

  let createMenuOpen = false
  let profileMenuOpen = false
  let lastPath = ''

  const localizedProjectPath = (path: string) => {
    const language = normalizeInterfaceLanguage($locale) ?? originalPostLanguage
    if (language === originalPostLanguage || !path.startsWith('/')) return path
    return `/${language}${path}`
  }

  $: path = $page.url.pathname
  $: if (path !== lastPath) {
    lastPath = path
    createMenuOpen = false
    profileMenuOpen = false
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
  $: projectAboutPath = localizedProjectPath(PUBLIC_PROJECT_ABOUT)
  $: projectAdvertisementPath = localizedProjectPath(PUBLIC_PROJECT_ADVERTISEMENT)
  $: projectAppsPath = localizedProjectPath(PUBLIC_PROJECT_APPS)
  $: projectAuthorsPath = localizedProjectPath(PUBLIC_PROJECT_AUTHORS)
  $: projectRulesPath = localizedProjectPath(PUBLIC_PROJECT_RULES)

  const isActive = (item: 'feed' | 'communities' | 'notifications' | 'profile') => {
    if (item === 'feed') return path === '/'
    if (item === 'communities') return path === '/comuns' || path.startsWith('/comuns/')
    if (item === 'notifications') return path === '/notifications' || path.startsWith('/inbox')
    return /^\/id\d+/.test(path) || path.startsWith('/profile') || path === '/settings'
  }

  const closeOnEscape = (event: KeyboardEvent) => {
    if (event.key !== 'Escape') return
    createMenuOpen = false
    profileMenuOpen = false
  }

  const toggleCreateMenu = () => {
    profileMenuOpen = false
    createMenuOpen = !createMenuOpen
  }

  const toggleProfileMenu = () => {
    createMenuOpen = false
    profileMenuOpen = !profileMenuOpen
  }

  const logout = async () => {
    profileMenuOpen = false
    if ($siteUser) {
      await siteLogout()
      return
    }
    if ($profile?.jwt) {
      $profile.jwt = undefined
      await goto('/', { invalidateAll: true })
    }
  }
</script>

<svelte:window on:keydown={closeOnEscape} />

{#if createMenuOpen || profileMenuOpen}
  <button
    type="button"
    class="fixed inset-0 z-[890] block bg-slate-950/20 md:hidden"
    aria-label={$t('site.nav.closeMenu')}
    on:click={() => {
      createMenuOpen = false
      profileMenuOpen = false
    }}
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

  {#if profileMenuOpen}
    <div
      class="profile-menu absolute bottom-[calc(100%+0.75rem)] right-2 max-h-[min(34rem,calc(100vh-8rem))] w-[min(20rem,calc(100vw-1rem))] overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 shadow-xl dark:border-zinc-700 dark:bg-zinc-900"
    >
      {#if $siteUser}
        <div class="flex items-center gap-3 px-3 py-2.5">
          {#if $siteUser.avatar_url}
            <img
              src={$siteUser.avatar_url}
              alt=""
              class="h-9 w-9 shrink-0 rounded-full object-cover"
            />
          {:else}
            <Icon src={UserCircle} size="36" class="shrink-0 text-slate-500 dark:text-zinc-400" />
          {/if}
          <span class="min-w-0 truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
            {$siteUser.username}
          </span>
        </div>
        <div class="menu-divider"></div>
        <a href={`/id${$siteUser.id}`} class="profile-menu-item">
          <Icon src={UserCircle} size="19" />
          {$t('site.nav.profile')}
        </a>
        <a href="/settings" class="profile-menu-item">
          <Icon src={Cog6Tooth} size="19" />
          {$t('site.nav.settings')}
        </a>
        <a href="/chats" class="profile-menu-item">
          <Icon src={ChatBubbleLeftRight} size="19" />
          {$t('site.nav.chats')}
        </a>
      {:else if $profile?.jwt}
        <a href="/profile" class="profile-menu-item">
          <Icon src={UserCircle} size="19" />
          {$t('profile.profile')}
        </a>
        <a href="/inbox" class="profile-menu-item">
          <Icon src={Inbox} size="19" />
          {$t('profile.inbox')}
        </a>
        <a href="/chats" class="profile-menu-item">
          <Icon src={ChatBubbleLeftRight} size="19" />
          {$t('site.nav.chats')}
        </a>
        <a href="/saved" class="profile-menu-item">
          <Icon src={Bookmark} size="19" />
          {$t('profile.saved')}
        </a>
      {:else}
        <a href={profilePath} class="profile-menu-item">
          <Icon src={UserCircle} size="19" />
          {$t('account.login')}
        </a>
      {/if}

      <div class="menu-divider"></div>
      <p class="menu-section-label">{$t('site.sidebar.resources')}</p>
      <a href={projectAboutPath} class="profile-menu-item">
        <Icon src={InformationCircle} size="19" />
        {$t('site.sidebar.aboutProject')}
      </a>
      <a href={projectAdvertisementPath} class="profile-menu-item">
        <Icon src={Megaphone} size="19" />
        {$t('site.sidebar.advertisement')}
      </a>
      <a href={projectAppsPath} class="profile-menu-item">
        <Icon src={DocumentText} size="19" />
        {$t('site.sidebar.apps')}
      </a>
      <a href={projectAuthorsPath} class="profile-menu-item">
        <Icon src={PencilSquare} size="19" />
        {$t('site.sidebar.authors')}
      </a>
      <a href={projectRulesPath} class="profile-menu-item">
        <Icon src={ClipboardDocumentList} size="19" />
        {$t('site.sidebar.rules')}
      </a>

      {#if $siteUser || $profile?.jwt}
        <div class="menu-divider"></div>
        <button type="button" class="profile-menu-item profile-menu-logout" on:click={logout}>
          <Icon src={ArrowLeftOnRectangle} size="19" />
          {$t('account.logout')}
        </button>
      {/if}
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

    <button
      type="button"
      class:active={isActive('profile')}
      class="mobile-tab"
      aria-expanded={profileMenuOpen}
      aria-label={$t('site.nav.userMenu')}
      on:click={toggleProfileMenu}
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
    </button>

    <button
      type="button"
      class="create-button absolute left-1/2 top-0 grid h-14 w-14 -translate-x-1/2 -translate-y-4 place-items-center rounded-full border-4 border-white bg-blue-600 text-white shadow-lg transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:border-zinc-950 dark:bg-blue-600 dark:hover:bg-blue-500 dark:focus-visible:ring-offset-zinc-950"
      aria-label={$t('nav.create.label')}
      aria-expanded={createMenuOpen}
      on:click={toggleCreateMenu}
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

  .profile-menu-item {
    display: flex;
    width: 100%;
    align-items: center;
    gap: 0.75rem;
    border-radius: 0.375rem;
    padding: 0.7rem 0.75rem;
    color: rgb(30 41 59);
    font-size: 0.875rem;
    font-weight: 500;
    line-height: 1.25rem;
    text-align: left;
    transition: background-color 0.15s ease;
  }

  .profile-menu-item:hover {
    background: rgb(241 245 249);
  }

  .menu-divider {
    height: 1px;
    margin: 0.375rem 0;
    background: rgb(226 232 240);
  }

  .menu-section-label {
    padding: 0.5rem 0.75rem 0.25rem;
    color: rgb(100 116 139);
    font-size: 0.75rem;
    font-weight: 600;
    line-height: 1rem;
  }

  .profile-menu-logout {
    color: rgb(220 38 38);
  }

  :global(.dark) .mobile-tab {
    color: rgb(161 161 170);
  }

  :global(.dark) .mobile-tab.active {
    color: rgb(96 165 250);
  }

  :global(.dark) .profile-menu-item {
    color: rgb(244 244 245);
  }

  :global(.dark) .profile-menu-item:hover {
    background: rgb(39 39 42);
  }

  :global(.dark) .menu-divider {
    background: rgb(63 63 70);
  }

  :global(.dark) .menu-section-label {
    color: rgb(161 161 170);
  }

  :global(.dark) .profile-menu-logout {
    color: rgb(248 113 113);
  }
</style>
