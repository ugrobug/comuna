<script lang="ts">
  import TelegramConnectionCard from '$lib/components/telegram/TelegramConnectionCard.svelte'
  import type { SiteNotificationEventSetting } from '$lib/siteAuth'
  import { createEventDispatcher } from 'svelte'

  export let events: SiteNotificationEventSetting[] = []
  export let loading = false
  export let saving = false
  export let telegramLinked = false
  export let telegramUsername = ''
  export let telegramFirstName = ''
  export let pushConfigured = false
  export let pushRegisteredDevicesCount = 0
  export let pushPlatforms: string[] = []

  const dispatch = createEventDispatcher<{
    toggle: { index: number; channel: 'site' | 'telegram' | 'push'; value: boolean }
    grouping: { index: number; groupingPeriod: 'none' | 'day' | 'week' }
  }>()

  const defaultGroupingOptions: Array<{ value: 'none' | 'day' | 'week'; label: string }> = [
    { value: 'none', label: 'Не группировать' },
    { value: 'day', label: 'Группировать за день' },
    { value: 'week', label: 'Группировать за неделю' },
  ]

  const handleToggle = (
    index: number,
    channel: 'site' | 'telegram' | 'push',
    event: Event
  ) => {
    const target = event.currentTarget as HTMLInputElement | null
    dispatch('toggle', {
      index,
      channel,
      value: Boolean(target?.checked),
    })
  }

  const handleGroupingChange = (index: number, event: Event) => {
    const target = event.currentTarget as HTMLSelectElement | null
    const rawValue = target?.value
    const value: 'none' | 'day' | 'week' =
      rawValue === 'day' || rawValue === 'week' ? rawValue : 'none'
    dispatch('grouping', {
      index,
      groupingPeriod: value,
    })
  }
</script>

<div class="flex flex-col gap-4">
  <div class="text-sm text-slate-500 dark:text-zinc-400">
    Выберите, для каких событий показывать уведомления в колокольчике на сайте и
    отправлять сообщения в Telegram-бот и push-уведомления в мобильные приложения.
    {#if saving}
      <span class="ml-1 text-slate-400 dark:text-zinc-500">Сохраняем...</span>
    {/if}
  </div>

  <TelegramConnectionCard
    linked={telegramLinked}
    username={telegramUsername}
    firstName={telegramFirstName}
  />

  {#if pushConfigured}
    <div class="rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm dark:border-zinc-800 dark:bg-zinc-900/60">
      <div class="font-medium text-slate-900 dark:text-zinc-100">
        Push-канал подключен
      </div>
      <div class="mt-1 text-slate-500 dark:text-zinc-400">
        Активных устройств: {pushRegisteredDevicesCount}
        {#if pushPlatforms.length}
          ({pushPlatforms.join(', ')})
        {/if}
      </div>
    </div>
  {/if}

  {#if loading && !events.length}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Загружаем настройки оповещений...
    </div>
  {:else if events.length}
    <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-zinc-800">
      <table class="w-full min-w-[960px] text-sm">
        <thead class="bg-slate-50 dark:bg-zinc-900/70">
          <tr class="text-left">
            <th class="px-4 py-3 font-medium text-slate-700 dark:text-zinc-200">Событие</th>
            <th class="px-4 py-3 font-medium text-center text-slate-700 dark:text-zinc-200 w-28">На сайте</th>
            <th class="px-4 py-3 font-medium text-center text-slate-700 dark:text-zinc-200 w-28">Telegram</th>
            <th class="px-4 py-3 font-medium text-center text-slate-700 dark:text-zinc-200 w-28">Push</th>
            <th class="px-4 py-3 font-medium text-slate-700 dark:text-zinc-200 w-52">Группировка</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200 dark:divide-zinc-800">
          {#each events as event, index}
            <tr class="align-top">
              <td class="px-4 py-3">
                <div class="font-medium text-slate-900 dark:text-zinc-100">
                  {event.title}
                </div>
                {#if event.description}
                  <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                    {event.description}
                  </div>
                {/if}
              </td>
              <td class="px-4 py-3 text-center">
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                  checked={event.site_enabled}
                  on:change={(event) => handleToggle(index, 'site', event)}
                />
              </td>
              <td class="px-4 py-3 text-center">
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                  checked={event.telegram_enabled}
                  on:change={(event) => handleToggle(index, 'telegram', event)}
                />
              </td>
              <td class="px-4 py-3 text-center">
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                  checked={event.push_enabled}
                  on:change={(event) => handleToggle(index, 'push', event)}
                />
              </td>
              <td class="px-4 py-3">
                {#if event.supports_grouping}
                  <select
                    class="w-full rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
                    value={event.grouping_period}
                    on:change={(event) => handleGroupingChange(index, event)}
                  >
                    {#each event.grouping_options.length ? event.grouping_options : defaultGroupingOptions as option}
                      <option value={option.value}>{option.label}</option>
                    {/each}
                  </select>
                {:else}
                  <span class="text-xs text-slate-400 dark:text-zinc-500">-</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

  {:else}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Список событий уведомлений пока пуст.
    </div>
  {/if}
</div>
