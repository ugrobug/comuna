<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildComunCustomTemplateEditorPath,
    buildComunUrl,
    type BackendComun,
    type BackendComunCustomTemplate,
  } from '$lib/api/backend'
  import { getTemplateEditorBlocks } from '$lib/postTemplates'
  import { siteToken } from '$lib/siteAuth'

  export let data

  type BlockPlacement = 'available' | 'header' | 'footer'
  type FieldType = 'text' | 'file' | 'select' | 'checkbox'
  type FieldPlacement = 'header' | 'footer'
  type PaletteFieldType = 'text' | 'select' | 'checkbox'
  type DragPaletteItem =
    | { kind: 'block'; blockType: string }
    | { kind: 'field'; fieldType: PaletteFieldType }

  const slug = String(data?.slug ?? '')
  const templateRef = String(data?.template ?? 'new')
  const isNewTemplate = templateRef === 'new'
  const DRAG_TYPE = 'application/x-comuna-template-palette'

  const fallbackBlockPlacementOptions = [
    { value: 'available', label: 'Текст' },
    { value: 'header', label: 'Header' },
    { value: 'footer', label: 'Footer' },
  ]
  const fallbackBlockOptions = getTemplateEditorBlocks('movie_review').map((option) => ({
    value: option.type,
    label: option.label,
  }))
  const fallbackFieldTypeOptions = [
    { value: 'text', label: 'Текст' },
    { value: 'file', label: 'Файл' },
    { value: 'select', label: 'Выбор значений' },
    { value: 'checkbox', label: 'Чекбокс' },
  ]
  const fallbackFieldPlacementOptions = [
    { value: 'header', label: 'Header' },
    { value: 'footer', label: 'Footer' },
  ]

  let comun: BackendComun | null = data?.comun ?? null
  let loading = true
  let saving = false
  let deleting = false
  let errorMessage = ''
  let draft: BackendComunCustomTemplate | null = null

  let headerBlockToAdd = ''
  let textBlockToAdd = ''
  let footerBlockToAdd = ''
  let headerBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let bodyBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let footerBlocks: NonNullable<BackendComunCustomTemplate['blocks']> = []
  let headerFields: NonNullable<BackendComunCustomTemplate['fields']> = []
  let footerFields: NonNullable<BackendComunCustomTemplate['fields']> = []
  let headerBlockOptionsToAdd: Array<{ value: string; label: string }> = []
  let bodyBlockOptionsToAdd: Array<{ value: string; label: string }> = []
  let footerBlockOptionsToAdd: Array<{ value: string; label: string }> = []
  let activeDropZone: 'header' | 'available' | 'footer' | null = null

  const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value))

  const normalizeTemplate = (template?: BackendComunCustomTemplate | null): BackendComunCustomTemplate => ({
    id: Number(template?.id) > 0 ? Number(template?.id) : undefined,
    name: String(template?.name ?? '').trim(),
    slug: String(template?.slug ?? '').trim() || undefined,
    sort_order: Number(template?.sort_order ?? 0) || 0,
    blocks: Array.isArray(template?.blocks)
      ? template.blocks.map((block, index) => ({
          id: Number(block?.id) > 0 ? Number(block?.id) : undefined,
          block_type: String(block?.block_type ?? '').trim(),
          placement: (String(block?.placement ?? '').trim() || 'available') as BlockPlacement,
          is_required: Boolean(block?.is_required),
          sort_order: Number(block?.sort_order ?? index) || index,
        }))
      : [],
    fields: Array.isArray(template?.fields)
      ? template.fields.map((field, index) => ({
          id: Number(field?.id) > 0 ? Number(field?.id) : undefined,
          key: String(field?.key ?? '').trim() || undefined,
          label: String(field?.label ?? '').trim(),
          field_type: (String(field?.field_type ?? '').trim() || 'text') as FieldType,
          placement: (String(field?.placement ?? '').trim() || 'header') as FieldPlacement,
          is_required: Boolean(field?.is_required),
          options: Array.isArray(field?.options)
            ? field.options.map((option) => String(option ?? '').trim()).filter(Boolean)
            : [],
          sort_order: Number(field?.sort_order ?? index) || index,
        }))
      : [],
  })

  const customTemplates = (value: BackendComun | null) =>
    Array.isArray(value?.custom_templates)
      ? value.custom_templates.map((template) => normalizeTemplate(template))
      : []

  const blockOptions = () =>
    Array.isArray(comun?.options?.custom_template_editor?.block_options)
      ? comun?.options?.custom_template_editor?.block_options?.length
        ? comun?.options?.custom_template_editor?.block_options ?? fallbackBlockOptions
        : fallbackBlockOptions
      : fallbackBlockOptions

  const blockPlacementOptions = () =>
    Array.isArray(comun?.options?.custom_template_editor?.block_placement_options)
      ? comun?.options?.custom_template_editor?.block_placement_options ?? []
      : fallbackBlockPlacementOptions

  const fieldTypeOptions = () =>
    Array.isArray(comun?.options?.custom_template_editor?.field_type_options)
      ? comun?.options?.custom_template_editor?.field_type_options ?? []
      : fallbackFieldTypeOptions

  const fieldPlacementOptions = () =>
    Array.isArray(comun?.options?.custom_template_editor?.field_placement_options)
      ? comun?.options?.custom_template_editor?.field_placement_options ?? []
      : fallbackFieldPlacementOptions

  const backToSettings = () => goto(`/comuns/${encodeURIComponent(slug)}/settings`)

  const refreshEditor = async () => {
    if (!browser || !slug) return
    if (!$siteToken) {
      loading = false
      errorMessage = 'Нужна авторизация'
      return
    }
    loading = true
    errorMessage = ''
    try {
      const comunUrl = new URL(buildComunUrl(slug), window.location.origin)
      comunUrl.searchParams.set('_', String(Date.now()))
      const response = await fetch(comunUrl.toString(), {
        headers: { Authorization: `Bearer ${$siteToken}` },
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить шаблон')
      }
      if (!payload?.comun?.can_manage_moderators) {
        throw new Error('Редактор шаблонов доступен только владельцу сообщества')
      }
      comun = payload.comun
      if (isNewTemplate) {
        draft = normalizeTemplate({
          name: '',
          blocks: [],
          fields: [],
        })
      } else {
        const existingTemplate =
          customTemplates(payload.comun).find((template) => template.slug === templateRef) ??
          customTemplates(payload.comun).find((template) => String(template.id ?? '') === templateRef) ??
          null
        if (!existingTemplate) {
          throw new Error('Шаблон не найден')
        }
        draft = normalizeTemplate(existingTemplate)
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка загрузки'
      draft = null
    } finally {
      loading = false
    }
  }

  onMount(() => {
    void refreshEditor()
  })

  const setDraft = (patch: Partial<BackendComunCustomTemplate>) => {
    if (!draft) return
    draft = { ...draft, ...patch }
  }

  const blocksByPlacement = (placement: BlockPlacement) =>
    (draft?.blocks ?? []).filter((block) => block.placement === placement)

  const fieldsByPlacement = (placement: FieldPlacement) =>
    (draft?.fields ?? []).filter((field) => field.placement === placement)

  const usedBlockTypes = () => new Set((draft?.blocks ?? []).map((block) => block.block_type))

  const availableBlockOptionsForAdd = (placement: BlockPlacement) => {
    const used = usedBlockTypes()
    return blockOptions().filter((option) => {
      if (!used.has(option.value)) return true
      return blocksByPlacement(placement).some((block) => block.block_type === option.value)
    })
  }

  $: headerBlocks = blocksByPlacement('header')
  $: bodyBlocks = blocksByPlacement('available')
  $: footerBlocks = blocksByPlacement('footer')
  $: headerFields = fieldsByPlacement('header')
  $: footerFields = fieldsByPlacement('footer')
  $: headerBlockOptionsToAdd = availableBlockOptionsForAdd('header').filter(
    (option) => !headerBlocks.some((block) => block.block_type === option.value)
  )
  $: bodyBlockOptionsToAdd = availableBlockOptionsForAdd('available').filter(
    (option) => !bodyBlocks.some((block) => block.block_type === option.value)
  )
  $: footerBlockOptionsToAdd = availableBlockOptionsForAdd('footer').filter(
    (option) => !footerBlocks.some((block) => block.block_type === option.value)
  )

  const addBlock = (placement: BlockPlacement, blockType: string) => {
    if (!draft || !blockType) return
    const existingIndex = (draft.blocks ?? []).findIndex((block) => block.block_type === blockType)
    const nextBlocks = [...(draft.blocks ?? [])]
    if (existingIndex >= 0) {
      nextBlocks[existingIndex] = {
        ...nextBlocks[existingIndex],
        placement,
      }
    } else {
      nextBlocks.push({
        block_type: blockType,
        placement,
        is_required: false,
        sort_order: nextBlocks.length,
      })
    }
    setDraft({ blocks: nextBlocks })
  }

  const updateBlock = (blockType: string, patch: { placement?: BlockPlacement; is_required?: boolean }) => {
    if (!draft) return
    const nextBlocks = [...(draft.blocks ?? [])]
    const index = nextBlocks.findIndex((block) => block.block_type === blockType)
    if (index < 0) return
    nextBlocks[index] = { ...nextBlocks[index], ...patch }
    setDraft({ blocks: nextBlocks })
  }

  const updateBlockPlacementFromValue = (blockType: string, value: string, fallback: BlockPlacement) => {
    updateBlock(blockType, {
      placement: (value || fallback) as BlockPlacement,
    })
  }

  const removeBlock = (blockType: string) => {
    if (!draft) return
    setDraft({ blocks: (draft.blocks ?? []).filter((block) => block.block_type !== blockType) })
  }

  const addField = (placement: FieldPlacement) => {
    if (!draft) return
    setDraft({
      fields: [
        ...(draft.fields ?? []),
        {
          label: '',
          field_type: 'text',
          placement,
          is_required: false,
          options: [],
          sort_order: (draft.fields ?? []).length,
        },
      ],
    })
  }

  const addFieldOfType = (placement: FieldPlacement, fieldType: FieldType) => {
    if (!draft) return
    const nextIndex = (draft.fields ?? []).length + 1
    const defaultLabels: Record<FieldType, string> = {
      text: 'Текстовое поле',
      file: 'Файл',
      select: 'Выпадающий список',
      checkbox: 'Чекбокс',
    }
    setDraft({
      fields: [
        ...(draft.fields ?? []),
        {
          label: defaultLabels[fieldType] || `Поле ${nextIndex}`,
          field_type: fieldType,
          placement,
          is_required: false,
          options: fieldType === 'select' ? ['Вариант 1', 'Вариант 2'] : [],
          sort_order: nextIndex - 1,
        },
      ],
    })
  }

  const updateField = (
    fieldIndex: number,
    patch: Partial<NonNullable<BackendComunCustomTemplate['fields']>[number]>
  ) => {
    if (!draft) return
    const nextFields = [...(draft.fields ?? [])]
    if (!nextFields[fieldIndex]) return
    nextFields[fieldIndex] = { ...nextFields[fieldIndex], ...patch }
    if (nextFields[fieldIndex].field_type !== 'select') {
      nextFields[fieldIndex] = { ...nextFields[fieldIndex], options: [] }
    }
    setDraft({ fields: nextFields })
  }

  const updateFieldTypeFromValue = (fieldIndex: number, value: string) => {
    updateField(fieldIndex, { field_type: (value || 'text') as FieldType })
  }

  const updateFieldPlacementFromValue = (
    fieldIndex: number,
    value: string,
    fallback: FieldPlacement
  ) => {
    updateField(fieldIndex, { placement: (value || fallback) as FieldPlacement })
  }

  const removeField = (fieldIndex: number) => {
    if (!draft) return
    setDraft({ fields: (draft.fields ?? []).filter((_, index) => index !== fieldIndex) })
  }

  const fieldOptionsText = (field?: NonNullable<BackendComunCustomTemplate['fields']>[number]) =>
    (field?.options ?? []).join('\n')

  const openTemplatePreview = async () => {
    if (!browser || !slug || !draft) return
    localStorage.setItem(
      `comuna:custom-template-preview:${slug}`,
      JSON.stringify({
        saved_at: Date.now(),
        template: normalizeTemplate(draft),
      })
    )
    await goto(`/comuns/${encodeURIComponent(slug)}/new-post?template_preview=1`)
  }

  const readPaletteItem = (event: DragEvent): DragPaletteItem | null => {
    const raw =
      event.dataTransfer?.getData(DRAG_TYPE) || event.dataTransfer?.getData('text/plain') || ''
    if (!raw) return null
    try {
      const payload = JSON.parse(raw)
      if (payload?.kind === 'block' && typeof payload?.blockType === 'string') {
        return { kind: 'block', blockType: payload.blockType }
      }
      if (payload?.kind === 'field' && typeof payload?.fieldType === 'string') {
        return { kind: 'field', fieldType: payload.fieldType as PaletteFieldType }
      }
    } catch {
      return null
    }
    return null
  }

  const handleDropZoneEnter = (zone: 'header' | 'available' | 'footer') => {
    activeDropZone = zone
  }

  const applyPaletteItemToZone = (
    zone: 'header' | 'available' | 'footer',
    item: DragPaletteItem | null
  ) => {
    if (!item) return
    if (item.kind === 'block') {
      addBlock(zone as BlockPlacement, item.blockType)
      return
    }
    if (zone === 'available') return
    addFieldOfType(zone as FieldPlacement, item.fieldType)
  }

  const handlePaletteDrop = (event: DragEvent, zone: 'header' | 'available' | 'footer') => {
    applyPaletteItemToZone(zone, readPaletteItem(event))
    activeDropZone = null
  }

  const normalizedDraftForSave = () => {
    const currentDraft = normalizeTemplate(draft)
    return {
      id: currentDraft.id ?? null,
      name: currentDraft.name.trim(),
      blocks: (currentDraft.blocks ?? []).map((block, index) => ({
        block_type: String(block.block_type ?? '').trim(),
        placement: block.placement,
        is_required: Boolean(block.is_required),
        sort_order: index,
      })),
      fields: (currentDraft.fields ?? []).map((field, index) => ({
        key: String(field.key ?? '').trim(),
        label: String(field.label ?? '').trim(),
        field_type: field.field_type,
        placement: field.placement,
        is_required: Boolean(field.is_required),
        options: (field.options ?? []).map((option) => String(option ?? '').trim()).filter(Boolean),
        sort_order: index,
      })),
    }
  }

  const saveTemplate = async () => {
    if (!draft || !slug || !comun || !$siteToken) return
    if (!draft.name?.trim()) {
      errorMessage = 'Название шаблона обязательно'
      return
    }
    saving = true
    errorMessage = ''
    try {
      const templates = customTemplates(comun)
      const nextTemplate = normalizedDraftForSave()
      const nextTemplates = isNewTemplate
        ? [...templates, nextTemplate]
        : templates.map((template) =>
            template.id === draft.id || template.slug === draft.slug ? nextTemplate : normalizedDraftForSaveFromTemplate(template)
          )
      const response = await fetch(buildComunUrl(slug), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${$siteToken}`,
        },
        body: JSON.stringify({ custom_templates: nextTemplates }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить шаблон')
      }
      comun = payload.comun ?? comun
      const refreshedTemplate = isNewTemplate
        ? customTemplates(comun).at(-1) ?? null
        : customTemplates(comun).find((template) => template.id === draft.id || template.slug === draft.slug) ?? null
      toast({ content: 'Шаблон сохранен', type: 'success' })
      if (refreshedTemplate?.slug) {
        await goto(buildComunCustomTemplateEditorPath(slug, refreshedTemplate.slug))
        return
      }
      await goto(`/comuns/${encodeURIComponent(slug)}/settings`)
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      saving = false
    }
  }

  const normalizedDraftForSaveFromTemplate = (template: BackendComunCustomTemplate) => ({
    id: template.id ?? null,
    name: String(template.name ?? '').trim(),
    blocks: (template.blocks ?? []).map((block, index) => ({
      block_type: String(block.block_type ?? '').trim(),
      placement: (block.placement ?? 'available') as BlockPlacement,
      is_required: Boolean(block.is_required),
      sort_order: index,
    })),
    fields: (template.fields ?? []).map((field, index) => ({
      key: String(field.key ?? '').trim(),
      label: String(field.label ?? '').trim(),
      field_type: (field.field_type ?? 'text') as FieldType,
      placement: (field.placement ?? 'header') as FieldPlacement,
      is_required: Boolean(field.is_required),
      options: (field.options ?? []).map((option) => String(option ?? '').trim()).filter(Boolean),
      sort_order: index,
    })),
  })

  const deleteTemplate = async () => {
    if (isNewTemplate || !draft || !slug || !comun || !$siteToken) return
    deleting = true
    errorMessage = ''
    try {
      const nextTemplates = customTemplates(comun)
        .filter((template) => template.id !== draft.id && template.slug !== draft.slug)
        .map((template) => normalizedDraftForSaveFromTemplate(template))
      const response = await fetch(buildComunUrl(slug), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${$siteToken}`,
        },
        body: JSON.stringify({ custom_templates: nextTemplates }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось удалить шаблон')
      }
      toast({ content: 'Шаблон удален', type: 'success' })
      await backToSettings()
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Ошибка удаления'
    } finally {
      deleting = false
    }
  }

  const headerSectionClass =
    'rounded-[28px] border border-amber-200 bg-[linear-gradient(180deg,rgba(255,248,232,0.98),rgba(255,243,214,0.92))] dark:border-amber-900/40 dark:bg-[linear-gradient(180deg,rgba(69,46,20,0.58),rgba(45,32,15,0.4))]'
  const bodySectionClass =
    'rounded-[28px] border border-sky-200 bg-[linear-gradient(180deg,rgba(240,249,255,0.98),rgba(225,243,255,0.92))] dark:border-sky-900/40 dark:bg-[linear-gradient(180deg,rgba(16,54,78,0.56),rgba(14,37,54,0.38))]'
  const footerSectionClass =
    'rounded-[28px] border border-emerald-200 bg-[linear-gradient(180deg,rgba(238,253,247,0.98),rgba(222,248,236,0.92))] dark:border-emerald-900/40 dark:bg-[linear-gradient(180deg,rgba(19,63,49,0.58),rgba(15,40,32,0.38))]'
</script>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <Button color="ghost" on:click={backToSettings}>Назад к настройкам</Button>
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      {comun?.name ? `Сообщество: ${comun.name}` : ''}
    </div>
  </div>

  {#if loading}
    <div class="rounded-3xl border border-slate-200 px-4 py-8 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
      Загружаем редактор шаблона…
    </div>
  {:else if errorMessage && !draft}
    <div class="rounded-3xl border border-rose-200 bg-rose-50 px-4 py-6 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300">
      {errorMessage}
    </div>
  {:else if draft}
    <section class="flex w-full min-w-0 flex-col gap-4">
        <div class="rounded-[28px] border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/70">
          <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">Шаблон</div>
          <input
            value={draft.name ?? ''}
            on:input={(event) => setDraft({ name: event.currentTarget?.value ?? '' })}
            placeholder="Название шаблона"
            class="mt-3 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-base dark:border-zinc-700 dark:bg-zinc-900"
          />
        </div>

        <section
          role="group"
          class={`px-5 py-5 transition-shadow ${headerSectionClass} ${activeDropZone === 'header' ? 'ring-2 ring-amber-400 ring-offset-2 dark:ring-offset-zinc-950' : ''}`}
          on:dragover|preventDefault
          on:dragenter={() => handleDropZoneEnter('header')}
          on:dragleave={() => activeDropZone === 'header' && (activeDropZone = null)}
          on:drop|preventDefault={(event) => handlePaletteDrop(event, 'header')}
        >
          <div class="mb-4">
            <div class="text-xs uppercase tracking-[0.2em] text-amber-700 dark:text-amber-200">Header</div>
            <div class="mt-1 text-sm text-slate-700 dark:text-zinc-200">
              Перетащите сюда поля или блоки, которые должны закрепляться над основным текстом.
            </div>
          </div>

          <div class="grid gap-3">
            <div class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-zinc-800/70 dark:bg-zinc-950/35">
              <div class="mb-3 flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Блоки Header</div>
                <div class="lg:hidden flex flex-wrap gap-2">
                  <select bind:value={headerBlockToAdd} class="min-w-[220px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
                    <option value="">Добавить блок в Header</option>
                    {#each headerBlockOptionsToAdd as option}
                      <option value={option.value}>{option.label}</option>
                    {/each}
                  </select>
                  <Button
                    size="sm"
                    on:click={() => {
                      addBlock('header', headerBlockToAdd)
                      headerBlockToAdd = ''
                    }}
                    disabled={!headerBlockToAdd}
                  >
                    Добавить
                  </Button>
                </div>
              </div>
              <div class="mt-3 flex flex-col gap-2">
                {#if headerBlocks.length}
                  {#each headerBlocks as block}
                    <div class="grid gap-2 rounded-2xl border border-amber-200/70 bg-amber-50/70 px-3 py-3 md:grid-cols-[minmax(0,1fr)_160px_140px_auto] md:items-center dark:border-amber-900/40 dark:bg-amber-950/10">
                      <div class="font-medium text-slate-900 dark:text-zinc-100">
                        {blockOptions().find((item) => item.value === block.block_type)?.label ?? block.block_type}
                      </div>
                      <select
                        class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                        value={block.placement}
                        on:change={(event) =>
                          updateBlockPlacementFromValue(
                            block.block_type,
                            event.currentTarget?.value ?? 'header',
                            'header'
                          )}
                      >
                        {#each blockPlacementOptions() as option}
                          <option value={option.value}>{option.label}</option>
                        {/each}
                      </select>
                      <label class="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={Boolean(block.is_required)}
                          on:change={(event) =>
                            updateBlock(block.block_type, { is_required: Boolean(event.currentTarget?.checked) })}
                        />
                        <span>Обязательный</span>
                      </label>
                      <Button color="ghost" size="sm" on:click={() => removeBlock(block.block_type)}>Убрать</Button>
                    </div>
                  {/each}
                {:else}
                  <div class="rounded-2xl border border-dashed border-amber-300/70 px-3 py-3 text-sm text-slate-600 dark:border-amber-900/40 dark:text-zinc-300">
                    Header-блоков пока нет
                  </div>
                {/if}
              </div>
            </div>

            <div class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-zinc-800/70 dark:bg-zinc-950/35">
              <div class="mb-3 flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Поля Header</div>
                <Button class="lg:hidden" size="sm" on:click={() => addField('header')}>Добавить поле</Button>
              </div>
              <div class="flex flex-col gap-3">
                {#if headerFields.length}
                  {#each draft.fields ?? [] as field, fieldIndex}
                    {#if field.placement === 'header'}
                      <div class="rounded-2xl border border-amber-200/70 bg-amber-50/70 px-3 py-3 dark:border-amber-900/40 dark:bg-amber-950/10">
                        <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_160px_auto] md:items-center">
                          <input
                            value={field.label ?? ''}
                            on:input={(event) => updateField(fieldIndex, { label: event.currentTarget?.value ?? '' })}
                            placeholder="Название поля"
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                          />
                          <select
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            value={field.field_type ?? 'text'}
                            on:change={(event) => updateFieldTypeFromValue(fieldIndex, event.currentTarget?.value ?? 'text')}
                          >
                            {#each fieldTypeOptions() as option}
                              <option value={option.value}>{option.label}</option>
                            {/each}
                          </select>
                          <select
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            value={field.placement ?? 'header'}
                            on:change={(event) => updateFieldPlacementFromValue(fieldIndex, event.currentTarget?.value ?? 'header', 'header')}
                          >
                            {#each fieldPlacementOptions() as option}
                              <option value={option.value}>{option.label}</option>
                            {/each}
                          </select>
                          <Button color="ghost" size="sm" on:click={() => removeField(fieldIndex)}>Убрать</Button>
                        </div>
                        <div class="mt-3">
                          <label class="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={Boolean(field.is_required)}
                              on:change={(event) => updateField(fieldIndex, { is_required: Boolean(event.currentTarget?.checked) })}
                            />
                            <span>Обязательное поле</span>
                          </label>
                        </div>
                        {#if field.field_type === 'select'}
                          <textarea
                            rows="4"
                            class="mt-3 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            placeholder="Каждый вариант с новой строки"
                            value={fieldOptionsText(field)}
                            on:input={(event) =>
                              updateField(fieldIndex, {
                                options: (event.currentTarget?.value ?? '')
                                  .split('\n')
                                  .map((item) => item.trim())
                                  .filter(Boolean),
                              })}
                          ></textarea>
                        {/if}
                      </div>
                    {/if}
                  {/each}
                {:else}
                  <div class="rounded-2xl border border-dashed border-amber-300/70 px-3 py-3 text-sm text-slate-600 dark:border-amber-900/40 dark:text-zinc-300">
                    Header-полей пока нет
                  </div>
                {/if}
              </div>
            </div>
          </div>
        </section>

        <section
          role="group"
          class={`px-5 py-5 transition-shadow ${bodySectionClass} ${activeDropZone === 'available' ? 'ring-2 ring-sky-400 ring-offset-2 dark:ring-offset-zinc-950' : ''}`}
          on:dragover|preventDefault
          on:dragenter={() => handleDropZoneEnter('available')}
          on:dragleave={() => activeDropZone === 'available' && (activeDropZone = null)}
          on:drop|preventDefault={(event) => handlePaletteDrop(event, 'available')}
        >
          <div class="mb-4">
            <div class="text-xs uppercase tracking-[0.2em] text-sky-700 dark:text-sky-200">Текстовый блок</div>
            <div class="mt-1 text-sm text-slate-700 dark:text-zinc-200">
              Перетащите сюда блоки, которые автор сможет использовать внутри основного текста.
            </div>
          </div>

          <div class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-zinc-800/70 dark:bg-zinc-950/35">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Блоки текстового блока</div>
              <div class="lg:hidden flex flex-wrap gap-2">
                <select bind:value={textBlockToAdd} class="min-w-[220px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
                  <option value="">Добавить блок в текст</option>
                  {#each bodyBlockOptionsToAdd as option}
                    <option value={option.value}>{option.label}</option>
                  {/each}
                </select>
                <Button
                  size="sm"
                  on:click={() => {
                    addBlock('available', textBlockToAdd)
                    textBlockToAdd = ''
                  }}
                  disabled={!textBlockToAdd}
                >
                  Добавить
                </Button>
              </div>
            </div>

            <div class="flex flex-col gap-2">
              {#if bodyBlocks.length}
                {#each bodyBlocks as block}
                  <div class="grid gap-2 rounded-2xl border border-sky-200/70 bg-sky-50/70 px-3 py-3 md:grid-cols-[minmax(0,1fr)_160px_140px_auto] md:items-center dark:border-sky-900/40 dark:bg-sky-950/10">
                    <div class="font-medium text-slate-900 dark:text-zinc-100">
                      {blockOptions().find((item) => item.value === block.block_type)?.label ?? block.block_type}
                    </div>
                    <select
                      class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                      value={block.placement}
                      on:change={(event) =>
                        updateBlockPlacementFromValue(
                          block.block_type,
                          event.currentTarget?.value ?? 'available',
                          'available'
                        )}
                    >
                      {#each blockPlacementOptions() as option}
                        <option value={option.value}>{option.label}</option>
                      {/each}
                    </select>
                    <label class="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={Boolean(block.is_required)}
                        on:change={(event) =>
                          updateBlock(block.block_type, { is_required: Boolean(event.currentTarget?.checked) })}
                      />
                      <span>Обязательный</span>
                    </label>
                    <Button color="ghost" size="sm" on:click={() => removeBlock(block.block_type)}>Убрать</Button>
                  </div>
                {/each}
              {:else}
                <div class="rounded-2xl border border-dashed border-sky-300/70 px-3 py-3 text-sm text-slate-600 dark:border-sky-900/40 dark:text-zinc-300">
                  Текстовых блоков пока нет
                </div>
              {/if}
            </div>
          </div>
        </section>

        <section
          role="group"
          class={`px-5 py-5 transition-shadow ${footerSectionClass} ${activeDropZone === 'footer' ? 'ring-2 ring-emerald-400 ring-offset-2 dark:ring-offset-zinc-950' : ''}`}
          on:dragover|preventDefault
          on:dragenter={() => handleDropZoneEnter('footer')}
          on:dragleave={() => activeDropZone === 'footer' && (activeDropZone = null)}
          on:drop|preventDefault={(event) => handlePaletteDrop(event, 'footer')}
        >
          <div class="mb-4">
            <div class="text-xs uppercase tracking-[0.2em] text-emerald-700 dark:text-emerald-200">Footer</div>
            <div class="mt-1 text-sm text-slate-700 dark:text-zinc-200">
              Перетащите сюда поля и блоки, которые должны идти после основного текста.
            </div>
          </div>

          <div class="grid gap-3">
            <div class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-zinc-800/70 dark:bg-zinc-950/35">
              <div class="mb-3 flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Блоки Footer</div>
                <div class="lg:hidden flex flex-wrap gap-2">
                  <select bind:value={footerBlockToAdd} class="min-w-[220px] rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900">
                    <option value="">Добавить блок в Footer</option>
                    {#each footerBlockOptionsToAdd as option}
                      <option value={option.value}>{option.label}</option>
                    {/each}
                  </select>
                  <Button
                    size="sm"
                    on:click={() => {
                      addBlock('footer', footerBlockToAdd)
                      footerBlockToAdd = ''
                    }}
                    disabled={!footerBlockToAdd}
                  >
                    Добавить
                  </Button>
                </div>
              </div>
              <div class="flex flex-col gap-2">
                {#if footerBlocks.length}
                  {#each footerBlocks as block}
                    <div class="grid gap-2 rounded-2xl border border-emerald-200/70 bg-emerald-50/70 px-3 py-3 md:grid-cols-[minmax(0,1fr)_160px_140px_auto] md:items-center dark:border-emerald-900/40 dark:bg-emerald-950/10">
                      <div class="font-medium text-slate-900 dark:text-zinc-100">
                        {blockOptions().find((item) => item.value === block.block_type)?.label ?? block.block_type}
                      </div>
                      <select
                        class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                        value={block.placement}
                        on:change={(event) =>
                          updateBlockPlacementFromValue(
                            block.block_type,
                            event.currentTarget?.value ?? 'footer',
                            'footer'
                          )}
                      >
                        {#each blockPlacementOptions() as option}
                          <option value={option.value}>{option.label}</option>
                        {/each}
                      </select>
                      <label class="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={Boolean(block.is_required)}
                          on:change={(event) =>
                            updateBlock(block.block_type, { is_required: Boolean(event.currentTarget?.checked) })}
                        />
                        <span>Обязательный</span>
                      </label>
                      <Button color="ghost" size="sm" on:click={() => removeBlock(block.block_type)}>Убрать</Button>
                    </div>
                  {/each}
                {:else}
                  <div class="rounded-2xl border border-dashed border-emerald-300/70 px-3 py-3 text-sm text-slate-600 dark:border-emerald-900/40 dark:text-zinc-300">
                    Footer-блоков пока нет
                  </div>
                {/if}
              </div>
            </div>

            <div class="rounded-2xl border border-white/70 bg-white/80 px-4 py-4 dark:border-zinc-800/70 dark:bg-zinc-950/35">
              <div class="mb-3 flex items-center justify-between gap-3">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Поля Footer</div>
                <Button class="lg:hidden" size="sm" on:click={() => addField('footer')}>Добавить поле</Button>
              </div>
              <div class="flex flex-col gap-3">
                {#if footerFields.length}
                  {#each draft.fields ?? [] as field, fieldIndex}
                    {#if field.placement === 'footer'}
                      <div class="rounded-2xl border border-emerald-200/70 bg-emerald-50/70 px-3 py-3 dark:border-emerald-900/40 dark:bg-emerald-950/10">
                        <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_160px_160px_auto] md:items-center">
                          <input
                            value={field.label ?? ''}
                            on:input={(event) => updateField(fieldIndex, { label: event.currentTarget?.value ?? '' })}
                            placeholder="Название поля"
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                          />
                          <select
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            value={field.field_type ?? 'text'}
                            on:change={(event) => updateFieldTypeFromValue(fieldIndex, event.currentTarget?.value ?? 'text')}
                          >
                            {#each fieldTypeOptions() as option}
                              <option value={option.value}>{option.label}</option>
                            {/each}
                          </select>
                          <select
                            class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            value={field.placement ?? 'footer'}
                            on:change={(event) => updateFieldPlacementFromValue(fieldIndex, event.currentTarget?.value ?? 'footer', 'footer')}
                          >
                            {#each fieldPlacementOptions() as option}
                              <option value={option.value}>{option.label}</option>
                            {/each}
                          </select>
                          <Button color="ghost" size="sm" on:click={() => removeField(fieldIndex)}>Убрать</Button>
                        </div>
                        <div class="mt-3">
                          <label class="flex items-center gap-2 text-sm">
                            <input
                              type="checkbox"
                              checked={Boolean(field.is_required)}
                              on:change={(event) => updateField(fieldIndex, { is_required: Boolean(event.currentTarget?.checked) })}
                            />
                            <span>Обязательное поле</span>
                          </label>
                        </div>
                        {#if field.field_type === 'select'}
                          <textarea
                            rows="4"
                            class="mt-3 w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm dark:border-zinc-700 dark:bg-zinc-900"
                            placeholder="Каждый вариант с новой строки"
                            value={fieldOptionsText(field)}
                            on:input={(event) =>
                              updateField(fieldIndex, {
                                options: (event.currentTarget?.value ?? '')
                                  .split('\n')
                                  .map((item) => item.trim())
                                  .filter(Boolean),
                              })}
                          ></textarea>
                        {/if}
                      </div>
                    {/if}
                  {/each}
                {:else}
                  <div class="rounded-2xl border border-dashed border-emerald-300/70 px-3 py-3 text-sm text-slate-600 dark:border-emerald-900/40 dark:text-zinc-300">
                    Footer-полей пока нет
                  </div>
                {/if}
              </div>
            </div>
          </div>
        </section>
        <section class="rounded-[28px] border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/70">
          <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">Действия</div>
          {#if errorMessage}
            <div class="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-700 dark:border-rose-900/40 dark:bg-rose-950/20 dark:text-rose-300">
              {errorMessage}
            </div>
          {/if}
          <div class="mt-4 flex flex-wrap gap-3">
            <Button on:click={saveTemplate} disabled={saving || deleting}>
              {saving ? 'Сохраняем...' : 'Сохранить шаблон'}
            </Button>
            <Button color="ghost" on:click={openTemplatePreview} disabled={saving || deleting}>
              Предпросмотр
            </Button>
            {#if !isNewTemplate}
              <Button color="ghost" on:click={deleteTemplate} disabled={saving || deleting}>
                {deleting ? 'Удаляем...' : 'Удалить шаблон'}
              </Button>
            {/if}
            <Button color="ghost" on:click={backToSettings} disabled={saving || deleting}>
              Вернуться в настройки
            </Button>
          </div>
        </section>
    </section>
  {/if}
</div>
