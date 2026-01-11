<script lang="ts">
  import { notifications, profile } from '$lib/auth.js'
  import ShieldIcon from '$lib/components/lemmy/moderation/ShieldIcon.svelte'
  import {
    amModOfAny,
    isAdmin,
  } from '$lib/components/lemmy/moderation/moderation.js'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { site } from '$lib/lemmy.js'
  import {
    Button,
    Menu,
    MenuButton,
    MenuDivider,
    Modal,
    Spinner,
  } from 'mono-svelte'
  import {
    GlobeAlt,
    Home,
    Icon,
    MagnifyingGlass,
    PencilSquare,
    Plus,
    ServerStack,
    XMark,
    ArrowLeftOnRectangle,
    Newspaper,
    Moon,
    Sun,
    UserCircle,
    Bars3,
    Trophy,
    Fire,
    Clock,
    Inbox,
    ArrowPath,
    DocumentText,
    InformationCircle,
    Megaphone,
    ClipboardDocumentList
  } from 'svelte-hero-icons'
  import Profile from './Profile.svelte'
  import NavButton from './NavButton.svelte'
  import { LINKED_INSTANCE_URL } from '$lib/instance'
  import { t } from '$lib/translations'
  import CommandsWrapper from './commands/CommandsWrapper.svelte'
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import { userSettings } from '$lib/settings'
  import { dockProps } from '../layout/Shell.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { colorScheme } from '$lib/ui/colors'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public';
  import SidebarButton from '$lib/components/ui/sidebar/SidebarButton.svelte'
  import { iconOfLink } from '$lib/components/ui/navbar/link'
  import { Badge } from 'mono-svelte'
  import { onMount } from 'svelte';
  import { siteUser, logout as siteLogout } from '$lib/siteAuth'
  
  import { buildRubricsUrl } from '$lib/api/backend';
  import { getRandomTaglineFromSite, hasTaglines } from '$lib/taglineUtils.js';
  import Markdown from '$lib/components/markdown/Markdown.svelte';

  let rubrics: Array<{ name: string; slug: string; icon_url?: string | null }> = [];

  const PUBLIC_TELEGRAM_URL = env.PUBLIC_TELEGRAM_URL;

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about';
  const PUBLIC_PROJECT_ADVRTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement';
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors';
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules';
  
  // Переменная для случайного слогана
  let randomTagline = '';

  async function loadRubrics() {
    try {
      const response = await fetch(buildRubricsUrl());
      if (!response.ok) return;
      const data = await response.json();
      rubrics = data.rubrics ?? [];
    } catch (e) {
      rubrics = [];
    }
  }

  onMount(() => {
    loadRubrics();
    
    // Добавляем обработчик клавиши Escape
    document.addEventListener('keydown', handleKeydown);
    
    return () => {
      document.removeEventListener('keydown', handleKeydown);
    };
  });

  let promptOpen: boolean = false
  let loginModalOpen = false
  let sidebarOpen = false;
  function toggleSidebar() {
    sidebarOpen = !sidebarOpen;
    console.log('sidebarOpen:', sidebarOpen);
  }

  // Функция для переключения темы
  function toggleTheme() {
    $colorScheme = $colorScheme === 'dark' ? 'light' : 'dark'
  }

  // Функция для перехода на главную страницу с обновлением
  function goToHome() {
    goto('/', { 
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

  // Принудительное обновление при монтировании компонента
  onMount(() => {
    if ($site) {
      updateRandomTagline();
    }
  });
</script>

<CommandsWrapper bind:open={promptOpen} />
<nav
  class="flex flex-row gap-2 items-center w-full mx-auto z-[1000] box-border p-0.5
  @container backdrop-blur-xl 
  bg-slate-50/80 dark:bg-zinc-950/80
  pointer-events-auto overflow-hidden 
  border-b border-slate-300 dark:border-zinc-800
  md:relative fixed top-0 left-0 right-0 md:top-0 md:bottom-auto"
  style={$$props.style}
>
  <div class="w-full max-w-screen-sm xl:max-w-[1280px] mx-auto px-3 sm:px-4 xl:px-0 md:py-2 py-1">
    <!-- Единый навбар для всех устройств -->
    <div class="grid navbar-desktop-grid items-center w-full">
      <!-- 1 колонка: гамбургер, логотип -->
      <div class="flex items-center pl-0 xl:pl-4 gap-2 min-w-[80px]">
        <!-- Кнопка гамбургера только на мобилках -->
        <button
          class="md:hidden w-10 h-10 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          title="Меню"
          on:click={toggleSidebar}
        >
          <Icon src={Bars3} size="18" class="w-4 h-4" />
        </button>
        <div 
          class="logo cursor-pointer"
          on:click={goToHome}
          role="button"
          tabindex="0"
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && goToHome()}
        >
          <span class="text-xl font-medium tracking-tight font-roboto text-slate-900 dark:text-white">
            Comuna
          </span>
        </div>
      </div>
      <!-- 2 колонка: админка и модерация -->
      <div class="flex flex-row items-center gap-2 justify-center w-full">
        {#if $profile?.user && isAdmin($profile.user)}
          <NavButton
            href="/admin"
            label={$t('nav.admin')}
            icon={ServerStack}
            class="relative"
            isSelectedFilter={(path) => path.startsWith('/admin')}
          >
            {#if ($notifications.applications ?? 0) > 0}
              <div class="rounded-full w-2 h-2 bg-red-500 absolute -top-1 -left-1"/>
            {/if}
          </NavButton>
        {/if}
        {#if amModOfAny($profile?.user)}
          <NavButton
            href="/moderation"
            label={$t('nav.moderation')}
            class="relative"
          >
            {#if ($notifications.reports ?? 0) > 0}
              <div class="rounded-full w-2 h-2 bg-red-500 absolute -top-1 -left-1"/>
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
              title="Обновить слоган"
              on:click={updateRandomTagline}
            >
              <Icon src={ArrowPath} size="12" class="text-slate-500 dark:text-zinc-400" />
            </button>
          </div>
        {/if}
      </div>
      <!-- 3 колонка: все остальные элементы -->
      <div class="flex flex-row xl:pr-4 items-center gap-2 w-full justify-end">
        <!-- Поиск -->
        <button
          class="w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          title={$t('nav.search')}
          on:click={() => window.location.href = '/search'}
        >
          <Icon src={MagnifyingGlass} size="18" class="w-4 h-4 md:w-[18px] md:h-[18px]" />
        </button>
        <!-- Переключатель темы -->
        <button
          on:click={toggleTheme}
          class="w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          title={$colorScheme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
        >
          {#if $colorScheme === 'dark'}
            <Icon src={Sun} size="18" class="w-4 h-4 md:w-[18px] md:h-[18px]" />
          {:else}
            <Icon src={Moon} size="18" class="w-4 h-4 md:w-[18px] md:h-[18px]" />
          {/if}
        </button>
        <!-- Кнопка создания/входа -->
        {#if $profile?.jwt}
          <Menu placement="bottom-end">
            <Button
              color="none"
              class="!rounded-full bg-orange-600 hover:bg-orange-700 text-white font-normal py-2 px-4 !text-base md:py-2 md:px-4"
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
              href="/create/community"
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
            <a
              href="/account"
              class="!rounded-full bg-orange-600 hover:bg-orange-700 text-white font-normal py-2 px-4 !text-base md:py-2 md:px-4"
            >
              Кабинет
            </a>
            <Button
              color="ghost"
              class="!rounded-full font-normal py-2 px-4 !text-base md:py-2 md:px-4"
              on:click={siteLogout}
            >
              Выйти
            </Button>
          {:else}
            <Button
              color="none"
              class="!rounded-full bg-orange-600 hover:bg-orange-700 text-white font-normal py-2 px-4 !text-base md:py-2 md:px-4"
              title={$t('account.login')}
              on:click={() => (loginModalOpen = true)}
            >
              <span class="hidden md:inline">{$t('account.login')}</span>
              <span class="md:hidden">Войти</span>
            </Button>
          {/if}
        {/if}
        <!-- Профиль -->
        {#if $profile?.jwt}
          <Profile placement="bottom" />
        {/if}
      </div>
    </div>
  </div>
</nav>

<LoginModal bind:open={loginModalOpen} />

{#if sidebarOpen}
  <button
    type="button"
    tabindex="-1"
    class="fixed left-0 right-0 z-[9999] bg-black/30 md:hidden transition-opacity duration-300"
    style="pointer-events: auto; top: 56px; height: calc(100vh - 56px);"
    on:click={toggleSidebar}
    aria-label="Закрыть меню"
  >
    <aside
      class="absolute left-0 top-0 bottom-0 w-3/4 h-full bg-white dark:bg-zinc-900 shadow-lg flex flex-col items-start justify-start overflow-y-auto p-4 gap-2 transform transition-transform duration-300"
      class:translate-x-0={sidebarOpen}
      class:-translate-x-full={!sidebarOpen}
      on:click|stopPropagation
      aria-label="Боковое меню"
    >
      <!-- Контент меню с отступом сверху -->
      <div class="flex flex-col gap-2 w-full">
        {#if $userSettings.dock.pins?.length ?? 0 > 0}
          <div class="flex items-center flex-wrap gap-2 pl-1.5">
          {#each $userSettings.dock.pins as pin}
            <SidebarButton
              icon={iconOfLink(pin.url)}
              on:click={() => { sidebarOpen = false; goto(pin.url); }}
              alignment="center"
              selected={`${$page.url.pathname}${$page.url.search}` == pin.url}
              on:contextmenu={(e) => {
                e.preventDefault()
                $userSettings.dock.pins = $userSettings.dock.pins.toSpliced(
                  $userSettings.dock.pins.findLastIndex((p) => pin.url == p.url),
                  1
                )
                return false
              }}
              size="square-md"
            ></SidebarButton>
          {/each}
        </div>
        <hr class="border-slate-200 dark:border-zinc-900 my-1" />
      {/if}

      {#if $profile?.jwt}
        <div class="flex flex-col gap-1">
          <SidebarButton 
            icon={Home} 
            href="/?type=Subscribed"
            on:click={() => { sidebarOpen = false; handleAuthRequired(); }}
          >
            <span slot="label">{$t('nav.feed')}</span>
          </SidebarButton>
          <SidebarButton 
            icon={Trophy}
            href="/?sort=TopAll&type=All"
            active={$page.url.pathname === '/' && $page.url.searchParams.get('sort') === 'TopAll'}
            on:click={() => { sidebarOpen = false; }}
          >
            <span slot="label">{$t('nav.best')}</span>
          </SidebarButton>
          <SidebarButton 
            icon={Fire} 
            href="/?sort=Hot"
            on:click={() => { sidebarOpen = false; }}
          >
            <span slot="label">{$t('filter.sort.hot')}</span>
          </SidebarButton>
          <SidebarButton 
            icon={Clock} 
            href="/?sort=New"
            on:click={() => { sidebarOpen = false; }}
          >
            <span slot="label">{$t('filter.sort.new')}</span>
          </SidebarButton>
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

      {#if rubrics.length}
        <div class="flex flex-col gap-2">
          <span 
            class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200 text-left"
          >
            Рубрики
          </span>
          {#each rubrics as rubric}
            <SidebarButton href={`/rubrics/${rubric.slug}/posts`} on:click={() => { sidebarOpen = false; }}>
              <div slot="icon" class="w-7 h-7 rounded-full overflow-hidden bg-slate-100 dark:bg-zinc-800 flex items-center justify-center">
                {#if rubric.icon_url}
                  <img src={rubric.icon_url} alt={rubric.name} class="w-full h-full object-cover" />
                {:else}
                  <Icon src={DocumentText} size="20" />
                {/if}
              </div>
              <span slot="label">{rubric.name}</span>
            </SidebarButton>
          {/each}
        </div>
      {/if}

      <div class="flex flex-col gap-2">
        <span
          class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200 text-left"
        >
          Ресурсы
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
          <SidebarButton href={PUBLIC_PROJECT_ABOUT} icon={InformationCircle} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">О Проекте</span>
          </SidebarButton>
          <SidebarButton href={PUBLIC_PROJECT_ADVRTISEMENT} icon={Megaphone} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">Реклама</span>
          </SidebarButton>
          <SidebarButton href={PUBLIC_PROJECT_AUTHORS} icon={PencilSquare} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">Авторам</span>
          </SidebarButton>
          <SidebarButton href={PUBLIC_PROJECT_RULES} icon={ClipboardDocumentList} on:click={() => { sidebarOpen = false; }}>
            <span slot="label">Правила</span>
          </SidebarButton>
        </div>
      </div>

      </aside>
    </button>
{/if}

<style>
  .navbar-desktop-grid {
    grid-template-columns: 1fr 3fr 1fr;
    display: grid;
    width: 100%;
  }

  /* Адаптивные размеры для мобильных устройств */
  /* Удалено: .logo img, .logo svg — не используется, всё через Tailwind */

  @media (max-width: 1279px) {
    nav > div {
      max-width: 960px;
    }
  }

  @media (max-width: 767px) {
    nav > div {
      max-width: none;
    }
  }

  @media (max-width: 639px) {
    nav > div {
      max-width: 640px;
    }
  }

  @media (min-width: 1280px) {
    nav > div {
      max-width: 1280px;
    }
    
    .navbar-desktop-grid > *:first-child {
      max-width: 15rem;
      justify-self: end;
      width: 100%;
    }
    .navbar-desktop-grid > *:last-child {
      max-width: 20rem;
      justify-self: start;
      width: 100%;
    }
  }
</style>
