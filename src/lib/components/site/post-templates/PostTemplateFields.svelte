<script lang="ts">
  import { TextInput } from 'mono-svelte'
  import {
    MOVIE_REVIEW_KIND_OPTIONS,
    POST_TEMPLATE_TYPE_OPTIONS,
    createEmptyMovieReviewTemplateData,
    type MovieReviewTemplateData,
    type PostTemplateType,
  } from '$lib/postTemplates'

  export let templateType: '' | PostTemplateType = ''
  export let movieReviewData: MovieReviewTemplateData = createEmptyMovieReviewTemplateData()
</script>

<div class="template-fields rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-900/50 p-4 sm:p-5 flex flex-col gap-4">
  <div class="flex flex-col gap-1">
    <h3 class="text-base font-semibold text-slate-900 dark:text-zinc-100">Шаблон публикации</h3>
    <p class="text-sm text-slate-600 dark:text-zinc-400">
      Можно выбрать тип записи с дополнительными полями. Ниже останется обычный блоковый редактор.
    </p>
  </div>

  <label class="flex flex-col gap-1">
    <span class="text-sm text-slate-700 dark:text-zinc-300">Тип шаблона</span>
    <select
      bind:value={templateType}
      class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
    >
      {#each POST_TEMPLATE_TYPE_OPTIONS as option}
        <option value={option.value}>{option.label}</option>
      {/each}
    </select>
  </label>

  {#if templateType === 'movie_review'}
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <TextInput label="Название" bind:value={movieReviewData.title} placeholder="Например, Дюна: Часть вторая" />
      <TextInput
        label="Оригинальное название"
        bind:value={movieReviewData.original_title}
        placeholder="Например, Dune: Part Two"
      />
      <TextInput
        label="Ссылка на IMDb"
        bind:value={movieReviewData.imdb_url}
        placeholder="https://www.imdb.com/title/..."
      />
      <TextInput
        label="Постер (URL)"
        bind:value={movieReviewData.poster_url}
        placeholder="https://.../poster.jpg"
      />
      <TextInput label="Жанр" bind:value={movieReviewData.genre} placeholder="Фантастика, драма" />
      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Тип</span>
        <select
          bind:value={movieReviewData.content_kind}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        >
          {#each MOVIE_REVIEW_KIND_OPTIONS as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
      </label>
      <label class="flex flex-col gap-1">
        <span class="text-sm text-slate-700 dark:text-zinc-300">Дата премьеры</span>
        <input
          type="date"
          bind:value={movieReviewData.release_date}
          class="w-full rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
        />
      </label>
      <TextInput
        label="Где посмотреть"
        bind:value={movieReviewData.watch_where}
        placeholder="Кинотеатр, Netflix, Okko..."
      />
    </div>
  {/if}
</div>
