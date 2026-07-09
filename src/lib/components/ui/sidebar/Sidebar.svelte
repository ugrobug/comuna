<script lang="ts">
  import type { IconSource } from 'svelte-hero-icons'
  import {
    Inbox,
    UserGroup,
    Fire,
    Megaphone,
    DocumentText,
    InformationCircle,
    ChevronDown,
    Plus,
    PencilSquare,
    ClipboardDocumentList,
    Bookmark,
    ChartBar,
  } from 'svelte-hero-icons'
  import { notifications, profile } from '$lib/auth.js'
  import SidebarButton from '$lib/components/ui/sidebar/SidebarButton.svelte'
  import { Badge } from 'mono-svelte'
  import { locale, t } from '$lib/translations'
  import { normalizeInterfaceLanguage, originalPostLanguage } from '$lib/postLanguages'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { Icon } from 'svelte-hero-icons'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { env } from '$env/dynamic/public'
  import type { BackendComun } from '$lib/api/backend'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { loadSidebarComuns, selectSidebarComuns, sidebarComunsStore } from '$lib/communitySidebar'

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about';
  const PUBLIC_PROJECT_ADVRTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement';
  const PUBLIC_PROJECT_APPS = env.PUBLIC_PROJECT_APPS || '/apps';
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors';
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules';

  const localizedProjectPath = (path: string) => {
    const language = normalizeInterfaceLanguage($locale) ?? originalPostLanguage
    if (language === originalPostLanguage || !path.startsWith('/')) return path
    return `/${language}${path}`
  }

  let loginModalOpen = false;
  let sidebarComuns: BackendComun[] = [];
  let sidebarComunsTotal = 0;
  let communitiesOpen = true;
  let resourcesOpen = true;

  function handleAuthRequired(e: MouseEvent) {
    if (!$profile?.jwt) {
      e.preventDefault();
      loginModalOpen = true;
    }
  }
  onMount(() => {
    void loadSidebarComuns();
  });

  $: searchParams = new URLSearchParams($page.url.search);
  $: currentFeed = searchParams.get('feed') ?? ($userSettings.homeFeed ?? 'hot');
  $: sidebarComunsSelection = selectSidebarComuns(
    $sidebarComunsStore,
    $userSettings.myFeedComuns,
    !$siteToken || $feedSettingsHydrated
  );
  $: sidebarComuns = sidebarComunsSelection.items;
  $: sidebarComunsTotal = sidebarComunsSelection.total;
  $: projectAboutPath = localizedProjectPath(PUBLIC_PROJECT_ABOUT);
  $: projectAdvertisementPath = localizedProjectPath(PUBLIC_PROJECT_ADVRTISEMENT);
  $: projectAppsPath = localizedProjectPath(PUBLIC_PROJECT_APPS);
  $: projectAuthorsPath = localizedProjectPath(PUBLIC_PROJECT_AUTHORS);
  $: projectRulesPath = localizedProjectPath(PUBLIC_PROJECT_RULES);

</script>

<style>
  :global(.sidebar-title) {
    font-size: 16px !important;
    font-weight: 400 !important;
  }

  .sidebar-section-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    border-radius: 8px;
  }

  .sidebar-section-toggle:hover {
    background: rgba(148, 163, 184, 0.12);
  }

  :global(.dark) .sidebar-section-toggle:hover {
    background: rgba(63, 63, 70, 0.7);
  }

  .sidebar-section-chevron {
    transition: transform 0.18s ease;
  }

  .sidebar-section-chevron.expanded {
    transform: rotate(180deg);
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

<nav
  class="flex flex-col p-4 overflow-auto gap-2 h-auto min-h-0 sticky top-20 bg-slate-50 dark:bg-zinc-950 z-40 {$$props.class}"
  style={$$props.style}
>
  <div class="flex flex-col gap-1">
    <SidebarButton icon={Fire} href="/?feed=hot" active={currentFeed === 'hot'}>
      <span slot="label">{$t('site.sidebar.hot')}</span>
    </SidebarButton>
    <SidebarButton icon={UserGroup} href="/?feed=mine" active={currentFeed === 'mine'}>
      <span slot="label">{$t('site.sidebar.myFeed')}</span>
    </SidebarButton>
    <SidebarButton icon={Bookmark} href="/?feed=favorites" active={currentFeed === 'favorites'}>
      <span slot="label">{$t('site.sidebar.favorites')}</span>
    </SidebarButton>
  </div>

  {#if $profile?.jwt}
    <div class="flex flex-col gap-1">
      <SidebarButton icon={Inbox} href="/inbox" on:click={handleAuthRequired}>
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

  {#if $siteUser?.is_staff}
    <div class="flex flex-col gap-1">
      <SidebarButton icon={ChartBar} href="/moderator">
        <span slot="label">{$t('site.sidebar.moderator')}</span>
      </SidebarButton>
    </div>
  {/if}

  <div class="flex flex-col gap-2">
      <button
        type="button"
        class="sidebar-section-toggle px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
        aria-expanded={communitiesOpen}
        aria-controls="sidebar-communities-section"
        on:click={() => (communitiesOpen = !communitiesOpen)}
      >
        <span>{$t('site.sidebar.communities')}</span>
        <Icon
          src={ChevronDown}
          size="18"
          class="sidebar-section-chevron {communitiesOpen ? 'expanded' : ''}"
        />
      </button>
    {#if communitiesOpen}
      <div id="sidebar-communities-section" class="flex flex-col gap-1">
      <SidebarButton href="/comuns?create=1" icon={Plus}>
        <span slot="label">{$t('site.sidebar.createCommunity')}</span>
      </SidebarButton>
      {#each sidebarComuns as comun}
        <SidebarButton href={`/comuns/${comun.slug}`}>
          <div slot="icon" class="w-7 h-7 rounded-full overflow-hidden bg-slate-100 dark:bg-zinc-800 flex items-center justify-center">
            {#if comun.logo_url}
              <img src={comun.logo_url} alt={comun.name} class="w-full h-full object-cover" />
            {:else}
              <Icon src={DocumentText} size="20" />
            {/if}
          </div>
          <span slot="label" class="block min-w-0 truncate" title={comun.name}>{comun.name}</span>
        </SidebarButton>
      {/each}
          {#if sidebarComunsTotal > 10}
            <SidebarButton href="/comuns" icon={ChevronDown}>
              <span slot="label">{$t('site.sidebar.allCommunities')}</span>
            </SidebarButton>
      {/if}
      </div>
    {/if}
  </div>

  <div class="flex flex-col gap-2">
    <button
      type="button"
      class="sidebar-section-toggle px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
      aria-expanded={resourcesOpen}
      aria-controls="sidebar-resources-section"
      on:click={() => (resourcesOpen = !resourcesOpen)}
    >
      <span>{$t('site.sidebar.resources')}</span>
      <Icon
        src={ChevronDown}
        size="18"
        class="sidebar-section-chevron {resourcesOpen ? 'expanded' : ''}"
      />
    </button>
    {#if resourcesOpen}
    <div id="sidebar-resources-section" class="flex flex-col gap-2">
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
      <SidebarButton href={projectAboutPath} icon={InformationCircle}>
        <span slot="label">{$t('site.sidebar.aboutProject')}</span>
      </SidebarButton>
      <SidebarButton href={projectAdvertisementPath} icon={Megaphone}>
        <span slot="label">{$t('site.sidebar.advertisement')}</span>
      </SidebarButton>
      <SidebarButton href={projectAppsPath} icon={DocumentText}>
        <span slot="label">{$t('site.sidebar.apps')}</span>
      </SidebarButton>
      <SidebarButton href={projectAuthorsPath} icon={PencilSquare}>
        <span slot="label">{$t('site.sidebar.authors')}</span>
      </SidebarButton>
      <SidebarButton href={projectRulesPath} icon={ClipboardDocumentList}>
        <span slot="label">{$t('site.sidebar.rules')}</span>
      </SidebarButton>
    </div>
    </div>
    {/if}
  </div>

  <LoginModal bind:open={loginModalOpen} />
</nav>
