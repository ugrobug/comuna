<script lang="ts">
  import {
    formatMovieReviewReleaseDate,
    movieReviewGenreLabel,
    movieReviewKindLabel,
    movieReviewWatchWhereLabels,
    type MovieReviewTemplate,
  } from '$lib/postTemplates'

  export let template: MovieReviewTemplate
  export let fallbackTitle = ''

  $: data = template.data
  $: displayTitle = (data.title || fallbackTitle || '').trim()
  $: displayOriginalTitle = (data.original_title || '').trim()
  $: displayGenre = movieReviewGenreLabel(data.genre)
  $: releaseLabel = formatMovieReviewReleaseDate(data.release_date)
  $: watchWhereLabels = movieReviewWatchWhereLabels(data.watch_where)
  $: imdbHost = (() => {
    try {
      if (!data.imdb_url) return ''
      return new URL(data.imdb_url).hostname.replace(/^www\./, '')
    } catch {
      return 'IMDb'
    }
  })()
</script>

<section class="movie-review-hero overflow-hidden rounded-2xl border border-slate-200 dark:border-zinc-800">
  <div class="movie-review-hero__bg" style={data.poster_url ? `--poster:url('${data.poster_url}')` : undefined}></div>
  <div class="movie-review-hero__body">
    {#if data.poster_url}
      <div class="movie-review-hero__poster">
        <img src={data.poster_url} alt={displayTitle || 'Постер'} loading="lazy" />
      </div>
    {/if}

    <div class="movie-review-hero__content">
      <div class="movie-review-hero__chips">
        {#if data.content_kind}
          <span class="movie-review-chip">{movieReviewKindLabel(data.content_kind)}</span>
        {/if}
        {#if displayGenre}
          <span class="movie-review-chip">{displayGenre}</span>
        {/if}
        {#if releaseLabel}
          <span class="movie-review-chip">Премьера: {releaseLabel}</span>
        {/if}
      </div>

      {#if displayTitle}
        <h2 class="movie-review-hero__title">{displayTitle}</h2>
      {/if}

      {#if displayOriginalTitle && displayOriginalTitle.toLowerCase() !== displayTitle.toLowerCase()}
        <p class="movie-review-hero__subtitle">{displayOriginalTitle}</p>
      {/if}

      <div class="movie-review-hero__meta">
        {#if watchWhereLabels.length}
          <div class="movie-review-meta-item">
            <span class="movie-review-meta-label">Где посмотреть</span>
            <span class="movie-review-meta-value">{watchWhereLabels.join(', ')}</span>
          </div>
        {/if}

        {#if data.imdb_url}
          <div class="movie-review-meta-item">
            <span class="movie-review-meta-label">IMDb</span>
            <a
              href={data.imdb_url}
              target="_blank"
              rel="nofollow noopener"
              class="movie-review-meta-link"
            >
              Открыть на {imdbHost || 'IMDb'}
            </a>
          </div>
        {/if}
      </div>
    </div>
  </div>
</section>

<style lang="postcss">
  .movie-review-hero {
    position: relative;
    background:
      radial-gradient(120% 120% at 10% 0%, rgba(251, 191, 36, 0.25) 0%, rgba(251, 191, 36, 0) 55%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(30, 41, 59, 0.9));
  }

  .movie-review-hero__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .movie-review-hero__bg::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    background-image: var(--poster);
    background-size: cover;
    background-position: center;
    filter: blur(28px) saturate(0.9);
    transform: scale(1.2);
  }

  .movie-review-hero__bg[style*='--poster']::before {
    opacity: 0.22;
  }

  .movie-review-hero__body {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 180px) minmax(0, 1fr);
    gap: 1rem;
    padding: 1rem;
    align-items: start;
  }

  .movie-review-hero__poster {
    width: 100%;
    max-width: 180px;
    border-radius: 0.9rem;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 10px 25px rgba(2, 6, 23, 0.45);
    background: rgba(15, 23, 42, 0.35);
  }

  .movie-review-hero__poster img {
    display: block;
    width: 100%;
    height: auto;
    object-fit: cover;
    aspect-ratio: 2 / 3;
  }

  .movie-review-hero__content {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    color: #e2e8f0;
  }

  .movie-review-hero__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .movie-review-chip {
    border-radius: 9999px;
    border: 1px solid rgba(251, 191, 36, 0.45);
    background: rgba(15, 23, 42, 0.45);
    padding: 0.25rem 0.6rem;
    font-size: 0.75rem;
    line-height: 1.1;
    color: #fde68a;
  }

  .movie-review-hero__title {
    margin: 0;
    font-size: clamp(1.35rem, 2.1vw, 1.95rem);
    line-height: 1.15;
    color: #fff;
    font-weight: 700;
    text-wrap: balance;
  }

  .movie-review-hero__subtitle {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.98rem;
  }

  .movie-review-hero__meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.55rem;
    margin-top: 0.25rem;
  }

  .movie-review-meta-item {
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 0.75rem;
    background: rgba(15, 23, 42, 0.4);
    padding: 0.55rem 0.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .movie-review-meta-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #94a3b8;
  }

  .movie-review-meta-value {
    color: #f8fafc;
    font-size: 0.9rem;
    line-height: 1.3;
  }

  .movie-review-meta-link {
    color: #f59e0b;
    font-size: 0.9rem;
    line-height: 1.3;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .movie-review-meta-link:hover {
    color: #fbbf24;
  }

  @media (max-width: 760px) {
    .movie-review-hero__body {
      grid-template-columns: 1fr;
    }

    .movie-review-hero__poster {
      max-width: 160px;
    }
  }
</style>
