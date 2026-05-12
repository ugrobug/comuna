<script lang="ts">
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Icon, Trophy } from 'svelte-hero-icons'
  import type { BackendTopAuthor, BackendTopAuthorPeriod } from '$lib/api/backend'
  import {
    formatTopAuthorNumber,
    topAuthorHeroCardClass,
    topAuthorHeroRatingLabelMap,
    topAuthorRankBadgeClass,
  } from '$lib/ratings/topAuthors'

  export let authors: BackendTopAuthor[] = []
  export let period: BackendTopAuthorPeriod = 'month'
</script>

<section class="flex flex-col gap-4">
  {#each authors as author, index}
    <a href={`/${author.username}`} class={topAuthorHeroCardClass(index)}>
      <div class="hero-card__body">
        <div class="flex min-w-0 flex-1 items-center gap-4">
          <div class="hero-avatar-stack">
            <Avatar
              url={author.avatar_url || undefined}
              alt={author.title || author.username}
              width={64}
              class_="hero-avatar-image h-16 w-16 rounded-full ring-4 ring-white/70 dark:ring-zinc-950/70"
            />
            <div class={`${topAuthorRankBadgeClass(index)} hero-rank-badge`}>
              {index + 1}
            </div>
          </div>
          <div class="min-w-0 flex-1">
            <div class="hero-card__title">
              {author.title || author.username}
            </div>
            <div class="mt-1 truncate text-sm text-slate-500 dark:text-zinc-400">
              @{author.username}
            </div>
          </div>
        </div>
        <div class="stat-card stat-card--hero">
          <div class="stat-card__label">{topAuthorHeroRatingLabelMap[period]}</div>
          <div class="mt-3 flex items-center gap-2 text-slate-900 dark:text-zinc-50">
            <Icon src={Trophy} size="18" class="text-amber-500" />
            <div class="stat-card__value stat-card__value--inline">
              {formatTopAuthorNumber(author.rating ?? author.score)}
            </div>
          </div>
        </div>
      </div>
    </a>
  {/each}
</section>

<style>
  .hero-card {
    border-radius: 2rem;
    padding: 1.5rem;
    border: 1px solid rgb(226 232 240);
    background: white;
    box-shadow: 0 1px 2px rgb(15 23 42 / 0.06);
    transition:
      transform 0.15s ease,
      box-shadow 0.15s ease;
  }

  .hero-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 16px 32px rgb(15 23 42 / 0.08);
  }

  .hero-card__body {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
  }

  .hero-card--gold {
    background: linear-gradient(180deg, rgb(255 251 235), white 55%);
  }

  .hero-card--silver {
    background: linear-gradient(180deg, rgb(248 250 252), white 55%);
  }

  .hero-card--bronze {
    background: linear-gradient(180deg, rgb(255 247 237), white 55%);
  }

  :global(.dark) .hero-card {
    border-color: rgb(39 39 42);
    background: rgb(24 24 27);
    box-shadow: none;
  }

  :global(.dark) .hero-card--gold {
    background: linear-gradient(180deg, rgb(69 26 3), rgb(24 24 27) 58%);
  }

  :global(.dark) .hero-card--silver {
    background: linear-gradient(180deg, rgb(39 39 42), rgb(24 24 27) 58%);
  }

  :global(.dark) .hero-card--bronze {
    background: linear-gradient(180deg, rgb(67 20 7), rgb(24 24 27) 58%);
  }

  .rank-badge {
    width: 3rem;
    height: 3rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.125rem;
    font-weight: 700;
    color: white;
  }

  .hero-avatar-stack {
    position: relative;
    flex-shrink: 0;
    width: 4.75rem;
    height: 4.75rem;
  }

  .hero-avatar-image {
    display: block;
  }

  .hero-rank-badge {
    position: absolute;
    right: -0.15rem;
    bottom: -0.15rem;
    width: 2rem;
    height: 2rem;
    font-size: 0.875rem;
    box-shadow: 0 10px 24px rgb(15 23 42 / 0.18);
  }

  .rank-badge--gold {
    background: linear-gradient(135deg, rgb(245 158 11), rgb(217 119 6));
  }

  .rank-badge--silver {
    background: linear-gradient(135deg, rgb(148 163 184), rgb(100 116 139));
  }

  .rank-badge--bronze {
    background: linear-gradient(135deg, rgb(249 115 22), rgb(194 65 12));
  }

  .stat-card {
    border-radius: 1.25rem;
    background: rgb(255 255 255 / 0.75);
    padding: 0.875rem 1rem;
  }

  .stat-card--hero {
    min-width: 12rem;
    flex-shrink: 0;
  }

  :global(.dark) .stat-card {
    background: rgb(24 24 27 / 0.7);
  }

  .stat-card__label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgb(100 116 139);
  }

  .stat-card__value {
    margin-top: 0.375rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: rgb(15 23 42);
  }

  .stat-card__value--inline {
    margin-top: 0;
  }

  .hero-card__title {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    line-clamp: 2;
    -webkit-line-clamp: 2;
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.2;
    color: rgb(15 23 42);
    overflow-wrap: anywhere;
  }

  :global(.dark) .stat-card__label {
    color: rgb(161 161 170);
  }

  :global(.dark) .stat-card__value,
  :global(.dark) .hero-card__title {
    color: rgb(244 244 245);
  }

  @media (max-width: 640px) {
    .hero-card__body {
      flex-direction: column;
      align-items: flex-start;
    }

    .stat-card--hero {
      width: 100%;
      min-width: 0;
    }
  }
</style>
