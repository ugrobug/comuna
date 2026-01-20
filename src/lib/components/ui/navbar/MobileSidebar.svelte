<script lang="ts">
  import {
    ArrowLeftOnRectangle,
    Inbox,
    UserCircle,
    UserGroup,
    Cog6Tooth,
    Fire,
    Clock,
    Megaphone,
    DocumentText,
    InformationCircle,
    PencilSquare,
    ClipboardDocumentList,
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
  import { buildRubricsUrl } from '$lib/api/backend'
  import { siteUser, logout as siteLogout } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'

  const dispatch = createEventDispatcher()

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about';
  const PUBLIC_PROJECT_ADVRTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement';
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors';
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules';

  let loginModalOpen = false;
  let rubrics: Array<{ name: string; slug: string }> = [];

  function handleAuthRequired(e: MouseEvent) {
    if (!$profile?.jwt) {
      e.preventDefault();
      loginModalOpen = true;
    }
  }

  function handleNavigation() {
    dispatch('close');
  }
  
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

  onMount(async () => {
    loadRubrics();
  });

  $: searchParams = new URLSearchParams($page.url.search);
  $: isPostFormRoute = $page.url.pathname.includes('/create/post') || 
                       $page.url.pathname.includes('/edit/post')
  $: currentFeed = $page.url.searchParams.get('feed') ?? ($userSettings.homeFeed ?? 'hot')
</script>

<div style="background: #ffe; color: #b00; font-weight: bold; padding: 8px; text-align: center;">SIDEBAR TEST</div>

<nav class="flex flex-col p-4 overflow-auto gap-2 h-auto min-h-0">
  <div class="flex flex-col gap-1">
    {#if $siteUser}
      <SidebarButton href="/settings" on:click={handleNavigation} icon={Cog6Tooth}>
        <span slot="label">Настройки</span>
      </SidebarButton>
      <SidebarButton href=\"/account\" on:click={handleNavigation} icon={UserCircle}>
        <span slot=\"label\">Кабинет</span>
      </SidebarButton>
      <SidebarButton
        icon={ArrowLeftOnRectangle}
        on:click={() => {
          siteLogout();
          handleNavigation();
        }}
      >
        <span slot=\"label\">Выйти</span>
      </SidebarButton>
    {:else}
      <SidebarButton
        icon={ArrowLeftOnRectangle}
        on:click={() => {
          loginModalOpen = true;
        }}
      >
        <span slot=\"label\">Войти</span>
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
      <span slot="label">Горячее</span>
    </SidebarButton>
    <SidebarButton
      icon={Clock}
      href="/?feed=fresh"
      active={currentFeed === 'fresh'}
      on:click={handleNavigation}
    >
      <span slot="label">Свежее</span>
    </SidebarButton>
    <SidebarButton
      icon={UserGroup}
      href="/?feed=mine"
      active={currentFeed === 'mine'}
      on:click={handleNavigation}
    >
      <span slot="label">Моя лента</span>
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

  {#if rubrics.length}
    <div class="flex flex-col gap-2">
      <span
        class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
      >
        Рубрики
      </span>
      {#each rubrics as rubric}
        <SidebarButton
          href={`/rubrics/${rubric.slug}/posts`}
          on:click={handleNavigation}
        >
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
      class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
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
      <SidebarButton 
        href={PUBLIC_PROJECT_ABOUT} 
        icon={InformationCircle}
        on:click={handleNavigation}
      >
        <span slot="label">О Проекте</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_ADVRTISEMENT} 
        icon={Megaphone}
        on:click={handleNavigation}
      >
        <span slot="label">Реклама</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_AUTHORS} 
        icon={PencilSquare}
        on:click={handleNavigation}
      >
        <span slot="label">Авторам</span>
      </SidebarButton>
      <SidebarButton 
        href={PUBLIC_PROJECT_RULES} 
        icon={ClipboardDocumentList}
        on:click={handleNavigation}
      >
        <span slot="label">Правила</span>
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
