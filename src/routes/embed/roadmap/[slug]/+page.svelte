<script lang="ts">
  import {
    buildBackendPostPath,
    type BackendComun,
    type BackendComunRoadmapItem,
    type BackendComunRoadmapStage,
  } from '$lib/api/backend'
  import {
    buildComunRoadmapPagePath,
    roadmapEmbedCardLabel,
    roadmapEmbedLabels,
  } from '$lib/roadmapEmbed'

  export let data

  type StageDefinition = {
    key: BackendComunRoadmapStage
    label: string
    empty: string
  }

  const stageStyleVars = (stage: BackendComunRoadmapStage) => {
    if (stage === 'planned') return '--lane-h: 34; --lane-s: 88%; --lane-l: 50%;'
    if (stage === 'in_progress') return '--lane-h: 153; --lane-s: 77%; --lane-l: 40%;'
    return '--lane-h: 340; --lane-s: 78%; --lane-l: 52%;'
  }

  const postSnippet = (content: string | null | undefined) => {
    const source = String(content || '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&(quot|amp|apos|lt|gt|nbsp);/gi, (match, entity: string) => {
        const values: Record<string, string> = {
          quot: '"',
          amp: '&',
          apos: "'",
          lt: '<',
          gt: '>',
          nbsp: ' ',
        }
        return values[entity.toLowerCase()] ?? match
      })
      .replace(/\s+/g, ' ')
      .trim()
    return source.length > 130 ? `${source.slice(0, 129).trimEnd()}…` : source
  }

  let comun: BackendComun | null = data?.comun ?? null
  let items: BackendComunRoadmapItem[] = Array.isArray(data?.items) ? data.items : []

  $: language = String(data?.language || 'ru')
  $: labels = roadmapEmbedLabels(language)
  $: stages = [
    { key: 'planned', label: labels.planned, empty: labels.emptyPlanned },
    { key: 'in_progress', label: labels.inProgress, empty: labels.emptyInProgress },
    { key: 'done', label: labels.done, empty: labels.emptyDone },
  ] satisfies StageDefinition[]
  $: numberFormatter = new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : language)
  $: dateFormatter = new Intl.DateTimeFormat(language === 'ru' ? 'ru-RU' : language, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
  $: roadmapPath = buildComunRoadmapPagePath(comun?.slug || '', language)
  $: pageTitle = `${labels.openRoadmap} — ${comun?.name || 'Tambur'}`

  const itemsForStage = (stage: BackendComunRoadmapStage) =>
    items
      .filter((item) => item.stage === stage)
      .sort((left, right) => Number(left.position ?? 0) - Number(right.position ?? 0))

  const formatDate = (value: string | null | undefined) => {
    if (!value) return ''
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? '' : dateFormatter.format(date)
  }
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="embed-roadmap">
  <header class="embed-header">
    <div class="community-identity">
      {#if comun?.logo_url}
        <img src={comun.logo_url} alt="" class="community-logo" />
      {:else}
        <span class="community-logo community-logo--fallback">
          {(comun?.name || 'T').slice(0, 1).toUpperCase()}
        </span>
      {/if}
      <div class="community-copy">
        <strong>{comun?.name || 'Tambur'}</strong>
        {#if comun?.product_description}
          <span>{comun.product_description}</span>
        {/if}
      </div>
    </div>
    <a href={roadmapPath} target="_blank" rel="noopener noreferrer" class="open-roadmap">
      {labels.openRoadmap}
    </a>
  </header>

  <div class="roadmap-scroll">
    <div class="roadmap-grid">
      {#each stages as stage}
        {@const stageItems = itemsForStage(stage.key)}
        <section class="roadmap-lane" style={stageStyleVars(stage.key)}>
          <header class="lane-header">
            <span class="lane-pill">{stage.label}</span>
            <span class="lane-count">
              {numberFormatter.format(stageItems.length)} {roadmapEmbedCardLabel(language, stageItems.length)}
            </span>
          </header>

          <div class="lane-content">
            {#if stageItems.length}
              {#each stageItems as item (item.id)}
                {@const snippet = postSnippet(item.post.content)}
                <a
                  href={buildBackendPostPath(item.post, language)}
                  target="_blank"
                  rel="noopener noreferrer"
                  class="roadmap-card"
                >
                  <strong>{item.post.title || labels.untitled}</strong>
                  {#if snippet}<span class="card-snippet">{snippet}</span>{/if}
                  <span class="card-meta">
                    <span>{labels.votes} {numberFormatter.format(item.post.likes_count ?? 0)}</span>
                    <span>{labels.comments} {numberFormatter.format(item.post.comments_count ?? 0)}</span>
                    {#if formatDate(item.post.created_at)}
                      <span>{formatDate(item.post.created_at)}</span>
                    {/if}
                  </span>
                  <span class="card-action">{labels.openPost}</span>
                </a>
              {/each}
            {:else}
              <div class="lane-empty">{stage.empty}</div>
            {/if}
          </div>
        </section>
      {/each}
    </div>
  </div>

  <footer class="embed-footer">
    <a href={roadmapPath} target="_blank" rel="noopener noreferrer">Tambur</a>
  </footer>
</div>

<style>
  :global(html),
  :global(body) {
    margin: 0;
    min-width: 280px;
    background: transparent;
  }

  .embed-roadmap {
    box-sizing: border-box;
    min-height: 100vh;
    padding: 14px;
    background:
      radial-gradient(circle at 8% 0%, rgb(59 130 246 / 0.1), transparent 28rem),
      radial-gradient(circle at 92% 0%, rgb(249 115 22 / 0.1), transparent 24rem),
      #f8fafc;
    color: #0f172a;
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  .embed-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin: 0 auto 12px;
    max-width: 1320px;
  }

  .community-identity {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 10px;
  }

  .community-logo {
    width: 42px;
    height: 42px;
    flex: none;
    border: 1px solid rgb(203 213 225 / 0.85);
    border-radius: 10px;
    background: white;
    object-fit: cover;
  }

  .community-logo--fallback {
    display: grid;
    place-items: center;
    color: #4338ca;
    font-size: 18px;
    font-weight: 750;
  }

  .community-copy {
    display: grid;
    min-width: 0;
    gap: 2px;
  }

  .community-copy strong,
  .community-copy span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .community-copy strong {
    font-size: 15px;
  }

  .community-copy span {
    max-width: 680px;
    color: #64748b;
    font-size: 12px;
  }

  .open-roadmap {
    flex: none;
    color: #334155;
    font-size: 12px;
    font-weight: 650;
    text-decoration: none;
  }

  .open-roadmap:hover,
  .embed-footer a:hover {
    color: #2563eb;
  }

  .roadmap-scroll {
    max-width: 1320px;
    margin: 0 auto;
    overflow-x: auto;
    overscroll-behavior-x: contain;
  }

  .roadmap-grid {
    display: grid;
    min-width: 780px;
    grid-template-columns: repeat(3, minmax(240px, 1fr));
    gap: 10px;
    align-items: start;
  }

  .roadmap-lane {
    min-width: 0;
    padding: 12px;
    border: 1px solid rgb(148 163 184 / 0.24);
    border-radius: 12px;
    background: linear-gradient(180deg, hsla(var(--lane-h), 95%, 97%, 0.9), rgb(255 255 255 / 0.92));
  }

  .lane-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .lane-pill {
    padding: 4px 8px;
    border: 1px solid hsla(var(--lane-h), 84%, 56%, 0.2);
    border-radius: 999px;
    background: hsla(var(--lane-h), 92%, 93%, 0.94);
    color: hsl(var(--lane-h) 60% 30%);
    font-size: 10px;
    font-weight: 750;
    text-transform: uppercase;
  }

  .lane-count {
    color: #64748b;
    font-size: 11px;
  }

  .lane-content {
    display: grid;
    gap: 7px;
    margin-top: 10px;
  }

  .roadmap-card {
    display: grid;
    gap: 6px;
    padding: 10px;
    border: 1px solid rgb(148 163 184 / 0.2);
    border-radius: 9px;
    background: rgb(255 255 255 / 0.92);
    color: inherit;
    text-decoration: none;
    transition: border-color 140ms ease, box-shadow 140ms ease, transform 140ms ease;
  }

  .roadmap-card:hover {
    border-color: hsla(var(--lane-h), 80%, 48%, 0.34);
    box-shadow: 0 7px 18px rgb(15 23 42 / 0.07);
    transform: translateY(-1px);
  }

  .roadmap-card strong {
    line-clamp: 2;
    display: -webkit-box;
    overflow: hidden;
    font-size: 13px;
    line-height: 1.3;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .card-snippet {
    line-clamp: 3;
    display: -webkit-box;
    overflow: hidden;
    color: #475569;
    font-size: 11px;
    line-height: 1.4;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
  }

  .card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 3px 8px;
    color: #64748b;
    font-size: 10px;
  }

  .card-action {
    color: hsl(var(--lane-h) 62% 36%);
    font-size: 10px;
    font-weight: 650;
  }

  .lane-empty {
    padding: 12px;
    border: 1px dashed rgb(148 163 184 / 0.34);
    border-radius: 9px;
    color: #64748b;
    font-size: 11px;
    line-height: 1.45;
  }

  .embed-footer {
    display: flex;
    max-width: 1320px;
    justify-content: flex-end;
    margin: 9px auto 0;
  }

  .embed-footer a {
    color: #64748b;
    font-size: 11px;
    font-weight: 750;
    text-decoration: none;
  }

  :global(.dark) .embed-roadmap {
    background:
      radial-gradient(circle at 8% 0%, rgb(59 130 246 / 0.14), transparent 28rem),
      radial-gradient(circle at 92% 0%, rgb(249 115 22 / 0.12), transparent 24rem),
      #09090b;
    color: #f4f4f5;
  }

  :global(.dark) .community-logo {
    border-color: #3f3f46;
    background: #18181b;
  }

  :global(.dark) .community-copy span,
  :global(.dark) .lane-count,
  :global(.dark) .card-snippet,
  :global(.dark) .card-meta,
  :global(.dark) .lane-empty,
  :global(.dark) .embed-footer a,
  :global(.dark) .open-roadmap {
    color: #a1a1aa;
  }

  :global(.dark) .roadmap-lane {
    border-color: rgb(63 63 70 / 0.86);
    background: linear-gradient(180deg, hsla(var(--lane-h), 44%, 15%, 0.42), rgb(24 24 27 / 0.86));
  }

  :global(.dark) .roadmap-card {
    border-color: rgb(63 63 70 / 0.8);
    background: rgb(9 9 11 / 0.42);
  }

  :global(.dark) .lane-empty {
    border-color: #52525b;
  }

  @media (max-width: 620px) {
    .embed-roadmap {
      padding: 10px;
    }

    .embed-header {
      align-items: flex-start;
    }

    .community-copy span,
    .open-roadmap {
      display: none;
    }

    .roadmap-grid {
      min-width: 0;
      grid-template-columns: 1fr;
    }
  }
</style>
