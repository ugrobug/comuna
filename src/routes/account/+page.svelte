<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button } from 'mono-svelte'
  import { fetchVerificationCode, logout, refreshSiteUser, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'

  let code = ''
  let loading = false
  let error = ''

  const loadCode = async () => {
    loading = true
    error = ''
    try {
      code = await fetchVerificationCode()
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось получить код'
    }
    loading = false
  }

  onMount(() => {
    refreshSiteUser()
  })
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Личный кабинет</h1>
  </Header>

  {#if $siteUser}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <div class="text-sm text-slate-500 dark:text-zinc-400">Вы вошли как</div>
      <div class="text-lg font-semibold">@{$siteUser.username}</div>
      {#if $siteUser.email}
        <div class="text-sm text-slate-500 dark:text-zinc-400">{$siteUser.email}</div>
      {/if}
    </div>

    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <h2 class="text-lg font-semibold mb-2">Подтверждение админа канала</h2>
      <p class="text-sm text-slate-500 dark:text-zinc-400">
        Получите код и отправьте его в бота. Бот подтвердит, что вы администратор канала.
      </p>
      <div class="mt-4 flex flex-wrap items-center gap-3">
        <Button size="sm" color="primary" on:click={loadCode} loading={loading} disabled={loading}>
          Получить код
        </Button>
        {#if code}
          <div class="rounded-lg bg-slate-100 dark:bg-zinc-900 px-4 py-2 text-sm font-mono">
            {code}
          </div>
        {/if}
      </div>
      {#if error}
        <p class="text-sm text-red-600 mt-3">{error}</p>
      {/if}
      <p class="text-sm text-slate-500 dark:text-zinc-400 mt-4">
        Отправьте код боту в Telegram — @comuna_tg_bot.
      </p>
    </div>

    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-6">
      <h2 class="text-lg font-semibold mb-2">Ваши подтверждённые каналы</h2>
      {#if $siteUser.is_author && $siteUser.authors.length}
        <ul class="flex flex-col gap-2 text-sm">
          {#each $siteUser.authors as author}
            <li>
              @{author.username}
              {#if author.title}
                <span class="text-slate-500 dark:text-zinc-400">— {author.title}</span>
              {/if}
            </li>
          {/each}
        </ul>
      {:else}
        <p class="text-sm text-slate-500 dark:text-zinc-400">Пока нет подтверждённых каналов.</p>
      {/if}
    </div>

    <div>
      <Button color="ghost" on:click={logout}>Выйти</Button>
    </div>
  {:else}
    <p class="text-sm text-slate-500 dark:text-zinc-400">
      Войдите, чтобы управлять своим профилем.
    </p>
  {/if}
</div>
