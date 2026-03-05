<script lang="ts">
  import {
    formatMusicReleaseDate,
    musicReleaseStyleLabel,
    type MusicReleaseTemplate,
  } from '$lib/postTemplates'

  export let template: MusicReleaseTemplate
  export let fallbackTitle = ''

  type ReleaseEmbed = {
    provider: 'spotify' | 'yandex_music' | 'soundcloud'
    providerLabel: string
    embedUrl: string
    title: string
    height: number
  }

  const normalizeExternalUrl = (value: string | undefined): string => {
    const raw = (value || '').trim()
    if (!raw) return ''

    // Allow pasting full iframe code from "Поделиться" and extract src.
    const quotedSrcMatch = raw.match(/src\s*=\s*(['"])(https?:\/\/[^'"]+)\1/i)
    const plainSrcMatch = raw.match(/src\s*=\s*(https?:\/\/[^\s>]+)/i)
    const extracted = (quotedSrcMatch?.[2] || plainSrcMatch?.[1] || raw)
      .replace(/&amp;/gi, '&')
      .trim()

    if (!extracted) return ''
    if (/^https?:\/\//i.test(extracted)) return extracted
    return `https://${extracted}`
  }

  const resolveReleaseEmbed = (value: string): ReleaseEmbed | null => {
    if (!value) return null

    let parsed: URL
    try {
      parsed = new URL(value)
    } catch {
      return null
    }

    const host = parsed.hostname.replace(/^www\./i, '').toLowerCase()
    const path = parsed.pathname

    if (host === 'music.yandex.ru' || host === 'music.yandex.com') {
      const albumTrackMatch =
        path.match(/\/album\/(\d+)\/track\/(\d+)(?:\/|$)/i) ||
        path.match(/\/iframe\/album\/(\d+)\/track\/(\d+)(?:\/|$)/i)
      if (albumTrackMatch) {
        const albumId = albumTrackMatch[1]
        const trackId = albumTrackMatch[2]
        return {
          provider: 'yandex_music',
          providerLabel: 'Яндекс Музыка',
          embedUrl: `https://music.yandex.ru/iframe/album/${albumId}/track/${trackId}`,
          title: 'Плеер Яндекс Музыки',
          height: 244,
        }
      }

      const hashTrackMatch = parsed.hash.match(/#track\/(\d+)\/(\d+)(?:\/|$)/i)
      if (hashTrackMatch) {
        const trackId = hashTrackMatch[1]
        const albumId = hashTrackMatch[2]
        return {
          provider: 'yandex_music',
          providerLabel: 'Яндекс Музыка',
          embedUrl: `https://music.yandex.ru/iframe/album/${albumId}/track/${trackId}`,
          title: 'Плеер Яндекс Музыки',
          height: 244,
        }
      }

      const trackMatch = path.match(/\/track\/(\d+)(?:\/|$)/i)
      if (trackMatch) {
        const trackId = trackMatch[1]
        const albumId = parsed.searchParams.get('album_id') || parsed.searchParams.get('albumId')
        if (albumId) {
          return {
            provider: 'yandex_music',
            providerLabel: 'Яндекс Музыка',
            embedUrl: `https://music.yandex.ru/iframe/album/${albumId}/track/${trackId}`,
            title: 'Плеер Яндекс Музыки',
            height: 244,
          }
        }
      }
    }

    if (host === 'open.spotify.com' || host.endsWith('.spotify.com')) {
      const trackMatch = path.match(/\/track\/([A-Za-z0-9]+)(?:\/|$)/)
      if (trackMatch) {
        return {
          provider: 'spotify',
          providerLabel: 'Spotify',
          embedUrl: `https://open.spotify.com/embed/track/${trackMatch[1]}?utm_source=comuna`,
          title: 'Плеер Spotify',
          height: 152,
        }
      }
      const albumMatch = path.match(/\/album\/([A-Za-z0-9]+)(?:\/|$)/)
      if (albumMatch) {
        return {
          provider: 'spotify',
          providerLabel: 'Spotify',
          embedUrl: `https://open.spotify.com/embed/album/${albumMatch[1]}?utm_source=comuna`,
          title: 'Плеер Spotify',
          height: 352,
        }
      }
    }

    if (host === 'soundcloud.com' || host.endsWith('.soundcloud.com') || host === 'snd.sc') {
      return {
        provider: 'soundcloud',
        providerLabel: 'SoundCloud',
        embedUrl: `https://w.soundcloud.com/player/?url=${encodeURIComponent(value)}&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false`,
        title: 'Плеер SoundCloud',
        height: 180,
      }
    }

    return null
  }

  $: data = template.data
  $: displayTitle = (data.release_title || fallbackTitle || '').trim()
  $: displayArtist = (data.artist_name || '').trim()
  $: styleLabel = musicReleaseStyleLabel(data.style)
  $: releaseDateLabel = formatMusicReleaseDate(data.release_date)
  $: locationLabel = [data.city, data.country].filter(Boolean).join(', ')
  $: normalizedAlbumUrl = normalizeExternalUrl(data.album_url)
  $: releaseEmbed = resolveReleaseEmbed(normalizedAlbumUrl)
  $: albumHost = (() => {
    try {
      if (!normalizedAlbumUrl) return ''
      return new URL(normalizedAlbumUrl).hostname.replace(/^www\./, '')
    } catch {
      return ''
    }
  })()
</script>

<section class="music-release-hero overflow-hidden rounded-2xl border border-slate-200 dark:border-zinc-800">
  <div
    class="music-release-hero__bg"
    style={data.cover_image_url ? `--cover:url('${data.cover_image_url}')` : undefined}
  ></div>
  <div class="music-release-hero__body">
    {#if data.cover_image_url}
      <div class="music-release-hero__cover">
        <img src={data.cover_image_url} alt={displayTitle || 'Обложка релиза'} loading="lazy" />
      </div>
    {/if}

    <div class="music-release-hero__content">
      <div class="music-release-hero__chips">
        {#if styleLabel}
          <span class="music-release-chip">{styleLabel}</span>
        {/if}
        {#if releaseDateLabel}
          <span class="music-release-chip">Релиз: {releaseDateLabel}</span>
        {/if}
      </div>

      {#if displayTitle}
        <h2 class="music-release-hero__title">{displayTitle}</h2>
      {/if}

      {#if displayArtist}
        <p class="music-release-hero__subtitle">{displayArtist}</p>
      {/if}

      <div class="music-release-hero__meta">
        {#if locationLabel}
          <div class="music-release-meta-item">
            <span class="music-release-meta-label">Группа</span>
            <span class="music-release-meta-value">{locationLabel}</span>
          </div>
        {/if}

        {#if normalizedAlbumUrl}
          <div class="music-release-meta-item">
            <span class="music-release-meta-label">Ссылка на релиз</span>
            <a
              href={normalizedAlbumUrl}
              target="_blank"
              rel="nofollow noopener"
              class="music-release-meta-link"
            >
              Открыть на {albumHost || 'площадке'}
            </a>
          </div>
        {/if}
      </div>

      {#if releaseEmbed}
        <div class="music-release-hero__player">
          <iframe
            class="music-release-player__frame"
            src={releaseEmbed.embedUrl}
            loading="lazy"
            title={releaseEmbed.title}
            frameborder="0"
            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
            referrerpolicy="no-referrer-when-downgrade"
            style={`--player-height:${releaseEmbed.height}px`}
          ></iframe>
        </div>
      {/if}
    </div>
  </div>
</section>

<style lang="postcss">
  .music-release-hero {
    position: relative;
    background:
      radial-gradient(130% 120% at 0% 0%, rgba(34, 211, 238, 0.24), rgba(34, 211, 238, 0) 56%),
      radial-gradient(120% 120% at 100% 0%, rgba(16, 185, 129, 0.22), rgba(16, 185, 129, 0) 58%),
      linear-gradient(135deg, rgba(7, 89, 133, 0.92), rgba(15, 23, 42, 0.9));
  }

  .music-release-hero__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .music-release-hero__bg::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0;
    background-image: var(--cover);
    background-size: cover;
    background-position: center;
    filter: blur(30px) saturate(1.02);
    transform: scale(1.22);
  }

  .music-release-hero__bg[style*='--cover']::before {
    opacity: 0.26;
  }

  .music-release-hero__body {
    position: relative;
    z-index: 1;
    display: grid;
    grid-template-columns: minmax(0, 180px) minmax(0, 1fr);
    gap: 1rem;
    padding: 1rem;
    align-items: start;
  }

  .music-release-hero__cover {
    width: 100%;
    max-width: 180px;
    border-radius: 0.9rem;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.2);
    box-shadow: 0 10px 25px rgba(2, 6, 23, 0.45);
    background: rgba(15, 23, 42, 0.35);
  }

  .music-release-hero__cover img {
    display: block;
    width: 100%;
    height: auto;
    object-fit: cover;
    aspect-ratio: 1 / 1;
  }

  .music-release-hero__content {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    color: #e2e8f0;
  }

  .music-release-hero__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
  }

  .music-release-chip {
    border-radius: 9999px;
    border: 1px solid rgba(125, 211, 252, 0.45);
    background: rgba(15, 23, 42, 0.45);
    padding: 0.25rem 0.6rem;
    font-size: 0.75rem;
    line-height: 1.1;
    color: #bae6fd;
  }

  .music-release-hero__title {
    margin: 0;
    font-size: clamp(1.35rem, 2.1vw, 1.95rem);
    line-height: 1.15;
    color: #fff;
    font-weight: 700;
    text-wrap: balance;
  }

  .music-release-hero__subtitle {
    margin: 0;
    color: #d1fae5;
    font-size: 0.98rem;
  }

  .music-release-hero__meta {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.55rem;
    margin-top: 0.25rem;
  }

  .music-release-meta-item {
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 0.75rem;
    background: rgba(15, 23, 42, 0.4);
    padding: 0.55rem 0.7rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .music-release-meta-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #bae6fd;
  }

  .music-release-meta-value {
    color: #f0fdfa;
    font-size: 0.9rem;
    line-height: 1.3;
  }

  .music-release-meta-link {
    color: #34d399;
    font-size: 0.9rem;
    line-height: 1.3;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  .music-release-meta-link:hover {
    color: #6ee7b7;
  }

  .music-release-hero__player {
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 0.85rem;
    overflow: hidden;
    background: rgba(15, 23, 42, 0.45);
    margin-top: 0.2rem;
  }

  .music-release-player__frame {
    display: block;
    width: 100%;
    height: var(--player-height, 180px);
    border: 0;
  }

  @media (max-width: 760px) {
    .music-release-hero__body {
      grid-template-columns: 1fr;
    }

    .music-release-hero__cover {
      max-width: 160px;
    }
  }
</style>
