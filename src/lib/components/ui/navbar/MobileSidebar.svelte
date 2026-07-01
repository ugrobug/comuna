<script lang="ts">
  import {
    ArrowLeftOnRectangle,
    Inbox,
    UserCircle,
    UserGroup,
    Cog6Tooth,
    Fire,
    Megaphone,
    DocumentText,
    InformationCircle,
    PencilSquare,
    ClipboardDocumentList,
    Bookmark,
    ChevronDown,
    Plus,
  } from 'svelte-hero-icons'
  import { notifications, profile } from '$lib/auth.js'
  import SidebarButton from '$lib/components/ui/sidebar/SidebarButton.svelte'
  import { Badge } from 'mono-svelte'
  import { t } from '$lib/translations'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { Icon } from 'svelte-hero-icons'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { env } from '$env/dynamic/public'
  import { createEventDispatcher } from 'svelte'
  import type { BackendComun } from '$lib/api/backend'
  import { siteToken, siteUser, logout as siteLogout } from '$lib/siteAuth'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { loadSidebarComuns, selectSidebarComuns, sidebarComunsStore } from '$lib/communitySidebar'

  const dispatch = createEventDispatcher()

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about';
  const PUBLIC_PROJECT_ADVRTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement';
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors';
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules';

  let loginModalOpen = false;
  let sidebarComuns: BackendComun[] = [];
  let sidebarComunsTotal = 0;

  function handleAuthRequired(e: MouseEvent) {
    if (!$profile?.jwt) {
      e.preventDefault();
      loginModalOpen = true;
    }
  }

  function handleNavigation() {
    dispatch('close');
  }
  
  onMount(async () => {
    void loadSidebarComuns();
  });

  $: searchParams = new URLSearchParams($page.url.search);
  $: isPostFormRoute = $page.url.pathname.includes('/create/post') || 
                       $page.url.pathname.includes('/edit/post')
  $: currentFeed = $page.url.searchParams.get('feed') ?? ($userSettings.homeFeed ?? 'hot')
  $: sidebarComunsSelection = selectSidebarComuns(
    $sidebarComunsStore,
    $userSettings.myFeedComuns,
    !$siteToken || $feedSettingsHydrated
  )
  $: sidebarComuns = sidebarComunsSelection.items
  $: sidebarComunsTotal = sidebarComunsSelection.total
</script>

<nav class="flex flex-col p-4 overflow-auto gap-2 h-auto min-h-0">
  <div class="flex flex-col gap-1">
    {#if $siteUser}
      <SidebarButton href="/settings" on:click={handleNavigation} icon={Cog6Tooth}>
        <span slot="label">{$t('site.nav.settings')}</span>
      </SidebarButton>
      <SidebarButton href={`/id${$siteUser.id}`} on:click={handleNavigation} icon={UserCircle}>
        <span slot="label">{$t('site.nav.profile')}</span>
      </SidebarButton>
      <SidebarButton
        icon={ArrowLeftOnRectangle}
        on:click={() => {
          siteLogout();
          handleNavigation();
        }}
      >
        <span slot="label">{$t('account.logout')}</span>
      </SidebarButton>
    {:else}
      <SidebarButton
        icon={ArrowLeftOnRectangle}
        on:click={() => {
          loginModalOpen = true;
        }}
      >
        <span slot="label">{$t('account.login')}</span>
      </SidebarButton>
    {/if}
  </div>
  <div class="flex flex-col gap-1">
    <SidebarButton
      icon={Fire}
      href="/?feed=hot"
      active={currentFeed === 'hot'}
      on:click={handleNavigation}
    >
      <span slot="label">{$t('site.nav.hot')}</span>
    </SidebarButton>
    <SidebarButton
      icon={UserGroup}
      href="/?feed=mine"
      active={currentFeed === 'mine'}
      on:click={handleNavigation}
    >
      <span slot="label">{$t('site.nav.mine')}</span>
    </SidebarButton>
    <SidebarButton
      icon={Bookmark}
      href="/?feed=favorites"
      active={currentFeed === 'favorites'}
      on:click={handleNavigation}
    >
      <span slot="label">{$t('site.nav.favorites')}</span>
    </SidebarButton>
  </div>

  {#if $profile?.jwt}
    <div class="flex flex-col gap-1">
      <SidebarButton 
        icon={Inbox} 
        href="/inbox"
        on:click={(e) => {
          handleAuthRequired(e);
          if ($profile?.jwt) handleNavigation();
        }}
      >
        <span slot="label" class="flex items-center gap-2">
          {$t('profile.inbox')}
          {#if $notifications.inbox}
            <Badge
              class="w-5 h-5 !p-0 grid place-items-center ml-auto"
              color="red-subtle"
            >
              {$notifications.inbox}
            </Badge>
          {/if}
        </span>
      </SidebarButton>
    </div>
  {/if}

  <div class="flex flex-col gap-2">
      <span
        class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
      >
        {$t('site.nav.communities')}
      </span>
      <SidebarButton href="/comuns?create=1" on:click={handleNavigation} icon={Plus}>
        <span slot="label">{$t('site.nav.createCommunity')}</span>
      </SidebarButton>
      {#each sidebarComuns as comun}
        <SidebarButton
          href={`/comuns/${comun.slug}`}
          on:click={handleNavigation}
        >
          <div slot="icon" class="w-7 h-7 rounded-full overflow-hidden bg-slate-100 dark:bg-zinc-800 flex items-center justify-center">
            {#if comun.logo_url}
              <img src={comun.logo_url} alt={comun.name} class="w-full h-full object-cover" />
            {:else}
              <Icon src={DocumentText} size="20" />
            {/if}
          </div>
          <span slot="label">{comun.name}</span>
        </SidebarButton>
      {/each}
      <SidebarButton href="/comuns" on:click={handleNavigation} icon={ChevronDown}>
        <span slot="label">{$t('site.nav.allCommunities')}</span>
      </SidebarButton>
  </div>

  <div class="flex flex-col gap-2">
    <span
      class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
    >
      {$t('site.nav.resources')}
    </span>
    {#if env.PUBLIC_TELEGRAM_URL || env.PUBLIC_GITHUB_URL}
      <div class="flex items-center pl-2 gap-2">
        {#if env.PUBLIC_TELEGRAM_URL}
          <a href={env.PUBLIC_TELEGRAM_URL} target="_blank" rel="noopener noreferrer" class="telegram-btn group">
            <img src="/img/logos/telegram_logo.svg" alt="Telegram" class="w-5 h-5 min-w-[20px] min-h-[20px] max-w-[20px] max-h-[20px] transition-transform group-hover:scale-110 group-hover:drop-shadow-lg" />
          </a>
        {/if}
        {#if env.PUBLIC_GITHUB_URL}
          <a href={env.PUBLIC_GITHUB_URL} target="_blank" rel="noopener noreferrer" class="github-btn group">
            <img src="/img/logos/github-mark.svg" alt="GitHub" class="w-5 h-5 min-w-[20px] min-h-[20px] max-w-[20px] max-h-[20px] opacity-80 transition-transform group-hover:scale-110 group-hover:drop-shadow-lg dark:invert" />
          </a>
        {/if}
      </div>
    {/if}
    <div class="flex flex-col gap-1">
      <SidebarButton 
        href={PUBLIC_PROJECT_ABOUT} 
        icon={InformationCircle}
        on:click={handleNavigation}
      >
        <span slot="label">{$t('site.nav.aboutProject')}</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_ADVRTISEMENT} 
        icon={Megaphone}
        on:click={handleNavigation}
      >
        <span slot="label">{$t('site.nav.advertisement')}</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_AUTHORS} 
        icon={PencilSquare}
        on:click={handleNavigation}
      >
        <span slot="label">{$t('site.nav.authors')}</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_RULES} 
        icon={ClipboardDocumentList}
        on:click={handleNavigation}
      >
        <span slot="label">{$t('site.nav.rules')}</span>
      </SidebarButton>
    </div>
  </div>

  <LoginModal bind:open={loginModalOpen} />
</nav>

<style>
  :global(.sidebar-title) {
    font-size: 16px !important;
    font-weight: 400 !important;
  }
  .telegram-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: background 0.2s;
    padding: 2px;
  }

  .github-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: background 0.2s;
    padding: 2px;
  }
</style> 
