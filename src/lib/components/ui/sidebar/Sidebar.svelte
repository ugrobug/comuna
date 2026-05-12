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
  } from 'svelte-hero-icons'
  import { notifications, profile } from '$lib/auth.js'
  import SidebarButton from '$lib/components/ui/sidebar/SidebarButton.svelte'
  import CommunityList from '$lib/components/ui/sidebar/CommunityList.svelte'
  import { Badge } from 'mono-svelte'
  import { t } from '$lib/translations'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { getTopCommunities, getFederatedCommunities } from '$lib/api/communities'
  import CommunityIcon from '$lib/components/ui/CommunityIcon.svelte'
  import { Icon } from 'svelte-hero-icons'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { env } from '$env/dynamic/public'
  import { HAS_LEMMY_INSTANCE } from '$lib/instance'
  import { buildComunsUrl, type BackendComun } from '$lib/api/backend'
  import { cachedJson } from '$lib/api/publicCache'
  import { userSettings } from '$lib/settings'

  const PUBLIC_PROJECT_ABOUT = env.PUBLIC_PROJECT_ABOUT || '/about';
  const PUBLIC_PROJECT_ADVRTISEMENT =
    env.PUBLIC_PROJECT_ADVRTISEMENT || '/advertisement';
  const PUBLIC_PROJECT_AUTHORS = env.PUBLIC_PROJECT_AUTHORS || '/authors';
  const PUBLIC_PROJECT_RULES = env.PUBLIC_PROJECT_RULES || '/rules';

  let topCommunities: Array<{
    name: string;
    icon: string | null;
    url: string;
    subscribers: number;
  }> = [];
  
  let displayedCommunitiesCount = 20; // Показываем первые 20 локальных
  let hasMoreCommunities = false; // Флаг наличия дополнительных сообществ
  let allLocalCommunities: Array<{
    name: string;
    icon: string | null;
    url: string;
    subscribers: number;
  }> = [];
  
  let federatedCommunities: Array<{
    name: string;
    icon: string | null;
    url: string;
    subscribers: number;
  }> = [];
  
  let showFederated = false; // Флаг показа федерациях сообществ

  let loginModalOpen = false;
  let comuns: BackendComun[] = [];
  let sidebarComuns: BackendComun[] = [];

  function handleAuthRequired(e: MouseEvent) {
    if (!$profile?.jwt) {
      e.preventDefault();
      loginModalOpen = true;
    }
  }
  
  function loadMoreCommunities() {
    if (!showFederated) {
      // Если еще не показываем федерация, сначала показываем все локальные
      if (displayedCommunitiesCount < allLocalCommunities.length) {
        // Показываем все локальные сообщества (без повторений)
        topCommunities = allLocalCommunities;
        displayedCommunitiesCount = allLocalCommunities.length;
        hasMoreCommunities = true; // Еще есть федерация
      } else {
        // Показываем федерация сообщества
        showFederated = true;
        loadFederatedCommunities();
      }
    } else {
      // Уже показываем федерация, добавляем еще
      const currentFederatedCount = displayedCommunitiesCount - allLocalCommunities.length;
      const newFederatedCount = currentFederatedCount + 10;
      
      // Показываем все локальные + больше федерация
      const federatedToShow = federatedCommunities.slice(0, newFederatedCount);
      topCommunities = [...allLocalCommunities, ...federatedToShow];
      displayedCommunitiesCount = allLocalCommunities.length + newFederatedCount;
      
      hasMoreCommunities = newFederatedCount < federatedCommunities.length;
    }
  }
  
  async function loadFederatedCommunities() {
    federatedCommunities = await getFederatedCommunities();
    
    // Показываем все локальные + первые 10 федерация
    const federatedToShow = federatedCommunities.slice(0, 10);
    topCommunities = [...allLocalCommunities, ...federatedToShow];
    displayedCommunitiesCount = allLocalCommunities.length + 10;
    hasMoreCommunities = 10 < federatedCommunities.length;
  }

  async function loadComuns() {
    try {
      const data = await cachedJson<{ comuns?: BackendComun[] }>(
        'public:comuns',
        buildComunsUrl(),
        { ttlMs: 120_000 }
      );
      comuns = data.comuns ?? [];
    } catch (e) {
      comuns = [];
    }
  }

  function updateDisplayedCommunities() {
    if (showFederated) {
      // Показываем все локальные + часть федерация
      const totalCommunities = [...allLocalCommunities, ...federatedCommunities];
      topCommunities = totalCommunities.slice(0, displayedCommunitiesCount);
      hasMoreCommunities = displayedCommunitiesCount < totalCommunities.length;
    } else {
      // Показываем только локальные
      topCommunities = allLocalCommunities.slice(0, displayedCommunitiesCount);
      hasMoreCommunities = displayedCommunitiesCount < allLocalCommunities.length || allLocalCommunities.length > 0;
    }
  }

  onMount(async () => {
    if (HAS_LEMMY_INSTANCE) {
      // Загружаем сообщества только если настроен инстанс Lemmy
      allLocalCommunities = await getTopCommunities();
      
      // Показываем первые 20 локальных сообществ
      topCommunities = allLocalCommunities.slice(0, displayedCommunitiesCount);
      // Кнопка показывается, если есть больше локальных ИЛИ есть федерация сообщества
      hasMoreCommunities = allLocalCommunities.length > displayedCommunitiesCount || allLocalCommunities.length > 0;
    }
    loadComuns();
  });

  $: searchParams = new URLSearchParams($page.url.search);
  $: currentFeed = searchParams.get('feed') ?? ($userSettings.homeFeed ?? 'hot');
  $: sidebarComuns = comuns.slice(0, 10);

</script>

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

<nav
  class="flex flex-col p-4 overflow-auto gap-2 h-auto min-h-0 sticky top-20 bg-slate-50 dark:bg-zinc-950 z-40 {$$props.class}"
  style={$$props.style}
>
  <div class="flex flex-col gap-1">
    <SidebarButton icon={Fire} href="/?feed=hot" active={currentFeed === 'hot'}>
      <span slot="label">Горячее</span>
    </SidebarButton>
    <SidebarButton icon={UserGroup} href="/?feed=mine" active={currentFeed === 'mine'}>
      <span slot="label">Моя лента</span>
    </SidebarButton>
    <SidebarButton icon={Bookmark} href="/?feed=favorites" active={currentFeed === 'favorites'}>
      <span slot="label">Избранное</span>
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

  <div class="flex flex-col gap-2">
      <span
        class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
      >
        Сообщества
      </span>
      <SidebarButton href="/comuns?create=1" icon={Plus}>
        <span slot="label">Создать сообщество</span>
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
          <span slot="label">{comun.name}</span>
        </SidebarButton>
      {/each}
          {#if comuns.length > 10}
            <SidebarButton href="/comuns" icon={ChevronDown}>
              <span slot="label">Все сообщества</span>
            </SidebarButton>
      {/if}
  </div>

  {#if HAS_LEMMY_INSTANCE}
    <div class="flex flex-col gap-2">
      {#if $profile?.jwt}
        <span 
          class="px-2 py-1 text-sm font-normal text-slate-500 dark:text-zinc-200"
        >
          {$t('nav.popular_communities')}
        </span>
      {/if}
      
      {#each topCommunities as community}
        <SidebarButton href={community.url}>
          <div slot="icon" class="w-7 h-7">
            <CommunityIcon name={community.name} icon={community.icon} />
          </div>
          <span slot="label">
            {community.name}
          </span>
        </SidebarButton>
      {/each}
      
      <!-- Отладка: {hasMoreCommunities} -->
      {#if hasMoreCommunities}
        <SidebarButton 
          on:click={loadMoreCommunities} 
          icon={ChevronDown}
          href="javascript:void(0)"
        >
          <span slot="label">Показать все</span>
        </SidebarButton>
      {/if}
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
      <SidebarButton href={PUBLIC_PROJECT_ABOUT} icon={InformationCircle}>
        <span slot="label">О Проекте</span>
      </SidebarButton>
      <SidebarButton href={PUBLIC_PROJECT_ADVRTISEMENT} icon={Megaphone}>
        <span slot="label">Реклама</span>
      </SidebarButton>
      <SidebarButton href={PUBLIC_PROJECT_AUTHORS} icon={PencilSquare}>
        <span slot="label">Авторам</span>
      </SidebarButton>
      <SidebarButton href={PUBLIC_PROJECT_RULES} icon={ClipboardDocumentList}>
        <span slot="label">Правила</span>
      </SidebarButton>
    </div>
  </div>

  <LoginModal bind:open={loginModalOpen} />
</nav>
