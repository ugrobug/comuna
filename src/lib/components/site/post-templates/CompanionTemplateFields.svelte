<script lang="ts">
  import CompanionMap from './CompanionMap.svelte'
  import { normalizeCompanionTemplateData, type CompanionTemplateData } from '$lib/postTemplates'
  export let data: CompanionTemplateData
  const inputClass = 'w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
  const localDate = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }
  $: dateValue = localDate(data.starts_at)
  const updateDate = (event: Event) => {
    data = normalizeCompanionTemplateData({ ...data, starts_at: (event.target as HTMLInputElement).value })
  }
</script>

<div class="space-y-4">
  <p class="text-sm text-slate-500 dark:text-zinc-400">Пригласите одного спутника. Выберите участника из откликов — объявление закроется, а встреча появится в вашем общем чате.</p>
  <label class="flex flex-col gap-1 text-sm">
    Куда зовёте спутника
    <textarea class={inputClass} rows="3" maxlength="1000" placeholder="Например: прогуляться по парку и выпить кофе" bind:value={data.description} required></textarea>
  </label>
  <div class="grid gap-4 sm:grid-cols-2">
    <label class="flex flex-col gap-1 text-sm">Дата и время встречи
      <input class={inputClass} type="datetime-local" value={dateValue} on:change={updateDate} required />
      <span class="text-xs text-slate-500">Время в вашем часовом поясе.</span>
    </label>
    <label class="flex flex-col gap-1 text-sm">Название места (необязательно)
      <input class={inputClass} maxlength="255" placeholder="Например: главный вход в парк" bind:value={data.place} />
    </label>
  </div>
  <div>
    <p class="mb-2 text-sm">Нажмите на карту, чтобы выбрать место встречи.</p>
    <CompanionMap bind:lat={data.lat} bind:lng={data.lng} radius={data.radius_m} editable />
  </div>
  <div class="grid gap-3 sm:grid-cols-3">
    <label class="flex flex-col gap-1 text-sm">Широта
      <input class={inputClass} type="number" min="-85" max="85" step="any" bind:value={data.lat} placeholder="Выберите на карте" />
    </label>
    <label class="flex flex-col gap-1 text-sm">Долгота
      <input class={inputClass} type="number" min="-180" max="180" step="any" bind:value={data.lng} placeholder="Выберите на карте" />
    </label>
    <label class="flex flex-col gap-1 text-sm">Радиус, м (необязательно)
      <input class={inputClass} type="number" min="0" max="100000" step="100" bind:value={data.radius_m} placeholder="Без радиуса" />
    </label>
  </div>
</div>
