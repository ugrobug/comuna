<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { buildBugReportStatusUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import {
    BUG_REPORT_STATUS_OPTIONS,
    bugReportBrowserLabels,
    bugReportPlatformLabels,
    bugReportStatusLabel,
    bugReportStatusTone,
    normalizeBugReportTemplateData,
    type BugReportTemplate,
    type BugReportStatus,
  } from '$lib/postTemplates'

  export let template: BugReportTemplate
  export let fallbackTitle = ''
  export let compact = false
  export let canManageStatus = false
  export let postId: number | null = null

  const dispatch = createEventDispatcher<{
    statuschange: { status: BugReportStatus; template: BugReportTemplate }
  }>()

  let selectedStatus: BugReportStatus = 'review'
  let lastTemplateStatus: BugReportStatus = 'review'
  let statusSaving = false
  let statusError = ''

  $: data = template.data
  $: normalizedTemplateStatus = normalizeBugReportTemplateData(data).status ?? 'review'
  $: if (!statusSaving && normalizedTemplateStatus !== lastTemplateStatus) {
    lastTemplateStatus = normalizedTemplateStatus
    selectedStatus = normalizedTemplateStatus
  }
  $: statusTone = bugReportStatusTone(selectedStatus)
  $: platformLabels = bugReportPlatformLabels(data.platforms)
  $: browserLabels = bugReportBrowserLabels(data.browsers)
  $: metaParts = [
    platformLabels.length ? `Платформа: ${platformLabels.join(', ')}` : '',
    browserLabels.length ? `Браузер: ${browserLabels.join(', ')}` : '',
  ].filter(Boolean)

  const updateStatus = async (event: Event) => {
    const nextStatus = (event.currentTarget as HTMLSelectElement).value as BugReportStatus
    selectedStatus = nextStatus
    statusError = ''
    if (!postId || !canManageStatus || !$siteToken) return
    statusSaving = true
    try {
      const response = await fetch(buildBugReportStatusUrl(postId), {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ status: nextStatus }),
      })
      const payload = await response.json().catch(() => null)
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || 'status update failed')
      }
      const updatedTemplate = (payload.template ?? {
        ...template,
        data: { ...template.data, status: nextStatus },
      }) as BugReportTemplate
      lastTemplateStatus = nextStatus
      dispatch('statuschange', { status: nextStatus, template: updatedTemplate })
    } catch (error) {
      console.error('Failed to update bug report status:', error)
      selectedStatus = normalizeBugReportTemplateData(template.data).status ?? 'review'
      statusError = 'Не удалось обновить статус'
    } finally {
      statusSaving = false
    }
  }
</script>

<section class:bug-report-card={true} class:is-compact={compact}>
  <div class="bug-report-card__surface">
    {#if fallbackTitle}
      <h2 class="bug-report-card__title">{fallbackTitle}</h2>
    {/if}

    <div class="bug-report-card__meta-line">
      {#if canManageStatus}
        <label class={`bug-report-card__status-control tone-${statusTone}`}>
          <select
            value={selectedStatus}
            disabled={statusSaving}
            on:change={updateStatus}
            aria-label="Статус баг-репорта"
          >
            {#each BUG_REPORT_STATUS_OPTIONS as option}
              <option value={option.value}>{option.label}</option>
            {/each}
          </select>
        </label>
      {:else}
        <div class={`bug-report-card__status tone-${statusTone}`}>{bugReportStatusLabel(selectedStatus)}</div>
      {/if}

      {#each metaParts as part}
        <span class="bug-report-card__meta-part">{part}</span>
      {/each}
    </div>

    {#if statusError}
      <div class="bug-report-card__status-error">{statusError}</div>
    {/if}

    {#if !compact}
      {#if data.error_code}
        <div class="bug-report-card__code-wrap">
          <div class="bug-report-card__meta-label">Код ошибки</div>
          <pre class="bug-report-card__code"><code>{data.error_code}</code></pre>
        </div>
      {/if}

      {#if data.screenshot_url}
        <div class="bug-report-card__image-wrap">
          <img src={data.screenshot_url} alt="Скриншот бага" class="bug-report-card__image" />
        </div>
      {/if}
    {/if}
  </div>
</section>

<style>
  .bug-report-card {
    width: 100%;
  }

  .bug-report-card__surface {
    color: #111827;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .bug-report-card.is-compact .bug-report-card__surface {
    gap: 0.55rem;
  }

  .bug-report-card__title {
    margin: 0;
    color: #111827;
    font-size: clamp(1.35rem, 2vw, 1.9rem);
    font-weight: 800;
    line-height: 1.18;
    letter-spacing: -0.03em;
  }

  .bug-report-card.is-compact .bug-report-card__title {
    font-size: 1.2rem;
  }

  .bug-report-card__meta-line {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    flex-wrap: wrap;
    gap: 0.55rem;
    color: #4b5563;
    font-size: 0.92rem;
    line-height: 1.35;
  }

  .bug-report-card__meta-part {
    display: inline-flex;
    align-items: center;
    color: #4b5563;
  }

  .bug-report-card__meta-part::before {
    content: '';
    width: 0.25rem;
    height: 0.25rem;
    margin-right: 0.55rem;
    border-radius: 999px;
    background: #c7a65b;
  }

  .bug-report-card__status,
  .bug-report-card__status-control {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.01em;
    border: 1px solid rgba(17, 24, 39, 0.08);
  }

  .bug-report-card__status-control select {
    appearance: none;
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    letter-spacing: inherit;
    outline: none;
    cursor: pointer;
  }

  .bug-report-card__status-control select:disabled {
    cursor: wait;
    opacity: 0.7;
  }

  .bug-report-card__status.tone-amber,
  .bug-report-card__status-control.tone-amber {
    background: rgba(245, 158, 11, 0.16);
    color: #92400e;
  }

  .bug-report-card__status.tone-blue,
  .bug-report-card__status-control.tone-blue {
    background: rgba(59, 130, 246, 0.16);
    color: #1d4ed8;
  }

  .bug-report-card__status.tone-green,
  .bug-report-card__status-control.tone-green {
    background: rgba(34, 197, 94, 0.16);
    color: #15803d;
  }

  .bug-report-card__status.tone-red,
  .bug-report-card__status-control.tone-red {
    background: rgba(239, 68, 68, 0.16);
    color: #b91c1c;
  }

  .bug-report-card__status-error {
    color: #b91c1c;
    font-size: 0.82rem;
  }

  .bug-report-card__meta-label {
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #6b7280;
  }

  .bug-report-card__code-wrap,
  .bug-report-card__image-wrap {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .bug-report-card__code {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
    border-radius: 14px;
    border: 1px solid rgba(17, 24, 39, 0.1);
    background: #f8fafc;
    color: #374151;
    padding: 0.95rem 1rem;
    font-size: 0.86rem;
    line-height: 1.45;
    overflow-x: auto;
  }

  .bug-report-card__image {
    width: 100%;
    display: block;
    border-radius: 14px;
    border: 1px solid rgba(17, 24, 39, 0.1);
    object-fit: cover;
    max-height: 24rem;
    background: #f8fafc;
  }

  @media (max-width: 640px) {
    .bug-report-card__meta-line {
      gap: 0.45rem;
    }
  }
</style>
