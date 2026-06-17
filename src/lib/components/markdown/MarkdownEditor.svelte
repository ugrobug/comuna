<script lang="ts">
  import { profile } from '$lib/auth.js'
  import MultiSelect from '$lib/components/input/Switch.svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import { t } from '$lib/translations'
  import { uploadImage } from '$lib/util.js'
  import { ImageInput, toast } from 'mono-svelte'
  import { Button, Label, Modal, TextArea } from 'mono-svelte'
  import { createEventDispatcher, tick, onMount } from 'svelte'
  import {
    Bold,
    CodeBracket,
    DocumentPlus,
    ExclamationTriangle,
    H1,
    Icon,
    Italic,
    Link,
    ListBullet,
    Photo,
    Strikethrough,
  } from 'svelte-hero-icons'
  import ImageUploadModal from '../lemmy/modal/ImageUploadModal.svelte'

  export let images: boolean = true
  export let value: string = ''
  export let label: string | undefined = undefined
  export let previewButton: boolean = true
  export let tools: boolean = true
  export let disabled: boolean = false
  export let rows: number = 2
  export let autoFocus: boolean = false
  export let showFooter: boolean = true
  export let helperText: string | undefined = undefined
  export let imageUploadHandler: ((image: File) => Promise<string | undefined>) | null = null
  export let imageInsertMode: 'markdown' | 'event' = 'markdown'

  export let beforePreview: (input: string) => string = (input) => input

  const dispatcher = createEventDispatcher<{ confirm: string; images: string[] }>()

  let textArea: HTMLTextAreaElement
  let imageInput: HTMLInputElement | null = null
  let linkDialogElement: HTMLDivElement | null = null
  let linkButtonElement: HTMLSpanElement | null = null
  let linkTextInput: HTMLInputElement | null = null
  let linkUrlInput: HTMLInputElement | null = null
  let linkDialogOpen = false
  let linkDialogStyle = ''
  let linkText = ''
  let linkUrl = ''
  let linkSelectionStart = 0
  let linkSelectionEnd = 0

  function replaceTextAtIndices(
    str: string,
    startIndex: number,
    endIndex: number,
    replacement: string
  ) {
    return str.substring(0, startIndex) + replacement + str.substring(endIndex)
  }

  function wrapSelection(start: string, end: string) {
    const startPos = textArea.selectionStart
    const endPos = textArea.selectionEnd

    const substring = textArea.value.substring(startPos, endPos)
    let newText = `${start}${substring}${end}`

    textArea.value = replaceTextAtIndices(
      textArea.value,
      startPos,
      endPos,
      newText
    )

    textArea.focus()
    textArea.selectionStart = startPos + start.length
    textArea.selectionEnd = endPos + start.length

    value = textArea.value
  }

  function looksLikeUrl(input: string) {
    const value = input.trim()
    return /^(https?:\/\/|mailto:|tel:|\/|#)/i.test(value) || /^www\./i.test(value)
  }

  function normalizeLinkUrl(input: string) {
    const value = input.trim()
    if (/^www\./i.test(value)) return `https://${value}`
    return value
  }

  function escapeMarkdownLinkText(input: string) {
    return input.replace(/\\/g, '\\\\').replace(/\[/g, '\\[').replace(/\]/g, '\\]')
  }

  function escapeMarkdownLinkUrl(input: string) {
    return input.replace(/\)/g, '%29')
  }

  function getMarkdownLinkMatch(input: string) {
    return input.match(/^\[([^\]]*)\]\(([^)]*)\)$/)
  }

  async function readClipboardUrl() {
    if (typeof navigator === 'undefined' || !navigator.clipboard?.readText) return ''
    try {
      const clipboardText = (await navigator.clipboard.readText()).trim()
      return looksLikeUrl(clipboardText) ? clipboardText : ''
    } catch {
      return ''
    }
  }

  function getTextareaCaretCoordinates(textarea: HTMLTextAreaElement, index: number) {
    if (typeof document === 'undefined') return textarea.getBoundingClientRect()

    const style = window.getComputedStyle(textarea)
    const mirror = document.createElement('div')
    const marker = document.createElement('span')
    const properties = [
      'box-sizing',
      'border-top-width',
      'border-right-width',
      'border-bottom-width',
      'border-left-width',
      'padding-top',
      'padding-right',
      'padding-bottom',
      'padding-left',
      'font-family',
      'font-size',
      'font-weight',
      'font-style',
      'letter-spacing',
      'line-height',
      'text-align',
      'text-indent',
      'text-transform',
      'word-spacing',
      'tab-size',
    ]

    properties.forEach((property) => {
      mirror.style.setProperty(property, style.getPropertyValue(property))
    })

    mirror.style.position = 'absolute'
    mirror.style.visibility = 'hidden'
    mirror.style.left = '-9999px'
    mirror.style.top = '0'
    mirror.style.width = `${textarea.offsetWidth}px`
    mirror.style.whiteSpace = 'pre-wrap'
    mirror.style.overflowWrap = 'break-word'
    mirror.style.wordBreak = 'break-word'
    mirror.textContent = textarea.value.substring(0, index)
    marker.textContent = textarea.value.substring(index) || '.'
    mirror.appendChild(marker)
    document.body.appendChild(mirror)

    const textareaRect = textarea.getBoundingClientRect()
    const mirrorRect = mirror.getBoundingClientRect()
    const markerRect = marker.getBoundingClientRect()
    const coordinates = {
      left: textareaRect.left + markerRect.left - mirrorRect.left - textarea.scrollLeft,
      top: textareaRect.top + markerRect.top - mirrorRect.top - textarea.scrollTop,
      height: markerRect.height || parseFloat(style.lineHeight) || 20,
    }

    mirror.remove()
    return coordinates
  }

  function positionLinkDialog() {
    if (!textArea || !linkDialogOpen) return

    const coordinates = getTextareaCaretCoordinates(textArea, linkSelectionStart)
    const dialogWidth = 352
    const dialogHeight = 224
    const margin = 12
    const maxLeft = Math.max(margin, window.innerWidth - dialogWidth - margin)
    const maxTop = Math.max(margin, window.innerHeight - dialogHeight - margin)
    const left = Math.min(
      Math.max(coordinates.left, margin),
      maxLeft
    )
    const top = Math.min(
      Math.max(coordinates.top + coordinates.height + 8, margin),
      maxTop
    )

    linkDialogStyle = `left: ${left}px; top: ${top}px;`
  }

  async function openLinkDialog() {
    if (disabled || !textArea) return

    linkSelectionStart = textArea.selectionStart
    linkSelectionEnd = textArea.selectionEnd
    const selectedText = textArea.value.substring(linkSelectionStart, linkSelectionEnd)
    const existingLink = getMarkdownLinkMatch(selectedText)
    const clipboardUrl = existingLink ? '' : await readClipboardUrl()

    linkText = existingLink?.[1] ?? selectedText
    linkUrl = existingLink?.[2] ?? clipboardUrl
    linkDialogStyle = 'left: 12px; top: 12px;'
    linkDialogOpen = true

    await tick()
    positionLinkDialog()
    if (linkUrl) {
      linkUrlInput?.focus()
      linkUrlInput?.select()
    } else {
      const initialInput = linkText ? linkUrlInput : linkTextInput
      initialInput?.focus()
    }
  }

  function closeLinkDialog() {
    linkDialogOpen = false
    textArea?.focus()
  }

  async function submitLinkDialog() {
    const normalizedUrl = normalizeLinkUrl(linkUrl)
    if (!normalizedUrl) {
      linkUrlInput?.focus()
      return
    }

    const displayText = linkText.trim() || normalizedUrl
    const markdown = `[${escapeMarkdownLinkText(displayText)}](${escapeMarkdownLinkUrl(
      normalizedUrl
    )})`
    linkDialogOpen = false
    await insertMarkdownAt(markdown, linkSelectionStart, linkSelectionEnd)
  }

  function handleLinkDialogKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape') {
      event.preventDefault()
      closeLinkDialog()
    }
    if (event.key === 'Enter') {
      event.preventDefault()
      void submitLinkDialog()
    }
  }

  function handleWindowMouseDown(event: MouseEvent) {
    if (!linkDialogOpen) return
    const target = event.target as Node | null
    if (!target) return
    if (linkDialogElement?.contains(target) || linkButtonElement?.contains(target)) return
    closeLinkDialog()
  }

  function handleWindowKeydown(event: KeyboardEvent) {
    if (linkDialogOpen && event.key === 'Escape') {
      event.preventDefault()
      closeLinkDialog()
    }
  }

  let uploadingImage = false
  let uploadingInlineImage = false
  let image: FileList | null = null

  export let previewing = false

  const shortcuts = {
    KeyB: () => wrapSelection('**', '**'),
    KeyI: () => wrapSelection('*', '*'),
    KeyS: () => wrapSelection('~~', '~~'),
    KeyH: () => wrapSelection('\n# ', ''),
    KeyK: () => void openLinkDialog(),
    Enter: (e: any) => {
      dispatcher('confirm', value)
      const newEvent = new Event('submit', { cancelable: true })
      e.target.form.dispatchEvent(newEvent)
    },
  }

  async function adjustHeight() {
    await tick()
    if (textArea) {
      textArea.style.height = 'auto' // Reset height to auto to calculate new height
      textArea.style.height = `${textArea.scrollHeight}px` // Set height to the scrollHeight
    }
  }

  async function insertMarkdownAt(
    markdown: string,
    startIndex = textArea?.selectionStart ?? value.length,
    endIndex = textArea?.selectionEnd ?? value.length
  ) {
    const currentValue = textArea?.value ?? value
    value = replaceTextAtIndices(currentValue, startIndex, endIndex, markdown)
    await tick()
    if (!textArea) return
    textArea.focus()
    const nextCursor = startIndex + markdown.length
    textArea.selectionStart = nextCursor
    textArea.selectionEnd = nextCursor
    await adjustHeight()
  }

  const imageFilesFromList = (files: FileList | File[]) =>
    Array.from(files).filter((file) => String(file?.type || '').startsWith('image/'))

  async function uploadAndInsertImages(files: File[], startIndex?: number, endIndex?: number) {
    if (!imageUploadHandler || !files.length || uploadingInlineImage) return
    uploadingInlineImage = true
    try {
      const urls = (
        await Promise.all(files.map((file) => imageUploadHandler?.(file)))
      ).filter((url): url is string => Boolean(url))
      if (!urls.length) return
      if (imageInsertMode === 'event') {
        dispatcher('images', urls)
        return
      }
      const markdown = `${urls.map((url) => `![](${url})`).join('\n\n')}\n\n`
      await insertMarkdownAt(markdown, startIndex, endIndex)
    } catch (err) {
      toast({
        content: (err as Error)?.message || 'Не удалось загрузить изображение',
        type: 'error',
      })
    } finally {
      uploadingInlineImage = false
    }
  }

  function openImageUpload() {
    if (disabled || uploadingInlineImage) return
    if (imageUploadHandler) {
      imageInput?.click()
      return
    }
    uploadingImage = !uploadingImage
  }

  function handleImageInputChange(event: Event) {
    const input = event.currentTarget as HTMLInputElement | null
    const files = input?.files ? imageFilesFromList(input.files) : []
    const startIndex = textArea?.selectionStart ?? value.length
    const endIndex = textArea?.selectionEnd ?? value.length
    if (input) input.value = ''
    void uploadAndInsertImages(files, startIndex, endIndex)
  }

  function handlePaste(event: ClipboardEvent) {
    const clipboardFiles = event.clipboardData?.files
    if (!clipboardFiles?.length) return
    const files = imageFilesFromList(clipboardFiles)
    if (!files.length) return
    if (imageUploadHandler) {
      event.preventDefault()
      const startIndex = textArea?.selectionStart ?? value.length
      const endIndex = textArea?.selectionEnd ?? value.length
      void uploadAndInsertImages(files, startIndex, endIndex)
      return
    }
    image = clipboardFiles
    uploadingImage = true
  }

  $: if (!previewing && value) adjustHeight()

  onMount(() => {
    if (autoFocus && textArea) {
      // Небольшая задержка для корректного рендеринга
      setTimeout(() => {
        textArea.focus()
      }, 100)
    }
  })
</script>

<svelte:window
  on:mousedown={handleWindowMouseDown}
  on:keydown={handleWindowKeydown}
  on:resize={positionLinkDialog}
  on:scroll={positionLinkDialog}
/>

{#if uploadingImage && images}
  <ImageUploadModal
    bind:open={uploadingImage}
    bind:image
    on:upload={(e) => {
      e.detail.forEach((i) => {
        wrapSelection(`![](${i})\n\n`, '')
      })
    }}
  />
{/if}

<div>
  {#if label || $$slots.label}
    <Label>
      {#if label}
        {label}
      {:else if $$slots.label}
        <slot name="label" />
      {/if}
    </Label>
  {/if}
  {#if helperText}
    <p class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
      {helperText}
    </p>
  {/if}
  <div
    class="flex flex-col border border-slate-200 border-b-slate-300 dark:border-t-zinc-700/70 dark:border-zinc-800
    focus-within:border-primary-900 focus-within:dark:border-primary-100 focus-within:ring ring-slate-300
    dark:ring-zinc-700 rounded-xl
overflow-hidden transition-colors {$$props.class}"
    class:mt-1={label}
  >
    {#if previewing}
      <div
        class="px-3 py-2.5 overflow-auto text-sm resize-y bg-white dark:bg-zinc-950"
      >
        <Markdown source={beforePreview(value)} />
      </div>
    {:else}
      {#if tools}
        <!--Toolbar-->
        <div
          class="[&>*]:flex-shrink-0 flex flex-row overflow-auto p-1.5 gap-1.5 border-b
          border-slate-200 dark:border-zinc-900 {$$props.disabled
            ? 'opacity-60 pointer-events-none'
            : ''}"
        >
          <Button
            on:click={() => wrapSelection('**', '**')}
            title="Bold"
            size="square-md"
          >
            <Icon src={Bold} size="16" mini />
          </Button>
          <Button
            on:click={() => wrapSelection('*', '*')}
            title="Italic"
            size="square-md"
          >
            <Icon src={Italic} size="16" micro />
          </Button>
          <span bind:this={linkButtonElement} class="inline-flex">
            <Button on:click={openLinkDialog} title="Link" size="square-md">
              <Icon src={Link} size="16" micro />
            </Button>
          </span>
          <Button
            on:click={() => wrapSelection('\n# ', '')}
            title="Header"
            size="square-md"
          >
            <Icon src={H1} size="16" micro />
          </Button>
          <Button
            on:click={() => wrapSelection('~~', '~~')}
            title="Strikethrough"
            size="square-md"
          >
            <Icon src={Strikethrough} size="16" micro />
          </Button>
          <Button
            on:click={() => wrapSelection('\n> ', '')}
            title="Quote"
            size="square-md"
          >
            <span class="font-bold font-serif text-lg">"</span>
          </Button>
          <Button
            on:click={() => wrapSelection('\n- ', '')}
            title="List"
            size="square-md"
          >
            <Icon src={ListBullet} micro size="16" />
          </Button>
          <Button
            on:click={() => wrapSelection('`', '`')}
            title="Code"
            size="square-md"
          >
            <Icon src={CodeBracket} micro size="16" />
          </Button>
          <Button
            on:click={() =>
              wrapSelection('::: spoiler <spoiler title>\n', '\n:::')}
            title="Spoiler"
            size="square-md"
          >
            <Icon src={ExclamationTriangle} micro size="16" />
          </Button>
          <Button
            on:click={() => wrapSelection('~', '~')}
            title="Subscript"
            size="square-md"
          >
            <span class="font-bold">
              X
              <sub>1</sub>
            </span>
          </Button>
          <Button
            on:click={() => wrapSelection('^', '^')}
            title="Superscript"
            size="square-md"
          >
            <span class="font-bold">
              X
              <sup>1</sup>
            </span>
          </Button>
          {#if images}
            <Button
              on:click={openImageUpload}
              title="Изображение"
              size="square-md"
              loading={uploadingInlineImage}
              disabled={disabled || uploadingInlineImage}
            >
              <Icon src={Photo} size="16" micro />
            </Button>
          {/if}
        </div>
      {/if}
      {#if linkDialogOpen}
        <div
          bind:this={linkDialogElement}
          class="fixed z-50 w-[min(22rem,calc(100vw-1.5rem))] rounded-xl border border-slate-200 bg-white p-3 shadow-xl shadow-slate-900/15 dark:border-zinc-700 dark:bg-zinc-950 dark:shadow-black/40"
          style={linkDialogStyle}
          role="dialog"
          aria-label="Вставка ссылки"
          tabindex="-1"
          on:keydown={handleLinkDialogKeydown}
        >
          <div class="space-y-2">
            <label class="block text-xs font-semibold text-slate-600 dark:text-zinc-300">
              Отображаемый текст
              <input
                bind:this={linkTextInput}
                bind:value={linkText}
                class="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-400 dark:focus:ring-primary-900/40"
                type="text"
              />
            </label>
            <label class="block text-xs font-semibold text-slate-600 dark:text-zinc-300">
              Ссылка
              <input
                bind:this={linkUrlInput}
                bind:value={linkUrl}
                class="mt-1 block w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-primary-500 focus:ring-2 focus:ring-primary-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-400 dark:focus:ring-primary-900/40"
                placeholder="https://"
                type="url"
              />
            </label>
          </div>
          <div class="mt-3 flex justify-end gap-2">
            <button
              type="button"
              class="rounded-lg px-3 py-1.5 text-sm font-semibold text-slate-600 hover:bg-slate-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
              on:click={closeLinkDialog}
            >
              Отмена
            </button>
            <button
              type="button"
              class="rounded-lg bg-primary-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-60"
              disabled={!normalizeLinkUrl(linkUrl)}
              on:click={submitLinkDialog}
            >
              Вставить
            </button>
          </div>
        </div>
      {/if}
      {#if images && imageUploadHandler}
        <input
          bind:this={imageInput}
          type="file"
          accept="image/*"
          multiple
          class="hidden"
          on:change={handleImageInputChange}
        />
      {/if}
      <!--Actual text area-->
      <TextArea
        class="bg-inherit z-0 border-0 rounded-none !ring-0 focus:!ring-transparent !transition-none resize-none"
        bind:value
        bind:element={textArea}
        on:keydown={(e) => {
          if (disabled) return
          if (e.ctrlKey || e.metaKey) {
            // @ts-ignore
            let shortcut = shortcuts[e.code]
            if (shortcut) {
              e.preventDefault()
              shortcut?.(e)
            }
          }
        }}
        on:input={adjustHeight}
        on:focus
        on:paste={handlePaste}
        {rows}
        {...$$restProps}
      />
    {/if}

    {#if showFooter}
      {#if previewButton}
        <div
          class="p-2 flex flex-row items-center w-full bg-white dark:bg-zinc-950 gap-1"
        >
          <MultiSelect
            bind:selected={previewing}
            options={[false, true]}
            optionNames={[$t('form.edit'), $t('form.preview')]}
          />
          <slot />
        </div>
      {:else}
        <div
          class="p-2 flex flex-row items-center w-full bg-white dark:bg-zinc-950 gap-1"
        >
          <slot name="actions" />
        </div>
      {/if}
    {/if}
  </div>
</div>
