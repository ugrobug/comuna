<script lang="ts">
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import { Button, Modal, toast } from 'mono-svelte'
  import { Clipboard, CodeBracket, Icon } from 'svelte-hero-icons'
  import {
    buildComunRoadmapEmbedCode,
    buildComunRoadmapEmbedPath,
  } from '$lib/roadmapEmbed'

  export let open = false
  export let slug = ''
  export let communityName = ''
  export let language = 'ru'

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: embedPath = buildComunRoadmapEmbedPath(slug, language)
  $: embedUrl = `${siteBaseUrl}${embedPath}`
  $: embedCode = buildComunRoadmapEmbedCode({
    baseUrl: siteBaseUrl,
    slug,
    language,
    communityName,
  })

  const copyEmbedCode = async () => {
    if (!embedCode) return
    try {
      await navigator.clipboard.writeText(embedCode)
      toast({ content: 'Код для вставки скопирован', type: 'success' })
    } catch {
      toast({ content: 'Не удалось скопировать код', type: 'error' })
    }
  }

  const selectCode = (event: FocusEvent) => {
    ;(event.currentTarget as HTMLTextAreaElement | null)?.select()
  }
</script>

<Modal bind:open dismissable title="Встроить дорожную карту">
  <div class="grid w-full min-w-0 max-w-full gap-5 sm:w-[34rem]">
    <p class="text-sm leading-6 text-slate-600 dark:text-zinc-300">
      Вставьте этот HTML-код на свой сайт. Виджет будет показывать публичную дорожную карту
      сообщества и обновляться автоматически.
    </p>

    <label class="grid min-w-0 gap-2">
      <span class="text-sm font-medium text-slate-900 dark:text-zinc-100">Код для вставки</span>
      <textarea
        readonly
        rows="5"
        wrap="soft"
        value={embedCode}
        on:focus={selectCode}
        class="box-border w-full min-w-0 max-w-full resize-none overflow-x-hidden rounded-lg border border-slate-300 bg-slate-50 p-3 font-mono text-xs leading-5 text-slate-800 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/15 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
      ></textarea>
    </label>

    <p class="text-xs leading-5 text-slate-500 dark:text-zinc-400">
      Ширина уже адаптивная. При необходимости измените значение <code>height="720"</code> в
      скопированном коде.
    </p>

    <div class="flex flex-wrap items-center gap-3 border-t border-slate-200 pt-4 dark:border-zinc-800">
      <Button color="primary" on:click={copyEmbedCode} disabled={!slug}>
        <Icon src={Clipboard} size="16" mini slot="prefix" />
        Скопировать код
      </Button>
      <a
        href={embedUrl}
        target="_blank"
        rel="noopener noreferrer"
        class="inline-flex min-h-10 items-center gap-2 rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-800 transition hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-800"
      >
        <Icon src={CodeBracket} size="16" mini />
        Открыть предпросмотр
      </a>
    </div>
  </div>
</Modal>
