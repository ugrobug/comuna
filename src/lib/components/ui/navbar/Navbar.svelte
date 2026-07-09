<script lang="ts">
  import { notifications, profile } from '$lib/auth.js'
  import ShieldIcon from '$lib/components/lemmy/moderation/ShieldIcon.svelte'
  import {
    amModOfAny,
    isAdmin,
  } from '$lib/components/lemmy/moderation/moderation.js'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import HeaderSearch from '$lib/components/ui/navbar/HeaderSearch.svelte'
  import { site } from '$lib/lemmy.js'
  import { Button, Menu, MenuButton, MenuDivider } from 'mono-svelte'
  import {
    Icon,
    PencilSquare,
    Plus,
    ServerStack,
    Newspaper,
    Bars3,
    Fire,
    Inbox,
    UserGroup,
    ArrowPath,
    DocumentText,
    InformationCircle,
    Megaphone,
    ClipboardDocumentList,
    ChevronDown,
    Bookmark,
    ChartBar,
    ChatBubbleLeftRight
  } from 'svelte-hero-icons'
  import Profile from './Profile.svelte'
  import NavButton from './NavButton.svelte'
  import { LINKED_INSTANCE_URL } from '$lib/instance'
  import { locale, t } from '$lib/translations'
  import { normalizeInterfaceLanguage, originalPostLanguage } from '$lib/postLanguages'
  import { brandNameForLanguage } from '$lib/brand'
  import CommandsWrapper from './commands/CommandsWrapper.svelte'
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public';
  import SidebarButton from '$lib/components/ui/sidebar/SidebarButton.svelte'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { Badge } from 'mono-svelte'
  import { onMount } from 'svelte';
  import { siteToken, siteUser, logout as siteLogout } from '$lib/siteAuth'
  
  import type { BackendComun } from '$lib/api/backend'
  import { loadSidebarComuns, selectSidebarComuns, sidebarComunsStore } from '$lib/communitySidebar'
  import { getRandomTaglineFromSite, hasTaglines } from '$lib/taglineUtils.js';
  import Markdown from '$lib/components/markdown/Markdown.svelte';

  let sidebarComuns: BackendComun[] = [];
  let sidebarComunsTotal = 0;
  $: brandName = brandNameForLanguage($locale)

  const PUBLIC_TELEGRAM_URL = env.PUBLIC_TELEGRAM_URL;

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
  
  // Переменная для случайного слогана
  let randomTagline = '';

  onMount(() => {
    void loadSidebarComuns();
    
    // Добавляем обработчик клавиши Escape
    document.addEventListener('keydown', handleKeydown);
    
    return () => {
      document.removeEventListener('keydown', handleKeydown);
    };
  });

  let promptOpen: boolean = false
  let loginModalOpen = false
  let sidebarOpen = false;
  $: projectAboutPath = localizedProjectPath(PUBLIC_PROJECT_ABOUT);
  $: projectAdvertisementPath = localizedProjectPath(PUBLIC_PROJECT_ADVRTISEMENT);
  $: projectAppsPath = localizedProjectPath(PUBLIC_PROJECT_APPS);
  $: projectAuthorsPath = localizedProjectPath(PUBLIC_PROJECT_AUTHORS);
  $: projectRulesPath = localizedProjectPath(PUBLIC_PROJECT_RULES);
  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
  }


  // Функция для перехода на главную страницу с обновлением
  function goToHome() {
    const defaultFeed = $userSettings.homeFeed ?? 'hot'
    const target = defaultFeed === 'hot' ? '/' : `/?feed=${defaultFeed}`
    goto(target, { 
      replaceState: true,
      invalidateAll: true // Принудительно инвалидируем все данные
    })
  }

  function handleAuthRequired() {
    if (!$profile?.jwt) {
      loginModalOpen = true;
    }
  }

  // Обработка клавиши Escape для закрытия меню
  function handleKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && sidebarOpen) {
      sidebarOpen = false;
    }
  }

  // Функция для обновления случайного слогана
  function updateRandomTagline() {
    if (hasTaglines($site)) {
      randomTagline = getRandomTaglineFromSite($site);
    } else {
      randomTagline = '';
    }
  }

  // Реактивное обновление слогана при изменении данных сайта
  $: if ($site) {
    updateRandomTagline();
  }

  $: currentFeed = $page.url.searchParams.get('feed') ?? ($userSettings.homeFeed ?? 'hot')
  $: sidebarComunsSelection = selectSidebarComuns(
    $sidebarComunsStore,
    $userSettings.myFeedComuns,
    !$siteToken || $feedSettingsHydrated
  )
  $: sidebarComuns = sidebarComunsSelection.items
  $: sidebarComunsTotal = sidebarComunsSelection.total

  // Принудительное обновление при монтировании компонента
  onMount(() => {
    if ($site) {
      updateRandomTagline();
    }
  });
</script>

<CommandsWrapper bind:open={promptOpen} />
<nav
  class="flex flex-row gap-2 items-center w-full mx-auto z-[1000] box-border p-0 md:p-0.5
  @container backdrop-blur-xl 
  bg-slate-50/80 dark:bg-zinc-950/80
  pointer-events-auto overflow-visible
  border-b border-slate-300 dark:border-zinc-800
  md:relative fixed top-0 left-0 right-0 md:top-0 md:bottom-auto"
  style={$$props.style}
>
  <div class="w-full mx-auto px-0 md:py-2 py-1">
    <!-- Единый навбар для всех устройств -->
    <div class="grid navbar-desktop-grid items-center w-full">
      <!-- 1 колонка: гамбургер, логотип -->
      <div class="navbar-brand-cell flex min-w-0 items-center pl-0 gap-2">
        <!-- Кнопка гамбургера только на мобилках -->
        <button
          type="button"
          class="md:hidden w-10 h-10 shrink-0 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          title="Меню"
          aria-label={$t('site.nav.sideMenu')}
          aria-controls="mobile-site-menu"
          aria-expanded={sidebarOpen}
          on:click={toggleSidebar}
        >
          <Icon src={Bars3} size="18" class="w-4 h-4" />
        </button>
        <div
          class="logo min-w-0 cursor-pointer"
          on:click={goToHome}
          role="button"
          tabindex="0"
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goToHome()}
        >
          <span class="block truncate text-xl font-medium tracking-tight font-roboto text-slate-900 dark:text-white">
            {brandName}
          </span>
        </div>
      </div>
      <!-- 2 колонка: поиск -->
      <div class="hidden md:flex items-center justify-center w-full">
        <div class="w-full max-w-[500px]">
          <HeaderSearch />
        </div>
      </div>
      <!-- 3 колонка: все остальные элементы -->
      <div class="flex min-w-0 flex-row pr-0 md:pr-[30px] items-center gap-1.5 md:gap-2 w-full justify-end">
        {#if $profile?.user && isAdmin($profile.user)}
          <NavButton
            href="/admin"
            label={$t('nav.admin')}
            icon={ServerStack}
            class="relative hidden md:flex"
            isSelectedFilter={(path) => path.startsWith('/admin')}
          >
            {#if ($notifications.applications ?? 0) > 0}
              <div class="rounded-full w-2 h-2 bg-red-500 absolute -top-1 -left-1"></div>
            {/if}
          </NavButton>
        {/if}
        {#if amModOfAny($profile?.user)}
          <NavButton
            href="/moderation"
            label={$t('nav.moderation')}
            class="relative hidden md:flex"
          >
            {#if ($notifications.reports ?? 0) > 0}
              <div class="rounded-full w-2 h-2 bg-red-500 absolute -top-1 -left-1"></div>
            {/if}
            <ShieldIcon
              let:size
              let:isSelected
              slot="icon"
              filled={isSelected}
              width={size}
            />
          </NavButton>
        {/if}
        {#if randomTagline}
          <div class="w-full flex items-center justify-center gap-2 hidden md:flex">
            <div class="text-sm font-light text-center">
              <Markdown source={randomTagline} inline />
            </div>
            <button
              class="w-6 h-6 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
              title={$t('site.nav.refreshTagline')}
              on:click={updateRandomTagline}
            >
              <Icon src={ArrowPath} size="12" class="text-slate-500 dark:text-zinc-400" />
            </button>
          </div>
        {/if}
        <!-- Кнопка создания/входа -->
        {#if $profile?.jwt}
          <Menu placement="bottom-end">
            <Button
              color="primary"
              class="!rounded-full font-normal py-2 px-4 !text-base md:py-2 md:px-4 dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110"
              slot="target"
              title={$t('nav.create.label')}
            >
              <div class="flex flex-row items-center h-full gap-1.5 button-content justify-center text-center">
                <Icon src={Plus} size="16" micro class="md:w-4 md:h-4 w-3 h-3" />
                <span class="hidden md:inline">{$t('nav.create.label')}</span>
              </div>
            </Button>
            <MenuDivider>{$t('nav.create.label')}</MenuDivider>
            <MenuButton link href="/create/post" disabled={!$profile?.jwt}>
              <Icon src={PencilSquare} size="16" micro slot="prefix" />
              {$t('nav.create.post')}
            </MenuButton>
            <MenuButton
              link
              href="/comuns?create=1"
              disabled={!$profile?.jwt ||
                !$profile?.user ||
                ($site?.site_view.local_site.community_creation_admin_only &&
                  !isAdmin($profile.user))}
            >
              <Icon src={Newspaper} size="16" micro slot="prefix" />
              {$t('nav.create.community')}
            </MenuButton>
          </Menu>
        {:else}
          {#if $siteUser}
            {#await import('$lib/components/notifications/NotificationBellMenu.svelte') then { default: NotificationBellMenu }}
              <NotificationBellMenu />
            {/await}
            <Button
              color="primary"
              class="!rounded-full font-normal py-2 px-4 !text-base md:py-2 md:px-4 dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110"
              href="/account/new-post?new=1"
            >
              {$t('site.nav.write')}
            </Button>
            <Menu placement="bottom-end">
              <button
                slot="target"
                class="flex items-center gap-2 rounded-full border border-slate-200 dark:border-zinc-700 px-2 py-1 transition-colors hover:bg-slate-100 dark:hover:bg-zinc-800"
                title={$t('site.nav.userMenu')}
              >
                <Avatar
                  url={$siteUser.avatar_url || undefined}
                  width={32}
                  alt={$siteUser.username}
                />
                <Icon src={ChevronDown} size="16" class="text-slate-500 dark:text-zinc-400" />
              </button>
              <MenuButton link href="/settings" class="py-2.5">
                {$t('site.nav.settings')}
              </MenuButton>
              <MenuButton link href={`/id${$siteUser.id}`} class="py-2.5">
                {$t('site.nav.profile')}
              </MenuButton>
              <MenuButton link href="/chats" class="py-2.5">
                <Icon src={ChatBubbleLeftRight} size="16" micro slot="prefix" />
                {$t('site.nav.chats')}
              </MenuButton>
              <MenuButton
                class="py-2.5 text-red-600 dark:text-red-400"
                on:click={siteLogout}
              >
                {$t('account.logout')}
              </MenuButton>
            </Menu>
          {:else}
            <Button
              color="primary"
              class="!rounded-full font-normal py-2 px-4 !text-base md:py-2 md:px-4 dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110"
              title={$t('account.login')}
              on:click={() => (loginModalOpen = true)}
            >
              <span class="hidden md:inline">{$t('account.login')}</span>
              <span class="md:hidden">{$t('account.login')}</span>
            </Button>
          {/if}
        {/if}
        <!-- Профиль -->
        {#if $profile?.jwt}
          <Profile placement="bottom" />
        {/if}
      </div>
    </div>
    <div class="md:hidden mt-2 w-full min-w-0">
      <HeaderSearch compact />
    </div>
  </div>
</nav>

<LoginModal bind:open={loginModalOpen} />

{#if sidebarOpen}
  <div
    class="fixed left-0 right-0 z-[9999] md:hidden"
    style="pointer-events: auto; top: 112px; height: calc(100dvh - 112px);"
  >
    <button
      type="button"
      tabindex="-1"
      class="absolute inset-0 bg-black/30 transition-opacity duration-300"
      on:click={() => (sidebarOpen = false)}
      aria-label={$t('site.nav.closeMenu')}
    ></button>
    <aside
      id="mobile-site-menu"
      class="absolute left-0 top-0 bottom-0 w-[min(82vw,20rem)] h-full bg-white dark:bg-zinc-900 shadow-lg flex flex-col items-start justify-start overflow-y-auto p-4 gap-2 transform transition-transform duration-300"
      class:translate-x-0={sidebarOpen}
      class:-translate-x-full={!sidebarOpen}
      aria-label={$t('site.nav.sideMenu')}
    >
      <!-- Контент меню с отступом сверху -->
      <div class="flex flex-col gap-2 w-full">
      <div class="flex flex-col gap-1">
        <SidebarButton
          icon={Fire}
          href="/?feed=hot"
          active={currentFeed === 'hot'}
          on:click={() => { sidebarOpen = false; }}
        >
          <span slot="label">{$t('site.nav.hot')}</span>
        </SidebarButton>
        <SidebarButton
          icon={UserGroup}
          href="/?feed=mine"
          active={currentFeed === 'mine'}
          on:click={() => { sidebarOpen = false; }}
        >
          <span slot="label">{$t('site.nav.mine')}</span>
        </SidebarButton>
        <SidebarButton
          icon={Bookmark}
          href="/?feed=favorites"
          active={currentFeed === 'favorites'}
          on:click={() => { sidebarOpen = false; }}
        >
          <span slot="label">{$t('site.nav.favorites')}</span>
        </SidebarButton>
      </div>

      {#if $profile?.jwt}
        <div class="flex flex-col gap-1">
          <SidebarButton 
            icon={Inbox} 
            href="/inbox"
            on:click={() => { sidebarOpen = false; handleAuthRequired(); }}
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

      {#if $siteUser?.is_staff}
        <div class="flex flex-col gap-1">
          <SidebarButton
            icon={ChartBar}
            href="/moderator"
            on:click={() => { sidebarOpen = false; }}
          >
            <span slot="label">{$t('site.nav.moderator')}</span>
          </SidebarButton>
        </div>
      {/if}

      <div class="flex flex-col gap-2">
          <span 
            class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200 text-left"
          >
            {$t('site.nav.communities')}
          </span>
          <SidebarButton href="/comuns?create=1" icon={Plus} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.createCommunity')}</span>
          </SidebarButton>
          {#each sidebarComuns as comun}
            <SidebarButton href={`/comuns/${comun.slug}`} on:click={() => { sidebarOpen = false; }}>
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
          <SidebarButton href="/comuns" icon={ChevronDown} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.allCommunities')}</span>
          </SidebarButton>
      </div>

      <div class="flex flex-col gap-2">
        <span
          class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200 text-left"
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
          <SidebarButton href={projectAboutPath} icon={InformationCircle} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.aboutProject')}</span>
          </SidebarButton>
          <SidebarButton href={projectAdvertisementPath} icon={Megaphone} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.advertisement')}</span>
          </SidebarButton>
          <SidebarButton href={projectAppsPath} icon={DocumentText} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.apps')}</span>
          </SidebarButton>
          <SidebarButton href={projectAuthorsPath} icon={PencilSquare} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.authors')}</span>
          </SidebarButton>
          <SidebarButton href={projectRulesPath} icon={ClipboardDocumentList} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">{$t('site.nav.rules')}</span>
          </SidebarButton>
        </div>
      </div>

	      </div>
	      </aside>
  </div>
{/if}

<style>
  .navbar-desktop-grid {
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 0.5rem;
    display: grid;
    width: 100%;
  }

  /* Адаптивные размеры для мобильных устройств */
  /* Удалено: .logo img, .logo svg — не используется, всё через Tailwind */

  @media (min-width: 768px) {
    .navbar-desktop-grid {
      grid-template-columns: minmax(120px, 1fr) minmax(320px, 500px) minmax(120px, 1fr);
      column-gap: 1rem;
    }

    .navbar-brand-cell {
      padding-left: 64px;
    }
  }

  @media (min-width: 1280px) {
    nav > div {
      max-width: none;
    }
    
    .navbar-desktop-grid > *:first-child {
      justify-self: start;
      width: 100%;
    }
    .navbar-desktop-grid > *:last-child {
      justify-self: end;
      width: 100%;
    }
  }
</style>
