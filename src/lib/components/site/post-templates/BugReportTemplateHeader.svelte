<script lang="ts">
  import {
    bugReportBrowserLabels,
    bugReportPlatformLabels,
    bugReportStatusLabel,
    bugReportStatusTone,
    type BugReportTemplate,
  } from '$lib/postTemplates'

  export let template: BugReportTemplate
  export let compact = false

  $: data = template.data
  $: statusTone = bugReportStatusTone(data.status)
  $: platformLabels = bugReportPlatformLabels(data.platforms)
  $: browserLabels = bugReportBrowserLabels(data.browsers)
  $: hasMeta = platformLabels.length > 0 || browserLabels.length > 0
</script>

<section class:bug-report-card={true} class:is-compact={compact}>
  <div class="bug-report-card__surface">
    <div class="bug-report-card__topline">
      <div class={`bug-report-card__status tone-${statusTone}`}>{bugReportStatusLabel(data.status)}</div>
    </div>

    {#if hasMeta}
      <div class="bug-report-card__meta">
        {#if platformLabels.length}
          <div class="bug-report-card__meta-group">
            <div class="bug-report-card__meta-label">Платформы</div>
            <div class="bug-report-card__chips">
              {#each platformLabels as label}
                <span class="bug-report-card__chip">{label}</span>
              {/each}
            </div>
          </div>
        {/if}

        {#if browserLabels.length}
          <div class="bug-report-card__meta-group">
            <div class="bug-report-card__meta-label">Браузеры</div>
            <div class="bug-report-card__chips">
              {#each browserLabels as label}
                <span class="bug-report-card__chip">{label}</span>
              {/each}
            </div>
          </div>
        {/if}
      </div>
    {/if}

    {#if !compact}
      {#if data.error_code}
        <div class="bug-report-card__code-wrap">
          <div class="bug-report-card__meta-label">Код ошибки</div>
          <pre class="bug-report-card__code"><code>{data.error_code}</code></pre>
        </div>
      {/if}

      {#if data.description}
        <div class="bug-report-card__description">{data.description}</div>
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
    border-radius: 28px;
    border: 1px solid rgba(191, 143, 43, 0.45);
    background:
      radial-gradient(circle at top right, rgba(191, 143, 43, 0.18), transparent 40%),
      linear-gradient(145deg, #252833 0%, #2f3a51 100%);
    box-shadow: 0 18px 44px rgba(12, 18, 34, 0.22);
    padding: 1.25rem;
    color: #f8fafc;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .bug-report-card.is-compact .bug-report-card__surface {
    border-radius: 22px;
    padding: 1rem 1.1rem;
    gap: 0.8rem;
  }

  .bug-report-card__topline {
    display: flex;
    align-items: center;
    justify-content: flex-start;
  }

  .bug-report-card__status {
    display: inline-flex;
    align-items: center;
    min-height: 2rem;
    padding: 0.35rem 0.8rem;
    border-radius: 999px;
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid rgba(255, 255, 255, 0.12);
  }

  .bug-report-card__status.tone-amber {
    background: rgba(245, 158, 11, 0.16);
    color: #fde68a;
  }

  .bug-report-card__status.tone-blue {
    background: rgba(59, 130, 246, 0.16);
    color: #bfdbfe;
  }

  .bug-report-card__status.tone-green {
    background: rgba(34, 197, 94, 0.16);
    color: #bbf7d0;
  }

  .bug-report-card__status.tone-red {
    background: rgba(239, 68, 68, 0.16);
    color: #fecaca;
  }

  .bug-report-card__meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.9rem;
  }

  .bug-report-card__meta-group {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  .bug-report-card__meta-label {
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: rgba(248, 250, 252, 0.68);
  }

  .bug-report-card__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .bug-report-card__chip {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.08);
    color: #f8fafc;
    font-size: 0.86rem;
    line-height: 1.1;
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
    border-radius: 18px;
    border: 1px solid rgba(191, 143, 43, 0.24);
    background: rgba(16, 23, 39, 0.72);
    color: #fde68a;
    padding: 0.95rem 1rem;
    font-size: 0.86rem;
    line-height: 1.45;
    overflow-x: auto;
  }

  .bug-report-card__description {
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0.95rem 1rem;
    color: rgba(248, 250, 252, 0.92);
    font-size: 0.95rem;
    line-height: 1.55;
    white-space: pre-wrap;
  }

  .bug-report-card__image {
    width: 100%;
    display: block;
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    object-fit: cover;
    max-height: 24rem;
    background: rgba(15, 23, 42, 0.6);
  }

  @media (max-width: 640px) {
    .bug-report-card__surface {
      border-radius: 24px;
      padding: 1rem;
    }

    .bug-report-card__meta {
      grid-template-columns: 1fr;
    }
  }
</style>
