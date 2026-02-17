<script lang="ts">
  import { t } from '$lib/translations'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Badge, Popover, Button } from 'mono-svelte'
  import UserLink from '$lib/components/lemmy/user/UserLink.svelte'
  import RelativeDate, {
    formatRelativeDate,
  } from '$lib/components/util/RelativeDate.svelte'
  import type { Community, Person, SubscribedType } from 'lemmy-js-client'
  import {
    Bookmark,
    ExclamationTriangle,
    Icon,
    LockClosed,
    RocketLaunch,
    Trash,
    PaperAirplane,
  } from 'svelte-hero-icons'
  import { getInstance, getClient } from '$lib/lemmy.js'
  import ShieldIcon from '../moderation/ShieldIcon.svelte'
  import { userSettings, type View } from '$lib/settings'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import { Pencil } from 'svelte-hero-icons'
  import CommunityHeader from '../community/CommunityHeader.svelte'
  import { publishedToDate } from '$lib/components/util/date'
  import { postLink } from './helpers'
  import { toast } from 'mono-svelte'
  import { Plus, Check } from 'svelte-hero-icons'
  import { profile } from '$lib/auth'
  import { siteUser } from '$lib/siteAuth'
  import { addSubscription } from '$lib/lemmy/user'
  import { client } from '$lib/lemmy'
  import Subscribe from '../../../../routes/communities/Subscribe.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { EyeSlash } from 'svelte-hero-icons'

  export let community: Community | undefined = undefined
  export let user: Person | undefined = undefined
  export let published: Date | undefined = undefined
  export let title: string | undefined = undefined
  export let id: number | undefined = undefined
  export let read: boolean = false
  export let edited: string | undefined = undefined
  export let view: View = 'cozy'
  export let subscribed: SubscribedType | undefined = undefined
  export let userUrlOverride: string | undefined = undefined
  export let subscribeUrl: string | undefined = undefined
  export let subscribeLabel: string = 'Подписаться'
  export let disableUserLink: boolean = false

  // Badges
  export let badges = {
    nsfw: false,
    saved: false,
    featured: false,
    deleted: false,
    removed: false,
    locked: false,
    moderator: false,
    admin: false,
  }


  let popoverOpen = false
  let showLoginModal = false
  $: authorUsername = (user?.name ?? '').trim()
  $: authorKey = authorUsername.toLowerCase()
  $: myFeedAuthorKeys = new Set(
    ($userSettings.myFeedAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: authorInMyFeed = Boolean(authorKey && myFeedAuthorKeys.has(authorKey))
  $: authorHidden = Boolean(authorKey && hiddenAuthorKeys.has(authorKey))
  $: myFeedActionLabel = authorInMyFeed ? 'Убрать автора из моей ленты' : 'Добавить автора в мою ленту'
  $: hiddenActionLabel = authorHidden ? 'Показывать автора' : 'Скрыть автора'

  // Функция для безопасного получения hostname
  function getInstanceFromActorId(actorId: string | undefined, isLocal: boolean | undefined): string {
    if (isLocal === true) {
      return '';
    }

    try {
      if (!actorId?.trim()) {
        return '';
      }
      
      const cleanActorId = actorId
        .replace('https://https//', 'https://')
        .replace('https://https//', 'https://');
      
      try {
        return new URL(cleanActorId).hostname;
      } catch (e) {
        if (actorId.includes('.')) {
          return actorId;
        }
        return '';
      }
    } catch (e) {
      return '';
    }
  }

  $: userLink = userUrlOverride ?? `/u/${user?.name}${user?.local === true ? '' : `@${getInstanceFromActorId(user?.actor_id, user?.local)}`}`

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function formatCustomDate(date: Date): string {
    const now = new Date();
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    
    // Форматирование времени
    const formatTime = (d: Date) => {
      return d.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit'
      });
    };

    // Форматирование даты для текущего года
    const formatDateCurrentYear = (d: Date) => {
      const day = d.getDate(); // Получаем день без ведущего нуля
      const month = d.toLocaleDateString('ru-RU', {
        month: 'short'
      }).replace('.', '');
      
      return `${day} ${month}`;
    };

    // Форматирование даты для прошлых лет
    const formatDatePastYear = (d: Date) => {
      return d.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
      });
    };

    // Проверяем, сегодня ли пост
    if (date.toDateString() === now.toDateString()) {
      return formatTime(date);
    }
    
    // Проверяем, вчера ли пост
    if (date.toDateString() === yesterday.toDateString()) {
      return 'вчера';
    }
    
    // Проверяем, в этом ли году пост
    if (date.getFullYear() === now.getFullYear()) {
      return formatDateCurrentYear(date);
    }
    
    // Если пост в прошлом году или раньше
    return formatDatePastYear(date);
  }

  function handleSubscribeClick(subscribe: () => Promise<any>) {
    if (!$profile?.jwt) {
      showLoginModal = true;
      return;
    }
    
    subscribe().then(res => {
      if (res) {
        subscribed = res.community_view.subscribed;
        toast({
          content: subscribed === 'Subscribed' 
            ? $t('toast.subscribed') 
            : $t('toast.unsubscribed'),
          type: 'success'
        });
      }
    }).catch(error => {
      toast({
        content: $t('toast.error.subscribe'),
        type: 'error'
      });
    });
  }

  const toggleAuthorMyFeed = () => {
    if (!$siteUser) {
      showLoginModal = true
      return
    }
    if (!authorUsername) return

    const nextAuthors = new Set($userSettings.myFeedAuthors ?? [])
    const existing = Array.from(nextAuthors).find(
      (value) => value.toLowerCase() === authorKey
    )
    if (existing) {
      nextAuthors.delete(existing)
      toast({
        content: 'Автор убран из "Моей ленты"',
        type: 'success',
      })
    } else {
      nextAuthors.add(authorUsername)
      toast({
        content: 'Посты автора будут выводиться в "Моей ленте"',
        type: 'success',
      })
    }
    $userSettings = { ...$userSettings, myFeedAuthors: Array.from(nextAuthors) }
  }

  const toggleHiddenAuthor = () => {
    if (!$siteUser) {
      showLoginModal = true
      return
    }
    if (!authorUsername) return

    const nextHidden = new Set($userSettings.hiddenAuthors ?? [])
    const existingHidden = Array.from(nextHidden).find(
      (value) => value.toLowerCase() === authorKey
    )
    if (existingHidden) {
      nextHidden.delete(existingHidden)
      toast({
        content: 'Посты автора снова отображаются на сайте',
        type: 'success',
      })
    } else {
      nextHidden.add(authorUsername)
      toast({
        content: 'Вы больше не увидите посты автора на сайте',
        type: 'success',
      })
    }

    const nextMyFeed = new Set($userSettings.myFeedAuthors ?? [])
    const existingMyFeed = Array.from(nextMyFeed).find(
      (value) => value.toLowerCase() === authorKey
    )
    if (existingMyFeed && !existingHidden) {
      nextMyFeed.delete(existingMyFeed)
    }

    $userSettings = {
      ...$userSettings,
      hiddenAuthors: Array.from(nextHidden),
      myFeedAuthors: Array.from(nextMyFeed),
    }
  }
</script>

<LoginModal bind:open={showLoginModal} />

<!-- 
  @component
  This component will build two different things: a post's meta block and the title.
-->
<header
  class="grid w-full meta text-xs min-w-0 max-w-full max-h-none sm:max-h-[3.75rem]"
  class:compact={view == 'compact'}
  style={$$props.style ?? ''}
>
  <div class="flex gap-4">
    <!-- Аватары -->
    <div class="relative flex-shrink-0">
      {#if disableUserLink}
        <div class="block">
          <Avatar
            url={user?.avatar}
            width={48}
            alt={user?.name}
            circle={true}
            class_="!rounded-full"
          />
        </div>
      {:else}
        <a
          href={userLink}
          class="block cursor-pointer"
          data-sveltekit-preload-data="tap"
        >
          <Avatar
            url={user?.avatar}
            width={48}
            alt={user?.name}
            circle={true}
            class_="!rounded-full hover:ring-2 transition-all ring-offset-0 ring-primary-900 dark:ring-primary-100"
          />
        </a>
      {/if}
      
      <!-- rubric icon removed -->
    </div>

    <!-- Информация -->
    <div class="flex flex-col min-w-0 justify-center">
      <div class="flex items-center gap-1">
        {#if disableUserLink}
          <span class="text-base font-normal !text-black dark:!text-white block max-w-full break-words line-clamp-2 sm:line-clamp-1">
            {user?.display_name || user?.name}
          </span>
        {:else}
          <a 
            href={userLink}
            class="text-base font-normal hover:underline !text-black dark:!text-white block max-w-full break-words line-clamp-2 sm:line-clamp-1"
            data-sveltekit-preload-data="tap"
          >
            {user?.display_name || user?.name}
          </a>
        {/if}
        
        {#if badges.admin}
          <img 
            src="/badge.svg" 
            alt="Администрация"
            class="w-4 h-4 !m-0" 
            title="Администрация"
          />
        {/if}
      </div>
      
      <div class="flex items-center gap-1 !text-slate-400 dark:!text-zinc-500">
        {#if community}
          <span class="!text-black dark:!text-white font-normal">{community.title}</span>
        {/if}
        {#if published}
          <span>{formatCustomDate(published)}</span>
          {#if edited}
            <div class="text-slate-400">
              <Icon src={Pencil} micro size="14" />
            </div>
          {/if}
        {/if}
      </div>
    </div>
  </div>

  <!-- Бейджи -->
  <div class="flex flex-row justify-end items-center gap-2 ml-auto">
    <!-- Tags removed -->
    {#if badges.nsfw}
      <Badge 
        label={$t('post.badges.nsfw')} 
        color="red-subtle" 
        allowIconOnly 
        class="h-8 w-8 flex items-center justify-center !p-0"
      >
        <Icon src={ExclamationTriangle} size="14" micro slot="icon" />
      </Badge>
    {/if}
    {#if badges.saved}
      <Badge
        label={$t('post.badges.saved')}
        color="yellow-subtle"
        allowIconOnly
        class="h-8 w-8 flex items-center justify-center !p-0"
      >
        <Icon src={Bookmark} micro size="14" slot="icon" />
      </Badge>
    {/if}
    {#if badges.removed}
      <Badge 
        label={$t('post.badges.removed')} 
        color="red-subtle" 
        allowIconOnly
        class="h-8 flex items-center"
      >
        <Icon src={Trash} micro size="14" slot="icon" />
        <span class="max-md:hidden">{$t('post.badges.removed')}</span>
      </Badge>
    {/if}
    {#if badges.deleted}
      <Badge 
        label={$t('post.badges.deleted')} 
        color="red-subtle" 
        allowIconOnly
        class="h-8 flex items-center"
      >
        <Icon src={Trash} micro size="14" slot="icon" />
        <span class="max-md:hidden">{$t('post.badges.deleted')}</span>
      </Badge>
    {/if}
    <div class="flex sm:flex-row flex-row gap-2 items-end">
      {#if badges.featured}
        <Icon 
          src={RocketLaunch}
          size="24" 
          outline
          class="text-slate-500 dark:text-zinc-400 self-center h-8 flex items-center" 
        />
      {/if}
	      {#if community}
	        {#if subscribeUrl}
	            <Button
	              size="square-md"
	              color="primary"
	              class="ml-2 max-sm:hidden h-8 w-8 !min-h-[2rem] !min-w-[2rem] !px-0 dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110 action-tooltip"
	              href={subscribeUrl}
	              target="_blank"
	              rel="nofollow noopener"
	              title={subscribeLabel}
	              aria-label={subscribeLabel}
                data-tooltip={subscribeLabel}
	            >
	              <span class="inline-flex items-center justify-center text-white">
	                <img src="/img/logos/telegram_logo.svg" alt="Telegram" class="w-4 h-4" />
	              </span>
	          </Button>
        {:else}
        <Subscribe community={{
          community,
          subscribed: subscribed || 'NotSubscribed',
          blocked: false,
          counts: {
            community_id: community.id,
            subscribers: 0,
            subscribers_local: 0,
            posts: 0,
            comments: 0,
            published: "",
            users_active_day: 0,
            users_active_week: 0,
            users_active_month: 0,
            users_active_half_year: 0
          },
          banned_from_community: false
        }}>
          <svelte:fragment let:subscribe let:subscribing>
            <!-- Кнопка для десктопа -->
            <Button
              size="sm"
              color={subscribed === 'Subscribed' ? 'secondary' : 'primary'}
              class="ml-2 max-sm:hidden h-8 !min-h-[2rem]"
              on:click={() => handleSubscribeClick(subscribe)}
              disabled={subscribing}
            >
              {subscribed === 'Subscribed' ? $t('cards.community.subscribed') : $t('cards.community.subscribe')}
            </Button>

            <!-- Иконка для мобильных -->
            <button
              class="hidden max-sm:flex items-center justify-center w-8 h-8 rounded-full transition-colors ml-2
              {subscribed === 'Subscribed' 
                ? 'bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400' 
                : 'bg-primary-100 dark:bg-primary-900 text-primary-900 dark:text-primary-100'}"
              on:click={() => handleSubscribeClick(subscribe)}
              disabled={subscribing}
              title={subscribed === 'Subscribed' ? $t('cards.community.subscribed') : $t('cards.community.subscribe')}
              aria-label={subscribed === 'Subscribed' ? $t('cards.community.subscribed') : $t('cards.community.subscribe')}
            >
              <Icon 
                src={subscribed === 'Subscribed' ? Check : Plus} 
                size="18"
                mini
              />
              <span class="sr-only">
                {subscribed === 'Subscribed' ? $t('cards.community.subscribed') : $t('cards.community.subscribe')}
              </span>
            </button>
          </svelte:fragment>
        </Subscribe>
        {/if}
      {/if}
      {#if $siteUser && authorUsername}
        <button
          type="button"
          class="inline-flex items-center justify-center h-8 w-8 rounded-full border transition-colors action-tooltip
          {authorInMyFeed
            ? 'border-blue-300 bg-blue-50 text-blue-600 dark:border-blue-700 dark:bg-blue-950 dark:text-blue-300'
            : 'border-slate-300 bg-white text-slate-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300'}"
          title={myFeedActionLabel}
          aria-label={myFeedActionLabel}
          data-tooltip={myFeedActionLabel}
          on:click={toggleAuthorMyFeed}
        >
          <Icon src={authorInMyFeed ? Check : Plus} size="16" mini />
          <span class="sr-only">{myFeedActionLabel}</span>
        </button>
        <button
          type="button"
          class="inline-flex items-center justify-center h-8 w-8 rounded-full border transition-colors action-tooltip
          {authorHidden
            ? 'border-rose-300 bg-rose-50 text-rose-600 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-300'
            : 'border-slate-300 bg-white text-slate-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300'}"
          title={hiddenActionLabel}
          aria-label={hiddenActionLabel}
          data-tooltip={hiddenActionLabel}
          on:click={toggleHiddenAuthor}
        >
          <Icon src={EyeSlash} size="16" mini />
          <span class="sr-only">{hiddenActionLabel}</span>
        </button>
      {/if}
    </div>
    <slot name="badges" />
  </div>
</header>
{#if title && id}
  <a
    href={postLink({ id, name: title })}
    class="inline hover:underline
    hover:text-primary-900 hover:dark:text-primary-100 transition-colors max-[480px]:!mt-0
    font-medium {$$props.titleClass ?? ''}"
    class:text-slate-800={$userSettings.markReadPosts && read}
    class:dark:text-zinc-400={$userSettings.markReadPosts && read}
    class:text-base={view == 'compact'}
    class:text-lg={view != 'compact'}
    style="grid-area: title;"
    data-sveltekit-preload-data="tap"
  >
    <Markdown
      source={title}
      inline
      noStyle
      class={view == 'compact' ? '' : 'leading-[1.3]'}
    ></Markdown>
  </a>
{:else}
  <div style="grid-area: title; margin: 0;"></div>
{/if}

<style>
  .meta {
    grid-template-columns: 1fr auto;
    gap: 1rem;
    align-items: center;
  }

  .action-tooltip {
    position: relative;
  }

  .action-tooltip::after {
    content: attr(data-tooltip);
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    bottom: calc(100% + 8px);
    background: rgba(15, 23, 42, 0.95);
    color: #fff;
    font-size: 12px;
    line-height: 1.2;
    white-space: nowrap;
    padding: 6px 8px;
    border-radius: 6px;
    opacity: 0;
    pointer-events: none;
    z-index: 40;
    transition: opacity 0.12s ease;
  }

  .action-tooltip:hover::after,
  .action-tooltip:focus-visible::after {
    opacity: 1;
  }
</style>
