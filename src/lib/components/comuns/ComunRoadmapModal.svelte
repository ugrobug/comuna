<script lang="ts">
  import { Button } from 'mono-svelte'
  import Portal from '$lib/mono/popover/Portal.svelte'
  import type { BackendPost } from '$lib/api/backend'

  export let open = false
  export let comunName = 'Сообщество'
  export let trackedCount = 0
  export let releasedCount = 0
  export let stages: Array<{
    key: string
    shortLabel: string
    emptyState: string
    count: number
    category: { name: string }
  }> = []
  export let getPreviewState: (stageKey: string) => {
    loading: boolean
    error: string | null
    posts: BackendPost[]
  }
  export let stageStyleVars: (stageKey: string) => string
  export let buildPostPath: (post: BackendPost) => string
  export let formatCount: (value?: number | null) => string
  export let formatDate: (value?: string | null) => string
  export let snippetForPost: (post: BackendPost, maxLength?: number) => string
  export let onClose: () => void
  export let onSubmit: () => void
</script>

{#if open}
  <Portal class="public-roadmap-portal-root">
    <div
      class="public-roadmap-modal fixed inset-0 z-[1200] flex h-screen w-screen items-stretch justify-stretch p-0"
      style="position: fixed; inset: 0; width: 100vw; height: 100dvh; z-index: 2147483000; margin: 0;"
      role="dialog"
      aria-modal="true"
      aria-label="Публичная дорожная карта"
    >
      <button
        type="button"
        class="public-roadmap-modal__backdrop absolute inset-0"
        on:click={onClose}
        aria-label="Закрыть дорожную карту"
      ></button>
      <section
        class="public-roadmap-modal__panel relative z-10 flex h-screen w-screen flex-col overflow-hidden"
        style="position: relative; width: 100vw; height: 100dvh;"
      >
        <header class="public-roadmap-modal__header flex items-center justify-between gap-3 px-3 py-2 sm:px-4">
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
              Публичная дорожная карта
            </div>
            <div class="truncate text-xs text-slate-500 dark:text-zinc-400">
              {comunName}
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              type="button"
              class="inline-flex items-center rounded-lg border border-slate-200 dark:border-zinc-700 px-3 py-1.5 text-xs sm:text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
              on:click={onClose}
              aria-label="Закрыть дорожную карту"
              title="Закрыть (Esc)"
            >
              Закрыть
            </button>
          </div>
        </header>
        <div class="public-roadmap-modal__content min-h-0 flex-1 overflow-y-auto">
          <div class="mx-auto w-full max-w-[1600px] p-3 sm:p-4 md:p-5">
            <section class="roadmap-shell rounded-3xl overflow-hidden">
              <div class="roadmap-glow"></div>
              <div class="roadmap-content p-4 sm:p-5 md:p-6 flex flex-col gap-5">
                <div class="roadmap-hero grid gap-4">
                  <div class="roadmap-hero-card rounded-2xl p-4 sm:p-5 flex flex-col gap-3">
                    <div class="space-y-2">
                      <h2 class="roadmap-title">
                        Показывайте, что будет дальше, и собирайте обратную связь в одном месте
                      </h2>
                    </div>
                    <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <div class="roadmap-stat-card rounded-xl p-3">
                        <div class="roadmap-stat-label">В дорожной карте всего</div>
                        <div class="roadmap-stat-value">{formatCount(trackedCount)}</div>
                      </div>
                      <div class="roadmap-stat-card rounded-xl p-3">
                        <div class="roadmap-stat-label">Готово</div>
                        <div class="roadmap-stat-value">{formatCount(releasedCount)}</div>
                      </div>
                    </div>
                  </div>
                </div>

                <div class="grid gap-3 lg:grid-cols-3">
                  {#each stages as stage}
                    {@const preview = getPreviewState(stage.key)}
                    <section
                      class="roadmap-lane rounded-2xl p-4 flex flex-col gap-3"
                      data-stage={stage.key}
                      style={stageStyleVars(stage.key)}
                    >
                      <div class="flex items-start justify-between gap-3">
                        <div class="min-w-0">
                          <div class="roadmap-lane-kicker">{stage.shortLabel}</div>
                          <div class="text-sm font-semibold text-slate-900 dark:text-zinc-100 truncate">
                            {stage.category.name}
                          </div>
                          <div class="text-xs text-slate-500 dark:text-zinc-400">
                            {formatCount(stage.count)} карточек
                          </div>
                        </div>
                      </div>

                      {#if preview.error}
                        <div class="roadmap-lane-state roadmap-lane-state--error">{preview.error}</div>
                      {:else if preview.posts.length}
                        <div class="flex flex-col gap-2">
                          {#each preview.posts as item}
                            {@const itemSnippet = snippetForPost(item)}
                            {@const itemDate = formatDate(item.created_at)}
                            <a
                              href={buildPostPath(item)}
                              class="roadmap-mini-card rounded-xl p-3 flex flex-col gap-2"
                              title="Открыть карточку и обсуждение"
                            >
                              <div class="roadmap-mini-title">{item.title || 'Без заголовка'}</div>
                              {#if itemSnippet}
                                <div class="roadmap-mini-snippet">{itemSnippet}</div>
                              {/if}
                              <div class="roadmap-mini-meta">
                                <span>Голоса: {formatCount(item.likes_count ?? 0)}</span>
                                <span>Комментарии: {formatCount(item.comments_count ?? 0)}</span>
                                {#if itemDate}
                                  <span>{itemDate}</span>
                                {/if}
                              </div>
                            </a>
                          {/each}
                        </div>
                      {:else if !preview.loading}
                        <div class="roadmap-lane-state">{stage.emptyState}</div>
                      {/if}
                    </section>
                  {/each}
                </div>

                <div class="roadmap-footer rounded-2xl p-4 flex items-center justify-start">
                  <Button on:click={onSubmit}>
                    Добавить предложение
                  </Button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>
    </div>
  </Portal>
{/if}

<style>
  .roadmap-shell {
    position: relative;
    background:
      radial-gradient(circle at top left, rgba(96, 165, 250, 0.18), transparent 42%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.98));
    border: 1px solid rgba(148, 163, 184, 0.2);
    box-shadow:
      0 28px 60px rgba(15, 23, 42, 0.12),
      inset 0 1px 0 rgba(255, 255, 255, 0.72);
  }

  :global(.dark) .roadmap-shell {
    background:
      radial-gradient(circle at top left, rgba(59, 130, 246, 0.16), transparent 42%),
      linear-gradient(180deg, rgba(15, 23, 42, 0.92), rgba(9, 9, 11, 0.98));
    border-color: rgba(63, 63, 70, 0.88);
    box-shadow:
      0 24px 54px rgba(0, 0, 0, 0.34),
      inset 0 1px 0 rgba(255, 255, 255, 0.04);
  }

  .roadmap-glow {
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle at 85% 0%, rgba(251, 191, 36, 0.14), transparent 28%),
      radial-gradient(circle at 0% 100%, rgba(16, 185, 129, 0.12), transparent 30%);
    pointer-events: none;
  }

  :global(.dark) .roadmap-glow {
    background:
      radial-gradient(circle at 85% 0%, rgba(251, 191, 36, 0.09), transparent 28%),
      radial-gradient(circle at 0% 100%, rgba(16, 185, 129, 0.08), transparent 30%);
  }

  .roadmap-content {
    position: relative;
    z-index: 1;
  }

  .roadmap-hero-card,
  .roadmap-footer {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(18px);
  }

  :global(.dark) .roadmap-hero-card,
  :global(.dark) .roadmap-footer {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(24, 24, 27, 0.58);
  }

  .roadmap-title {
    font-size: clamp(1.45rem, 2vw, 2.1rem);
    line-height: 1.05;
    letter-spacing: -0.03em;
    color: rgb(15 23 42);
  }

  :global(.dark) .roadmap-title {
    color: rgb(244 244 245);
  }

  .roadmap-stat-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(248, 250, 252, 0.82);
  }

  :global(.dark) .roadmap-stat-card {
    border-color: rgba(63, 63, 70, 0.75);
    background: rgba(9, 9, 11, 0.42);
  }

  .roadmap-stat-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: rgb(71 85 105);
  }

  .roadmap-stat-value {
    margin-top: 0.35rem;
    font-size: 1.4rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    color: rgb(15 23 42);
  }

  :global(.dark) .roadmap-stat-label {
    color: rgb(161 161 170);
  }

  :global(.dark) .roadmap-stat-value {
    color: rgb(244 244 245);
  }

  .roadmap-lane {
    border: 1px solid rgba(148, 163, 184, 0.2);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(248, 250, 252, 0.9)),
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 92%, 97%, 0.75),
        rgba(255, 255, 255, 0)
      );
  }

  :global(.dark) .roadmap-lane {
    border-color: rgba(63, 63, 70, 0.8);
    background:
      linear-gradient(180deg, rgba(24, 24, 27, 0.88), rgba(9, 9, 11, 0.92)),
      linear-gradient(
        180deg,
        hsla(var(--roadmap-stage-h), 40%, 13%, 0.38),
        rgba(9, 9, 11, 0)
      );
  }

  .roadmap-lane-kicker {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    font-size: 0.73rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: hsl(var(--roadmap-stage-h) 60% 30%);
    background: hsla(var(--roadmap-stage-h), 95%, 93%, 0.92);
    border: 1px solid hsla(var(--roadmap-stage-h), 88%, 56%, 0.2);
  }

  :global(.dark) .roadmap-lane-kicker {
    color: hsl(var(--roadmap-stage-h) 90% 82%);
    background: hsla(var(--roadmap-stage-h), 48%, 18%, 0.6);
    border-color: hsla(var(--roadmap-stage-h), 64%, 52%, 0.22);
  }

  .roadmap-mini-card {
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(255, 255, 255, 0.82);
    transition:
      transform 0.18s ease,
      border-color 0.18s ease,
      box-shadow 0.18s ease;
  }

  .roadmap-mini-card:hover {
    transform: translateY(-1px);
    border-color: hsla(var(--roadmap-stage-h), 80%, 48%, 0.28);
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.08);
  }

  :global(.dark) .roadmap-mini-card {
    border-color: rgba(63, 63, 70, 0.82);
    background: rgba(24, 24, 27, 0.76);
  }

  :global(.dark) .roadmap-mini-card:hover {
    border-color: hsla(var(--roadmap-stage-h), 70%, 56%, 0.3);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.22);
  }

  .roadmap-mini-title {
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.35;
    color: rgb(15 23 42);
  }

  .roadmap-mini-snippet {
    display: -webkit-box;
    line-clamp: 3;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 0.88rem;
    line-height: 1.5;
    color: rgb(71 85 105);
  }

  .roadmap-mini-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem 0.85rem;
    font-size: 0.75rem;
    color: rgb(100 116 139);
  }

  :global(.dark) .roadmap-mini-title {
    color: rgb(244 244 245);
  }

  :global(.dark) .roadmap-mini-snippet {
    color: rgb(161 161 170);
  }

  :global(.dark) .roadmap-mini-meta {
    color: rgb(113 113 122);
  }

  .roadmap-lane-state {
    min-height: 5.25rem;
    display: grid;
    place-items: center;
    text-align: center;
    border: 1px dashed rgba(148, 163, 184, 0.32);
    border-radius: 1rem;
    padding: 1rem;
    font-size: 0.88rem;
    color: rgb(71 85 105);
    background: rgba(248, 250, 252, 0.54);
  }

  .roadmap-lane-state--error {
    border-color: rgba(248, 113, 113, 0.35);
    color: rgb(185 28 28);
    background: rgba(254, 242, 242, 0.78);
  }

  :global(.dark) .roadmap-lane-state {
    border-color: rgba(82, 82, 91, 0.82);
    color: rgb(161 161 170);
    background: rgba(9, 9, 11, 0.35);
  }

  :global(.dark) .roadmap-lane-state--error {
    border-color: rgba(190, 24, 93, 0.32);
    color: rgb(253 164 175);
    background: rgba(76, 5, 25, 0.34);
  }

  .public-roadmap-modal {
    overscroll-behavior: contain;
  }

  :global(.portal-content.public-roadmap-portal-root) {
    position: fixed !important;
    inset: 0 !important;
    width: 100vw !important;
    height: 100dvh !important;
    margin: 0 !important;
    padding: 0 !important;
    display: block !important;
    z-index: 2147483000 !important;
    max-width: none !important;
    max-height: none !important;
    transform: none !important;
    pointer-events: none;
  }

  :global(.portal-content.public-roadmap-portal-root > .public-roadmap-modal) {
    pointer-events: auto;
  }

  .public-roadmap-modal__backdrop {
    border: 0;
    background:
      radial-gradient(circle at top, rgba(59, 130, 246, 0.14), transparent 38%),
      rgba(15, 23, 42, 0.58);
  }

  :global(.dark) .public-roadmap-modal__backdrop {
    background:
      radial-gradient(circle at top, rgba(59, 130, 246, 0.12), transparent 38%),
      rgba(2, 6, 23, 0.8);
  }

  .public-roadmap-modal__panel {
    backdrop-filter: blur(20px);
  }

  :global(.dark) .public-roadmap-modal__panel {
    background: rgba(2, 6, 23, 0.2);
  }

  .public-roadmap-modal__header {
    position: sticky;
    top: 0;
    z-index: 1;
    backdrop-filter: blur(18px);
    background: rgba(248, 250, 252, 0.86);
    border-bottom: 1px solid rgba(148, 163, 184, 0.2);
  }

  :global(.dark) .public-roadmap-modal__header {
    background: rgba(9, 9, 11, 0.82);
    border-bottom-color: rgba(63, 63, 70, 0.82);
  }

  .public-roadmap-modal__content {
    overscroll-behavior: contain;
  }

  :global(.dark) .public-roadmap-modal__content {
    background: transparent;
  }

  @media (max-width: 640px) {
    .public-roadmap-modal__header {
      padding-top: max(0.5rem, env(safe-area-inset-top));
    }
  }
</style>
