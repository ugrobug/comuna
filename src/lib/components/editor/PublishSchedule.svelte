<script lang="ts">
  import { formatPublishAt, scheduleError, toLocalDateTime } from '$lib/postSchedule'

  export let value: string | null = null
  export let disabled = false
  let dialog: HTMLDialogElement
  let selection = ''
  let error = ''
  let timeZone = ''

  const open = () => {
    selection = toLocalDateTime(value)
    error = ''
    timeZone = Intl.DateTimeFormat().resolvedOptions().timeZone
    dialog.showModal()
  }

  const apply = () => {
    if (!selection) {
      error = 'Выберите дату и время публикации.'
      return
    }
    error = scheduleError(selection)
    if (error) return
    value = new Date(selection).toISOString()
    dialog.close()
  }

  const clear = () => {
    value = null
    dialog.close()
  }
</script>

<div class="inline-flex items-center gap-2">
  <button
    type="button"
    class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
    class:bg-sky-100={Boolean(value)}
    aria-label={value ? `Изменить время публикации: ${formatPublishAt(value)}` : 'Отложить публикацию'}
    title={value ? `Публикация ${formatPublishAt(value)}` : 'Отложить публикацию'}
    aria-haspopup="dialog"
    {disabled}
    on:click={open}
  >
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
      <circle cx="12" cy="13" r="8" /><path d="M12 9v4l3 2M9 2h6M12 2v3M19 6l1-1" />
    </svg>
  </button>
  {#if value}
    <span class="text-sm text-slate-600 dark:text-zinc-300">{formatPublishAt(value)}</span>
  {/if}
</div>

<dialog bind:this={dialog} class="w-[calc(100%-2rem)] max-w-sm rounded-2xl border border-slate-200 bg-white p-6 text-slate-900 shadow-xl backdrop:bg-black/40 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100" aria-label="Отложенная публикация">
  <div class="flex flex-col gap-4">
    <h2 class="text-lg font-semibold">Отложенная публикация</h2>
    <label class="flex flex-col gap-2 text-sm">
      Дата и время публикации
      <input type="datetime-local" bind:value={selection} min={toLocalDateTime(new Date().toISOString())} class="min-w-0 rounded-lg border border-slate-300 bg-transparent p-3 dark:border-zinc-600 dark:[color-scheme:dark]" />
    </label>
    <p class="text-sm text-slate-500 dark:text-zinc-400">Ваш часовой пояс: {timeZone}. Без выбранной даты пост публикуется сразу.</p>
    {#if error}<p class="text-sm text-red-600" role="alert">{error}</p>{/if}
    <div class="flex flex-wrap gap-2">
      <button type="button" class="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700" on:click={apply}>Готово</button>
      <button type="button" class="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-zinc-600" on:click={clear}>Убрать время</button>
      <button type="button" class="rounded-lg px-3 py-2 text-sm" on:click={() => dialog.close()}>Отмена</button>
    </div>
  </div>
</dialog>
