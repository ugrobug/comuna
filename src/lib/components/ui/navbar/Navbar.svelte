<script lang="ts">
  import { notifications, profile } from '$lib/auth.js'
  import { isAdmin } from '$lib/components/lemmy/moderation/moderation.js'
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
    ArrowPath,
    ChevronDown,
    ChatBubbleLeftRight
  } from 'svelte-hero-icons'
  import Profile from './Profile.svelte'
  import NavButton from './NavButton.svelte'
  import { LINKED_INSTANCE_URL } from '$lib/instance'
  import { locale, t } from '$lib/translations'
  import { brandNameForLanguage } from '$lib/brand'
  import CommandsWrapper from './commands/CommandsWrapper.svelte'
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { goto } from '$app/navigation'
  import { userSettings } from '$lib/settings'
  import { onMount } from 'svelte';
  import { siteUser, logout as siteLogout } from '$lib/siteAuth'
  import { getRandomTaglineFromSite, hasTaglines } from '$lib/taglineUtils.js';
  import Markdown from '$lib/components/markdown/Markdown.svelte';

  $: brandName = brandNameForLanguage($locale)
  
  // Переменная для случайного слогана
  let randomTagline = '';

  onMount(() => {
    if ($site) {
      updateRandomTagline();
    }
  });

  let promptOpen: boolean = false
  let loginModalOpen = false


  // Функция для перехода на главную страницу с обновлением
  function goToHome() {
    const defaultFeed = $userSettings.homeFeed ?? 'hot'
    const target = defaultFeed === 'hot' ? '/' : `/?feed=${defaultFeed}`
    goto(target, { 
      replaceState: true,
      invalidateAll: true // Принудительно инвалидируем все данные
    })
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
      <!-- 1 колонка: логотип -->
      <div class="navbar-brand-cell flex min-w-0 items-center gap-2">
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

<style>
  .navbar-desktop-grid {
    grid-template-columns: minmax(0, 1fr) auto;
    column-gap: 0.5rem;
    display: grid;
    width: 100%;
  }

  .navbar-brand-cell {
    padding-left: 0.75rem;
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
