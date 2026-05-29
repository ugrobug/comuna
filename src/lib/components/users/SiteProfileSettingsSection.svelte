<script lang="ts">
  import TelegramLoginButton from '$lib/components/auth/TelegramLoginButton.svelte'
  import VkLoginButton from '$lib/components/auth/VkLoginButton.svelte'
  import type { SiteUser } from '$lib/siteAuth'
  import { Button, TextInput } from 'mono-svelte'
  import { createEventDispatcher } from 'svelte'

  export let siteUser: SiteUser | null = null
  export let displayName = ''
  export let avatarUrl = ''
  export let email = ''
  export let saving = false
  export let uploading = false

  const dispatch = createEventDispatcher<{
    avatarSelected: File
    clearAvatar: void
    externalLinked: void
    save: void
  }>()

  let fileInput: HTMLInputElement | null = null

  const onFileChange = (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file) return
    dispatch('avatarSelected', file)
    if (input) input.value = ''
  }

  const onExternalLinked = () => {
    dispatch('externalLinked')
  }
</script>

<div class="flex flex-col gap-4">
  <div class="text-sm text-slate-500 dark:text-zinc-400">
    Это профиль, который отображается на сайте в комментариях и на странице пользователя.
  </div>

  <div class="flex flex-col sm:flex-row gap-4 items-start">
    <div class="w-20 h-20 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
      {#if avatarUrl}
        <img src={avatarUrl} alt="Аватар профиля" class="w-full h-full object-cover" />
      {:else}
        <div class="w-full h-full grid place-items-center text-lg font-semibold text-slate-500 dark:text-zinc-400">
          {(siteUser?.display_name || siteUser?.username || '?').slice(0, 1).toUpperCase()}
        </div>
      {/if}
    </div>

    <div class="flex-1 min-w-0 flex flex-col gap-3">
      <input
        bind:this={fileInput}
        type="file"
        accept="image/*"
        class="hidden"
        on:change={onFileChange}
      />

      <TextInput
        bind:value={displayName}
        label="Имя отображаемое на сайте"
        placeholder={`Например: ${siteUser?.username ?? ''}`}
        maxLength={120}
      />

      <div class="flex flex-col gap-2">
        <TextInput
          bind:value={email}
          label="Email"
          placeholder="name@example.com"
        />
        {#if email && !siteUser?.email_verified}
          <div class="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200">
            Email нужно подтвердить. После сохранения мы отправим письмо с активационной ссылкой.
          </div>
        {:else if siteUser?.email_verified}
          <div class="text-xs text-emerald-700 dark:text-emerald-300">
            Email подтвержден.
          </div>
        {/if}
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          on:click={() => fileInput?.click()}
          disabled={saving || uploading}
        >
          {avatarUrl ? 'Заменить аватарку' : 'Загрузить аватарку'}
        </Button>
        {#if avatarUrl}
          <Button
            size="sm"
            color="ghost"
            on:click={() => dispatch('clearAvatar')}
            disabled={saving || uploading}
          >
            Убрать аватарку
          </Button>
        {/if}
        {#if uploading}
          <span class="text-xs text-slate-500 dark:text-zinc-400">Загрузка...</span>
        {/if}
      </div>

      <div class="flex flex-wrap items-center gap-2">
        <Button on:click={() => dispatch('save')} disabled={saving || uploading}>
          {saving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
        <div class="text-xs text-slate-500 dark:text-zinc-400">
          Логин @{siteUser?.username ?? ''} не меняется и используется для входа.
        </div>
      </div>

      <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
        <div class="text-sm font-semibold text-slate-900 dark:text-zinc-100">
          Связанные способы входа
        </div>
        <div class="mt-3 grid gap-3 md:grid-cols-2">
          {#if siteUser?.telegram_linked}
            <div class="rounded-xl border border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/70 dark:bg-zinc-950 dark:text-emerald-300">
              Telegram привязан{siteUser.telegram_username ? `: @${siteUser.telegram_username}` : ''}
            </div>
          {:else}
            <TelegramLoginButton
              label="Связать с Telegram"
              helperText="Привязать Telegram к текущему профилю"
              authIntent="login"
              privacyAccepted={false}
              onSuccess={onExternalLinked}
            />
          {/if}

          {#if siteUser?.vk_linked}
            <div class="rounded-xl border border-emerald-200 bg-white px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/70 dark:bg-zinc-950 dark:text-emerald-300">
              VK привязан{siteUser.vk_username ? `: ${siteUser.vk_username}` : ''}
            </div>
          {:else}
            <VkLoginButton
              label="Связать с VK"
              helperText="Привязать VK к текущему профилю"
              authIntent="login"
              privacyAccepted={false}
              onSuccess={onExternalLinked}
            />
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>
