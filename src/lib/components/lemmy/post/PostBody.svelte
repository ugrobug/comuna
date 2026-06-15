<script lang="ts">
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import type { View } from '$lib/settings'
  import { toast } from 'mono-svelte'
  import { ChevronDown, Icon } from 'svelte-hero-icons'
  import { browser } from '$app/environment'
  import { afterUpdate, createEventDispatcher, onMount, tick } from 'svelte'
  import { page } from '$app/stores'
  import {
    parseSerializedEditorModel,
    looksLikeSerializedEditorModel,
    buildOpenStreetMapEmbedUrl,
    normalizeOpenStreetMapZoom,
  } from '$lib/util'
  import {
    buildPostDetailUrl,
    buildPostPollVoteUrl,
    buildPostRatingVoteUrl,
    type BackendPoll,
    type BackendPollOption,
    type BackendPostRating,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import {
    formatMovieReviewReleaseDate,
    movieReviewAuthorRatingLabel,
    movieReviewAuthorRatingTone,
    isMovieReviewTemplate,
    isTemplateEditorBlockEnabled,
    movieReviewGenreLabel,
    movieReviewKindLabel,
    movieReviewWatchWhereLabels,
    type SitePostTemplate,
  } from '$lib/postTemplates'
  import {
    normalizePostLinkBlockData,
    normalizeInternalPostReference,
    type PostLinkSnapshot,
  } from '$lib/postLinkBlocks'
  import {
    showImage,
    type ExpandableImageGalleryItem,
  } from '$lib/components/ui/ExpandableImage.svelte'
  import { buildAuthorPublicPath, normalizeAuthorBlockData } from '$lib/authorBlocks'
  import { renderQuoteBlockHtml } from '$lib/quoteBlock'
  import { sanitizePostHtml as sanitizePostHtmlUniversal } from '$lib/security/html'
  
  let DOMPurify: any
  let purifyConfigured = false
  
  if (browser) {
    // Динамический импорт DOMPurify только на клиенте
    import('dompurify').then(module => {
      DOMPurify = module.default
      if (!purifyConfigured) {
        DOMPurify.addHook('afterSanitizeAttributes', (node: Element) => {
          if (node.tagName === 'A') {
            const href = node.getAttribute('href') || ''
            if (href.includes('t.me/')) {
              const rel = node.getAttribute('rel') || ''
              const relParts = new Set(rel.split(/\s+/).filter(Boolean))
              relParts.add('nofollow')
              relParts.add('noopener')
              node.setAttribute('rel', Array.from(relParts).join(' '))
            }
          }
          if (node.tagName === 'IFRAME') {
            const src = node.getAttribute('src') || ''
            const isTelegram = src.startsWith('https://t.me/')
            const isOpenStreetMap = src.startsWith('https://www.openstreetmap.org/export/embed.html')
            const isSpotify = src.startsWith('https://open.spotify.com/embed/')
            const isSoundCloud = src.startsWith('https://w.soundcloud.com/player/')
            const isYandexMusic =
              src.startsWith('https://music.yandex.ru/iframe/') ||
              src.startsWith('https://music.yandex.com/iframe/')
            if (!isTelegram && !isOpenStreetMap && !isSpotify && !isSoundCloud && !isYandexMusic) {
              node.remove()
              return
            }
            node.setAttribute('loading', 'lazy')
            if (!node.getAttribute('allow')) {
              node.setAttribute(
                'allow',
                'autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture'
              )
            }
            const referrerPolicy =
              isOpenStreetMap || isSpotify || isSoundCloud || isYandexMusic
                ? 'no-referrer-when-downgrade'
                : 'no-referrer'
            node.setAttribute('referrerpolicy', referrerPolicy)
          }
        })
        purifyConfigured = true
      }
    })
  }

  export let body: string
  export let postId: number | null = null
  export let allowPollVoting = false
  export let poll: BackendPoll | null = null
  export let postRatings: Record<string, BackendPostRating> | null = null
  export let title: string | undefined = undefined
  export let template: SitePostTemplate | null | undefined = null
  export let view: View = 'cozy'
  export let clickThrough = false
  export let showFullBody = false
  export let collapsible = false
  export let canExpandPreview = false
  export let externalPreviewImageUrl: string | null | undefined = null
  export let ratingVoteUrl: string | null = null
  $: void view
  $: void clickThrough
  
  let htmlElement = 'div'

  export { htmlElement as element }

  const dispatch = createEventDispatcher<{ expand: void; rating: BackendPostRating }>()

  let expanded = false
  let hasOverflow = false
  let hadOverflow = false
  let previewCanExpand = false
  let previewWasTrimmed = false
  let fullBody: string | null = null
  let fullBodyLoading = false
  let fullBodyLoadFailed = false
  let bodySourceKey = ''
  let element: Element
  let isFirstImage = true;
  let firstImageUrl: string | null = null;
  let firstImageSrcset: string | null = null;
  let hasPreview = false;
  let lastProcessedBody = '';
  let processedBody = '';
  let localPoll: BackendPoll | null = null
  let lastPollRef: BackendPoll | null = null
  let pollVoting = false
  let pollRenderState = ''
  let localPostRatings: Record<string, BackendPostRating> = {}
  let lastPostRatingsRef: Record<string, BackendPostRating> | null = null
  let postRatingsVoting = false
  let postRatingsRenderState = ''
  let pollRestoreInFlight = false
  let restoredPollToken: string | null = null
  const activeGlossaryTermClass = 'post-glossary-term--active'
  const maxPreviewLength = 250;
  const hydratedPostLinkSnapshots = new Map<number, PostLinkSnapshot>()
  type TocEntry = { id: string; text: string; level: 2 | 3 }

  const clonePollOption = (option: BackendPollOption): BackendPollOption => ({ ...option })

  const clonePoll = (value: BackendPoll | null | undefined): BackendPoll | null =>
    value
      ? {
          ...value,
          options: Array.isArray(value.options) ? value.options.map(clonePollOption) : [],
          user_selection: Array.isArray(value.user_selection) ? [...value.user_selection] : [],
        }
      : null

  const clonePostRating = (value: BackendPostRating | null | undefined): BackendPostRating | null =>
    value ? { ...value } : null

  const normalizePostRatingsMap = (
    value: Record<string, BackendPostRating> | null | undefined
  ): Record<string, BackendPostRating> => {
    if (!value || typeof value !== 'object') return {}
    return Object.fromEntries(
      Object.entries(value)
        .map(([blockId, rating]) => {
          const key = String(blockId || '').trim()
          if (!key) return null
          const cloned = clonePostRating(rating)
          if (!cloned) return null
          return [key, cloned]
        })
        .filter(Boolean) as Array<[string, BackendPostRating]>
    )
  }

  const mergeServerPollWithSelection = (
    serverPoll: BackendPoll | null,
    fallbackSelection: number[]
  ): BackendPoll | null => {
    const cloned = clonePoll(serverPoll)
    if (!cloned) return null
    const normalizedFallback = normalizePollSelection(fallbackSelection)
    const normalizedServerSelection = normalizePollSelection(cloned.user_selection ?? [])
    if (!normalizedServerSelection.length && normalizedFallback.length) {
      cloned.user_selection = normalizedFallback
    }
    return cloned
  }

  const storageKeyForPoll = (value: number | null | undefined): string => {
    const normalizedPostId = Number(value)
    if (!Number.isInteger(normalizedPostId) || normalizedPostId <= 0) return ''
    return `comuna:inline-poll:${normalizedPostId}`
  }

  const getPollIdentity = (value: BackendPoll | null | undefined): string => {
    const pollId = String(value?.id || '').trim()
    if (pollId) return pollId
    const questionValue = String(value?.question || '').trim()
    const optionsValue = Array.isArray(value?.options)
      ? value.options.map((option) => String(option?.text || '').trim()).join('|')
      : ''
    return `${questionValue}::${optionsValue}`
  }

  const clearActiveGlossaryTerms = () => {
    if (!element) return
    element
      .querySelectorAll(`.${activeGlossaryTermClass}`)
      .forEach((item) => item.classList.remove(activeGlossaryTermClass))
  }

  const positionGlossaryTermTooltip = (termElement: HTMLElement) => {
    if (!browser) return
    const definition = String(termElement.getAttribute('data-glossary-definition') || '').trim()
    const termRect = termElement.getBoundingClientRect()
    const contentRect =
      termElement.closest('.post-content')?.getBoundingClientRect() ??
      element?.getBoundingClientRect()
    if (!definition || !contentRect) return

    const viewportMargin = 12
    const contentMargin = 8
    const minLeft = Math.max(contentRect.left + contentMargin, viewportMargin)
    const maxRight = Math.min(contentRect.right - contentMargin, window.innerWidth - viewportMargin)
    const availableWidth = Math.max(180, maxRight - minLeft)
    const maxTooltipWidth = Math.min(352, window.innerWidth - viewportMargin * 2, availableWidth)
    const measureElement = document.createElement('span')
    measureElement.textContent = definition
    measureElement.style.position = 'fixed'
    measureElement.style.left = '-10000px'
    measureElement.style.top = '-10000px'
    measureElement.style.visibility = 'hidden'
    measureElement.style.whiteSpace = 'nowrap'
    measureElement.style.fontSize = '0.82rem'
    measureElement.style.fontWeight = '400'
    document.body.appendChild(measureElement)
    const measuredTextWidth = measureElement.getBoundingClientRect().width
    measureElement.remove()

    const tooltipHorizontalPadding = 28
    const tooltipWidth = Math.min(
      maxTooltipWidth,
      Math.max(96, Math.ceil(measuredTextWidth + tooltipHorizontalPadding))
    )
    const termCenter = termRect.left + termRect.width / 2
    const defaultLeft = termCenter - tooltipWidth / 2
    const maxLeft = maxRight - tooltipWidth
    const clampedLeft = Math.min(Math.max(defaultLeft, minLeft), maxLeft)
    const shiftX = Math.round(clampedLeft - defaultLeft)

    termElement.style.setProperty('--post-glossary-tooltip-width', `${Math.round(tooltipWidth)}px`)
    termElement.style.setProperty('--post-glossary-tooltip-shift-x', `${shiftX}px`)
  }

  const handlePostContentPointerOver = (event: PointerEvent) => {
    const target = event.target as HTMLElement | null
    const termElement = target?.closest('.post-glossary-term') as HTMLElement | null
    if (termElement && element?.contains(termElement)) {
      positionGlossaryTermTooltip(termElement)
    }
  }

  const handlePostContentFocusIn = (event: FocusEvent) => {
    const target = event.target as HTMLElement | null
    const termElement = target?.closest('.post-glossary-term') as HTMLElement | null
    if (termElement && element?.contains(termElement)) {
      positionGlossaryTermTooltip(termElement)
    }
  }

  const refreshActiveGlossaryTooltips = () => {
    if (!element) return
    element
      .querySelectorAll(`.${activeGlossaryTermClass}`)
      .forEach((item) => positionGlossaryTermTooltip(item as HTMLElement))
  }

  const handlePostContentClick = (event: MouseEvent) => {
    const target = event.target as HTMLElement | null
    const termElement = target?.closest('.post-glossary-term') as HTMLElement | null
    if (!termElement || !element?.contains(termElement)) {
      clearActiveGlossaryTerms()
      return
    }

    event.preventDefault()
    event.stopPropagation()
    const wasActive = termElement.classList.contains(activeGlossaryTermClass)
    clearActiveGlossaryTerms()
    if (!wasActive) {
      positionGlossaryTermTooltip(termElement)
      termElement.classList.add(activeGlossaryTermClass)
    }
  }

  const glossaryTermClickHandler = (node: Element) => {
    node.addEventListener('click', handlePostContentClick as EventListener)
    node.addEventListener('pointerover', handlePostContentPointerOver as EventListener)
    node.addEventListener('focusin', handlePostContentFocusIn as EventListener)
    window.addEventListener('resize', refreshActiveGlossaryTooltips)
    return {
      destroy() {
        node.removeEventListener('click', handlePostContentClick as EventListener)
        node.removeEventListener('pointerover', handlePostContentPointerOver as EventListener)
        node.removeEventListener('focusin', handlePostContentFocusIn as EventListener)
        window.removeEventListener('resize', refreshActiveGlossaryTooltips)
      },
    }
  }

  const persistLocalPoll = (value: BackendPoll | null | undefined) => {
    if (!browser) return
    const storageKey = storageKeyForPoll(postId)
    if (!storageKey) return
    if (!value) {
      localStorage.removeItem(storageKey)
      return
    }
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ poll: clonePoll(value), identity: getPollIdentity(value) })
      )
    } catch (error) {
      console.error('Failed to persist inline poll state:', error)
    }
  }

  const readStoredPoll = (): BackendPoll | null => {
    if (!browser) return null
    const storageKey = storageKeyForPoll(postId)
    if (!storageKey) return null
    try {
      const raw = localStorage.getItem(storageKey)
      if (!raw) return null
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || !parsed.poll || typeof parsed.poll !== 'object') {
        return null
      }
      const parsedPoll = clonePoll(parsed.poll as BackendPoll)
      if (!parsedPoll) return null
      const currentIdentity = getPollIdentity(poll)
      const storedIdentity =
        typeof parsed.identity === 'string' && parsed.identity.trim()
          ? parsed.identity.trim()
          : getPollIdentity(parsedPoll)
      if (currentIdentity && storedIdentity && currentIdentity !== storedIdentity) {
        localStorage.removeItem(storageKey)
        return null
      }
      return parsedPoll
    } catch (error) {
      console.error('Failed to read inline poll state:', error)
      return null
    }
  }

  const applyLocalPollState = (value: BackendPoll | null | undefined) => {
    localPoll = clonePoll(value)
    persistLocalPoll(localPoll)
    processedBody = extractPreviewContent(body)
  }

  const normalizePollSelection = (selection: number[]): number[] =>
    Array.from(
      new Set(
        selection
          .map((value) => Number(value))
          .filter((value) => Number.isInteger(value) && value >= 0)
      )
    ).sort((a, b) => a - b)

  const applyOptimisticPollSelection = (
    source: BackendPoll | null,
    nextSelection: number[]
  ): BackendPoll | null => {
    if (!source) return null

    const previousSelection = new Set(normalizePollSelection(source.user_selection ?? []))
    const nextSelectionSet = new Set(normalizePollSelection(nextSelection))
    const nextPoll = clonePoll(source)
    if (!nextPoll) return null

    nextPoll.options = nextPoll.options.map((option, index) => {
      let voterCount = Math.max(Number(option.voter_count || 0), 0)
      if (previousSelection.has(index) && !nextSelectionSet.has(index)) {
        voterCount = Math.max(0, voterCount - 1)
      }
      if (!previousSelection.has(index) && nextSelectionSet.has(index)) {
        voterCount += 1
      }
      return {
        ...option,
        voter_count: voterCount,
      }
    })

    const hadPreviousVote = previousSelection.size > 0
    const hasNextVote = nextSelectionSet.size > 0
    let totalVoterCount = Math.max(Number(nextPoll.total_voter_count || 0), 0)
    if (!hadPreviousVote && hasNextVote) {
      totalVoterCount += 1
    } else if (hadPreviousVote && !hasNextVote) {
      totalVoterCount = Math.max(0, totalVoterCount - 1)
    }

    nextPoll.total_voter_count = totalVoterCount
    nextPoll.user_selection = Array.from(nextSelectionSet).sort((a, b) => a - b)
    return nextPoll
  }

  const formatPollVoteLabel = (count: number): string => {
    const safeCount = Math.max(0, Math.floor(count))
    const mod10 = safeCount % 10
    const mod100 = safeCount % 100
    if (mod10 === 1 && mod100 !== 11) return `${safeCount} голос`
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
      return `${safeCount} голоса`
    }
    return `${safeCount} голосов`
  }

  const normalizeTextForCompare = (value: string): string =>
    value
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/[.!?]+$/g, '')
      .trim()
      .toLowerCase()

  const matchesInlinePollOptionSet = (left: BackendPollOption[] = [], right: string[] = []): boolean => {
    if (left.length !== right.length) return false
    return left.every((option, index) => normalizeTextForCompare(option.text || '') === normalizeTextForCompare(right[index] || ''))
  }

  $: if (poll !== lastPollRef) {
    lastPollRef = poll
    restoredPollToken = null
    applyLocalPollState(readStoredPoll() ?? poll)
  }

  $: pollRenderState =
    localPoll
      ? JSON.stringify({
          total: localPoll.total_voter_count,
          selected: localPoll.user_selection ?? [],
          options: localPoll.options.map((option) => option.voter_count),
        })
      : ''
  $: if (postRatings !== lastPostRatingsRef) {
    lastPostRatingsRef = postRatings
    localPostRatings = normalizePostRatingsMap(postRatings)
  }
  $: postRatingsRenderState = JSON.stringify(
    Object.entries(localPostRatings)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([blockId, rating]) => [
        blockId,
        Number(rating?.average_value ?? 0),
        Number(rating?.votes_count ?? 0),
        Number(rating?.user_vote ?? 0),
      ])
  )

  const refreshPollFromServer = async (tokenOverride?: string | null) => {
    if (!browser || !allowPollVoting || !postId || pollRestoreInFlight) return
    const token = tokenOverride ?? $siteToken
    if (!token) return

    pollRestoreInFlight = true
    try {
      const response = await fetch(buildPostDetailUrl(postId), {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
      const payload = await response.json().catch(() => null)
      if (response.ok && payload?.post?.poll && typeof payload.post.poll === 'object') {
        applyLocalPollState(payload.post.poll as BackendPoll)
      }
    } catch (error) {
      console.error('Failed to restore inline poll state:', error)
    } finally {
      pollRestoreInFlight = false
    }
  }

  const restoreInlinePollState = async () => {
    if (!browser || !allowPollVoting || !postId) return
    const storedPoll = readStoredPoll()
    if (storedPoll) {
      applyLocalPollState(storedPoll)
    }

    const token = $siteToken
    if (!token || restoredPollToken === token) return
    restoredPollToken = token
    await refreshPollFromServer(token)
  }

  const stripLeadingTitleFromHtml = (html: string): string => {
    const rawTitle = (title || '').trim()
    if (!rawTitle) return html
    const normalizedTitle = normalizeTextForCompare(rawTitle)
    if (!normalizedTitle) return html

    const stripInline = (fragment: string): string => {
      const withoutBreaks = fragment.replace(/<br\s*\/?>/gi, ' ')
      const withoutTags = withoutBreaks.replace(/<[^>]*>/g, ' ')
      return normalizeTextForCompare(withoutTags)
    }

    // Allow a media prefix (image/gallery/figure + <br>) before the title block.
    const mediaPrefixRegex =
      /^\s*(?:(?:<img\b[^>]*>\s*(?:<br\s*\/?>\s*)*)|(?:<figure\b[\s\S]*?<\/figure>\s*(?:<br\s*\/?>\s*)*)|(?:<div\b[^>]*class=(["'])[^"']*\bpost-gallery\b[^"']*\1[^>]*>[\s\S]*?<\/div>\s*(?:<br\s*\/?>\s*)*))*\s*/i
    const prefixMatch = html.match(mediaPrefixRegex)
    const prefix = prefixMatch ? prefixMatch[0] : ''
    const restHtml = html.slice(prefix.length)

    const boldMatch = restHtml.match(/^\s*<(b|strong)>([\s\S]*?)<\/\1>/i)
    if (boldMatch) {
      const inner = stripInline(boldMatch[2] || '')
      if (inner && inner === normalizedTitle) {
        const rest = restHtml
          .slice(boldMatch[0].length)
          .replace(/^\s*(?:<br\s*\/?>\s*)+/i, '')
        return `${prefix}${rest}`
      }
    }

    const pMatch = restHtml.match(/^\s*<p>([\s\S]*?)<\/p>/i)
    if (pMatch) {
      const inner = stripInline(pMatch[1] || '')
      if (inner && inner === normalizedTitle) {
        const rest = restHtml
          .slice(pMatch[0].length)
          .replace(/^\s*(?:<br\s*\/?>\s*)+/i, '')
        return `${prefix}${rest}`
      }
    }

    return html
  }

  const normalizePreviewImageUrl = (url: string | null | undefined): string => {
    const raw = (url || '').trim()
    if (!raw) return ''
    try {
      const parsed = new URL(raw, browser ? window.location.origin : 'https://tambur.local')
      return decodeURIComponent(parsed.pathname)
        .replace(/-\d+\.webp$/i, '')
        .replace(/\.[a-z0-9]+$/i, '')
        .toLowerCase()
    } catch {
      return raw
        .split(/[?#]/, 1)[0]
        .replace(/-\d+\.webp$/i, '')
        .replace(/\.[a-z0-9]+$/i, '')
        .toLowerCase()
    }
  }

  const isSamePreviewImage = (left: string | null | undefined, right: string | null | undefined) => {
    const leftKey = normalizePreviewImageUrl(left)
    const rightKey = normalizePreviewImageUrl(right)
    return Boolean(leftKey && rightKey && leftKey === rightKey)
  }

  const removeDuplicateLeadingPreviewImage = (html: string): string => {
    if (!externalPreviewImageUrl || showFullBody) return html

    if (browser) {
      const wrapper = document.createElement('div')
      wrapper.innerHTML = html
      const firstImage = wrapper.querySelector('img')
      const imageUrl = firstImage?.getAttribute('data-expandable-src') || firstImage?.getAttribute('src')
      if (!firstImage || !isSamePreviewImage(imageUrl, externalPreviewImageUrl)) return html

      const parent = firstImage.parentElement
      const nextElement = firstImage.nextElementSibling
      firstImage.remove()
      if (nextElement?.classList.contains('image-alt-text')) {
        nextElement.remove()
      }
      if (parent?.tagName.toLowerCase() === 'figure' && !parent.textContent?.trim()) {
        parent.remove()
      }
      return wrapper.innerHTML
    }

    const firstImageMatch = html.match(/<img\b[^>]*>/i)
    if (!firstImageMatch) return html
    const tag = firstImageMatch[0]
    const srcMatch = tag.match(/\s(?:data-expandable-src|src)=["']([^"']+)["']/i)
    if (!isSamePreviewImage(srcMatch?.[1], externalPreviewImageUrl)) return html
    return html
      .replace(tag, '')
      .replace(/^\s*<div\b[^>]*class=["'][^"']*\bimage-alt-text\b[^"']*["'][^>]*>[\s\S]*?<\/div>/i, '')
  }

  const shouldRenderInlinePreviewImage = (url: string | null | undefined): boolean => {
    const value = (url || '').trim()
    if (!value) return false
    return !externalPreviewImageUrl
  }

  const setupGalleries = () => {
    if (!browser || !element) return;
    const galleries = element.querySelectorAll('.post-gallery');

    const fullMode = showFullBody || (collapsible && expanded)
    const mode = fullMode ? 'full' : 'preview';
    galleries.forEach((gallery) => {
      if (gallery.getAttribute('data-gallery-ready') === mode) {
        return;
      }
      gallery.setAttribute('data-gallery-ready', mode);

      const images = Array.from(gallery.querySelectorAll('img'));
      if (!images.length) return;

      if (!fullMode) {
        // Keep all images in DOM so we can re-build the gallery when user expands,
        // but visually show only the first one in preview mode.
        images.forEach((img, index) => {
          if (!(img instanceof HTMLElement)) return;
          if (index === 0) {
            img.style.display = '';
            img.removeAttribute('data-preview-hidden');
          } else {
            img.style.display = 'none';
            img.setAttribute('data-preview-hidden', '1');
          }
        });
        return;
      }

      const getImgAttr = (img: Element, name: string) => {
        return img.getAttribute(name) || '';
      };

      const mainWrapper = document.createElement('div');
      mainWrapper.className = 'featured-gallery-main';

      const mainImage = document.createElement('img');
      const first = images[0];
      mainImage.src = getImgAttr(first, 'src');
      const firstExpandedSrc = getImgAttr(first, 'data-expandable-src');
      const firstSrcset = getImgAttr(first, 'srcset');
      if (firstSrcset) {
        mainImage.setAttribute('srcset', firstSrcset);
      }
      const firstSizes = getImgAttr(first, 'sizes');
      if (firstSizes) {
        mainImage.setAttribute('sizes', firstSizes);
      }
      mainImage.alt = getImgAttr(first, 'alt');
      mainImage.setAttribute('data-expandable-image', '1');
      if (firstExpandedSrc) {
        mainImage.setAttribute('data-expandable-src', firstExpandedSrc);
      }
      mainWrapper.appendChild(mainImage);

      const thumbs = document.createElement('div');
      thumbs.className = 'featured-gallery-thumbs';

      const updateMain = (img: Element, btn: HTMLButtonElement) => {
        mainImage.src = getImgAttr(img, 'src');
        const srcset = getImgAttr(img, 'srcset');
        if (srcset) {
          mainImage.setAttribute('srcset', srcset);
        } else {
          mainImage.removeAttribute('srcset');
        }
        const sizes = getImgAttr(img, 'sizes');
        if (sizes) {
          mainImage.setAttribute('sizes', sizes);
        } else {
          mainImage.removeAttribute('sizes');
        }
        mainImage.alt = getImgAttr(img, 'alt');
        const expandedSrc = getImgAttr(img, 'data-expandable-src');
        if (expandedSrc) {
          mainImage.setAttribute('data-expandable-src', expandedSrc);
        } else {
          mainImage.removeAttribute('data-expandable-src');
        }
        thumbs.querySelectorAll('.featured-gallery-thumb').forEach((item) => {
          item.classList.remove('active');
        });
        btn.classList.add('active');
      };

      images.forEach((img, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'featured-gallery-thumb';

        const thumb = document.createElement('img');
        thumb.src = getImgAttr(img, 'src');
        const srcset = getImgAttr(img, 'srcset');
        if (srcset) {
          thumb.setAttribute('srcset', srcset);
        }
        const sizes = getImgAttr(img, 'sizes');
        if (sizes) {
          thumb.setAttribute('sizes', sizes);
        }
        thumb.alt = getImgAttr(img, 'alt');
        thumb.loading = 'lazy';

        btn.appendChild(thumb);
        btn.addEventListener('click', () => updateMain(img, btn));

        if (index === 0) {
          btn.classList.add('active');
        }
        thumbs.appendChild(btn);
      });

      gallery.innerHTML = '';
      gallery.classList.add('featured-gallery');
      gallery.appendChild(mainWrapper);
      gallery.appendChild(thumbs);
    });
  };

  const setupImageComparisons = () => {
    if (!browser || !element) return
    const comparisons = element.querySelectorAll('.post-image-compare')

    const clampPosition = (value: unknown): number => {
      const parsed = Number(value)
      if (!Number.isFinite(parsed)) return 50
      return Math.min(95, Math.max(5, Math.round(parsed)))
    }

    comparisons.forEach((node) => {
      if (!(node instanceof HTMLElement)) return

      const viewport = node.querySelector('.post-image-compare__viewport') as HTMLElement | null
      const overlay = node.querySelector('.post-image-compare__overlay') as HTMLElement | null
      const divider = node.querySelector('.post-image-compare__divider') as HTMLElement | null
      if (!viewport || !overlay || !divider) return

      const applyPosition = (value: unknown) => {
        const safe = clampPosition(value)
        const rightInset = 100 - safe
        const clipRule = `inset(0 ${rightInset}% 0 0)`
        overlay.style.clipPath = clipRule
        ;(overlay.style as CSSStyleDeclaration & { webkitClipPath?: string }).webkitClipPath = clipRule
        divider.style.left = `${safe}%`
        node.setAttribute('data-compare-position', String(safe))
      }

      const updateFromClientX = (clientX: number) => {
        const rect = viewport.getBoundingClientRect()
        if (!rect.width) return
        const next = ((clientX - rect.left) / rect.width) * 100
        applyPosition(next)
      }

      if (node.getAttribute('data-compare-ready') !== '1') {
        let isDragging = false

        const onPointerMove = (event: PointerEvent) => {
          if (!isDragging) return
          event.preventDefault()
          updateFromClientX(event.clientX)
        }

        const stopDrag = () => {
          if (!isDragging) return
          isDragging = false
          node.removeAttribute('data-compare-dragging')
          window.removeEventListener('pointermove', onPointerMove)
          window.removeEventListener('pointerup', stopDrag)
          window.removeEventListener('pointercancel', stopDrag)
        }

        const startDrag = (event: PointerEvent) => {
          if (event.button !== 0 && event.pointerType !== 'touch') return
          event.preventDefault()
          isDragging = true
          node.setAttribute('data-compare-dragging', '1')
          updateFromClientX(event.clientX)
          window.addEventListener('pointermove', onPointerMove)
          window.addEventListener('pointerup', stopDrag)
          window.addEventListener('pointercancel', stopDrag)
        }

        viewport.addEventListener('pointerdown', startDrag)
        node.setAttribute('data-compare-ready', '1')
      }

      applyPosition(node.getAttribute('data-compare-position') ?? 50)
    })
  }

  const isExpandableImage = (image: HTMLImageElement | null): image is HTMLImageElement => {
    if (!image || !element?.contains(image)) return false
    if (
      image.closest(
        '.post-image-compare, .post-map, .post-quote__author, .featured-gallery-thumb, [data-post-link-id]'
      )
    ) {
      return false
    }
    return true
  }

  const expandableImageUrl = (image: HTMLImageElement) =>
    image.getAttribute('data-expandable-src') ||
    image.getAttribute('src') ||
    image.currentSrc ||
    ''

  const expandableImageItem = (image: HTMLImageElement): ExpandableImageGalleryItem | null => {
    const url = expandableImageUrl(image)
    if (!url) return null
    return {
      url,
      alt: image.getAttribute('alt') || image.getAttribute('title') || '',
    }
  }

  const galleryItemsForImage = (image: HTMLImageElement): ExpandableImageGalleryItem[] => {
    const gallery = image.closest('.post-gallery')
    const galleryImages = gallery?.classList.contains('featured-gallery')
      ? Array.from(gallery.querySelectorAll('.featured-gallery-thumb img'))
      : gallery
        ? Array.from(gallery.querySelectorAll('img'))
        : []
    const sourceImages = galleryImages.length
      ? galleryImages
      : element
        ? Array.from(element.querySelectorAll('img')).filter((candidate) =>
            isExpandableImage(candidate as HTMLImageElement | null)
          )
        : [image]

    return sourceImages
      .filter((candidate): candidate is HTMLImageElement => candidate instanceof HTMLImageElement)
      .map(expandableImageItem)
      .filter((item): item is ExpandableImageGalleryItem => Boolean(item?.url))
  }

  const openExpandedImage = (image: HTMLImageElement) => {
    const src = expandableImageUrl(image)
    if (!src) return
    showImage(src, image.getAttribute('alt') || image.getAttribute('title') || '', galleryItemsForImage(image))
  }

  const loadFullBodyForExpand = async (): Promise<boolean> => {
    if (!browser || showFullBody || !collapsible || !postId || fullBody !== null) return true
    if (fullBodyLoading) return false

    fullBodyLoading = true
    fullBodyLoadFailed = false
    try {
      const token = $siteToken
      const response = await fetch(buildPostDetailUrl(postId), {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const payload = await response.json().catch(() => null)
      const nextBody = typeof payload?.post?.content === 'string' ? payload.post.content : ''
      if (!response.ok || !nextBody) {
        throw new Error(payload?.error || 'Failed to load post body')
      }
      fullBody = nextBody
      if (payload?.post?.poll && typeof payload.post.poll === 'object') {
        applyLocalPollState(payload.post.poll as BackendPoll)
      }
      if (payload?.post?.post_ratings && typeof payload.post.post_ratings === 'object') {
        localPostRatings = normalizePostRatingsMap(payload.post.post_ratings)
      }
      return true
    } catch (error) {
      console.error('Failed to load full post body:', error)
      fullBodyLoadFailed = true
      toast({ content: 'Не удалось загрузить полный текст поста', type: 'error' })
      return false
    } finally {
      fullBodyLoading = false
    }
  }

  const expand = async (event?: Event) => {
    event?.preventDefault()
    event?.stopPropagation()
    if (expanded || fullBodyLoading) return
    const loaded = await loadFullBodyForExpand()
    if (!loaded) return
    expanded = true
    hasOverflow = false
    dispatch('expand')
    if (browser) {
      await tick()
      setTimeout(setupGalleries, 0)
      setTimeout(setupImageComparisons, 0)
    }
  }

  const collapse = async (event?: Event) => {
    event?.preventDefault()
    event?.stopPropagation()
    if (!expanded || !hadOverflow) return
    expanded = false
    hasOverflow = true
    if (browser) {
      await tick()
      setTimeout(setupGalleries, 0)
      setTimeout(setupImageComparisons, 0)
    }
  }

  const toggleExpand = async (event?: Event) => {
    if (expanded) {
      await collapse(event)
      return
    }
    await expand(event)
  }

  const getSelectedPollOptions = (pollElement: HTMLElement): number[] => {
    const selected = new Set<number>()
    pollElement
      .querySelectorAll<HTMLElement>('.post-poll-option.is-selected')
      .forEach((item) => {
        const raw = item.getAttribute('data-option-index')
        const index = raw === null ? Number.NaN : Number(raw)
        if (Number.isInteger(index) && index >= 0) {
          selected.add(index)
        }
      })
    return Array.from(selected).sort((a, b) => a - b)
  }

  const submitPollVote = async (pollElement: HTMLElement, nextSelection: number[]) => {
    if (!allowPollVoting || !postId) return
    const token = $siteToken
    if (!token) {
      toast({ content: 'Необходимо зарегистрироваться', type: 'warning' })
      return
    }

    const previousPollState = clonePoll(localPoll ?? poll)
    const optimisticPoll = applyOptimisticPollSelection(previousPollState, nextSelection)
    if (optimisticPoll) {
      applyLocalPollState(optimisticPoll)
    }
    pollVoting = true
    try {
      const response = await fetch(buildPostPollVoteUrl(postId), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ options: nextSelection }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data?.ok) {
        if (data?.poll && typeof data.poll === 'object') {
          applyLocalPollState(mergeServerPollWithSelection(data.poll as BackendPoll, nextSelection))
        }
        throw new Error(data?.error || 'Не удалось проголосовать')
      }
      if (data?.poll && typeof data.poll === 'object') {
        applyLocalPollState(mergeServerPollWithSelection(data.poll as BackendPoll, nextSelection))
      }
      await refreshPollFromServer(token)
    } catch (error) {
      if ((error as Error)?.message !== 'Вы уже проголосовали в этом опросе') {
        applyLocalPollState(previousPollState)
      }
      toast({
        content: (error as Error)?.message ?? 'Не удалось проголосовать',
        type: 'error',
      })
    } finally {
      pollVoting = false
    }
  }

  const handlePollClick = async (event: Event) => {
    if (!browser || !allowPollVoting || !postId || !element) return
    const target = event.target as HTMLElement | null
    if (!target) return
    const option = target.closest('.post-poll-option') as HTMLElement | null
    if (!option) return
    const pollElement = option.closest('.post-poll') as HTMLElement | null
    if (!pollElement || !element.contains(pollElement)) return

    event.preventDefault()
    event.stopPropagation()

    if (pollVoting || pollElement.getAttribute('data-poll-voting') === '1') return
    if (pollElement.getAttribute('data-poll-locked') === '1') return
    if (pollElement.getAttribute('data-poll-closed') === '1') {
      toast({ content: 'Опрос завершен', type: 'warning' })
      return
    }

    const rawOptionIndex = option.getAttribute('data-option-index')
    const optionIndex = rawOptionIndex === null ? Number.NaN : Number(rawOptionIndex)
    if (!Number.isInteger(optionIndex) || optionIndex < 0) return

    const multiple = pollElement.getAttribute('data-poll-multiple') === '1'
    const selected = getSelectedPollOptions(pollElement)
    const next = new Set(selected)

    if (multiple) {
      if (next.has(optionIndex)) {
        next.delete(optionIndex)
      } else {
        next.add(optionIndex)
      }
    } else if (next.has(optionIndex) && next.size === 1) {
      next.clear()
    } else {
      next.clear()
      next.add(optionIndex)
    }

    await submitPollVote(pollElement, Array.from(next).sort((a, b) => a - b))
  }

  const submitPostRatingVote = async (blockId: string, value: number) => {
    if (!postId) return
    const token = $siteToken
    if (!token) {
      toast({ content: 'Необходимо зарегистрироваться', type: 'warning' })
      return
    }
    if (!Number.isInteger(value) || value < 1 || value > 10 || postRatingsVoting) {
      return
    }

    postRatingsVoting = true
    try {
      const response = await fetch(ratingVoteUrl || buildPostRatingVoteUrl(postId), {
        method: 'POST',
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ block_id: blockId, value }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить оценку')
      }

      const nextBlockId =
        typeof payload?.block_id === 'string' && payload.block_id.trim()
          ? payload.block_id.trim()
          : blockId
      if (payload?.post_rating && typeof payload.post_rating === 'object') {
        localPostRatings = {
          ...localPostRatings,
          [nextBlockId]: { ...(payload.post_rating as BackendPostRating) },
        }
        dispatch('rating', payload.post_rating as BackendPostRating)
      }
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось сохранить оценку',
        type: 'error',
      })
    } finally {
      postRatingsVoting = false
    }
  }

  const handlePostRatingClick = async (event: Event) => {
    if (!browser || !postId || !element) return
    const target = event.target as HTMLElement | null
    if (!target) return
    const button = target.closest('.post-inline-rating__item') as HTMLElement | null
    if (!button) return
    const ratingElement = button.closest('[data-rating-block-id]') as HTMLElement | null
    if (!ratingElement || !element.contains(ratingElement)) return

    event.preventDefault()
    event.stopPropagation()

    const blockId = String(ratingElement.getAttribute('data-rating-block-id') || '').trim()
    const rawValue = button.getAttribute('data-rating-value')
    const value = rawValue === null ? Number.NaN : Number(rawValue)
    if (!blockId || !Number.isInteger(value)) return

    await submitPostRatingVote(blockId, value)
  }

  const openMapModal = (mapElement: HTMLElement) => {
    if (!browser) return
    const frame = mapElement.querySelector('iframe') as HTMLIFrameElement | null
    const source = frame?.getAttribute('src')
    if (!source) return
    if (document.querySelector('.post-map-modal')) return

    const modal = document.createElement('div')
    modal.className = 'post-map-modal'
    modal.innerHTML = `
      <div class="post-map-modal__backdrop"></div>
      <div class="post-map-modal__content">
        <iframe
          class="post-map-modal__frame"
          src="${source}"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          allowfullscreen
          frameborder="0"
          title="Карта OpenStreetMap"
        ></iframe>
        <button type="button" class="post-map-modal__close" aria-label="Закрыть карту">✕</button>
      </div>
    `

    const previousOverflow = document.body.style.overflow

    const close = () => {
      modal.remove()
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', onKeydown)
    }

    const onKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close()
    }

    modal.querySelector('.post-map-modal__backdrop')?.addEventListener('click', close)
    modal.querySelector('.post-map-modal__close')?.addEventListener('click', close)
    document.addEventListener('keydown', onKeydown)

    document.body.style.overflow = 'hidden'
    document.body.appendChild(modal)
  }

  const toggleSpoilerBlock = (spoiler: HTMLElement) => {
    if (!element?.contains(spoiler)) return
    const isOpen = spoiler.classList.toggle('is-open')
    spoiler.setAttribute('data-spoiler-open', isOpen ? '1' : '0')
    const trigger = spoiler.querySelector('.post-spoiler__trigger') as HTMLElement | null
    if (!trigger) return
    trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false')
    const hint = trigger.querySelector('.post-spoiler__hint') as HTMLElement | null
    if (hint) {
      hint.textContent = isOpen ? 'Нажмите, чтобы скрыть' : 'Нажмите, чтобы раскрыть'
    }
  }

  const applyHydratedPostLinkSnapshot = (wrapper: HTMLElement, snapshot: PostLinkSnapshot) => {
    const anchor = wrapper.querySelector('.post-linked-material__card') as HTMLAnchorElement | null
    if (anchor && snapshot.path) {
      anchor.setAttribute('href', snapshot.path)
    }

    const titleElement = wrapper.querySelector('[data-post-link-title]') as HTMLElement | null
    if (titleElement && snapshot.title) {
      titleElement.textContent = snapshot.title
    }

    const textElement = wrapper.querySelector('[data-post-link-text]') as HTMLElement | null
    if (textElement) {
      const nextText = (snapshot.preview_text || '').trim()
      if (nextText) {
        textElement.textContent = nextText
        textElement.removeAttribute('hidden')
      } else {
        textElement.textContent = ''
        textElement.setAttribute('hidden', 'hidden')
      }
    }

    const imageContainer = wrapper.querySelector('[data-post-link-image]') as HTMLElement | null
    if (imageContainer) {
      const imageUrl = (snapshot.preview_image_url || '').trim()
      const imageTitle = (snapshot.title || 'Превью поста').trim()
      if (imageUrl) {
        imageContainer.removeAttribute('hidden')
        imageContainer.innerHTML = `<img src="${escapeHtml(imageUrl)}" alt="${escapeHtml(imageTitle)}" loading="lazy" />`
        anchor?.classList.remove('post-linked-material__card--no-image')
      } else {
        imageContainer.innerHTML = ''
        imageContainer.setAttribute('hidden', 'hidden')
      }
    }

    wrapper.removeAttribute('data-post-link-needs-hydration')
    wrapper.setAttribute('data-post-link-hydrated', '1')
  }

  const fetchPostLinkSnapshotFromPage = async (
    path: string,
    postId: number
  ): Promise<PostLinkSnapshot | null> => {
    if (!browser || !path) return null

    try {
      const response = await fetch(path, { credentials: 'include' })
      if (!response.ok) return null

      const html = await response.text()
      const parser = new DOMParser()
      const doc = parser.parseFromString(html, 'text/html')

      const readMeta = (selector: string) =>
        (doc.querySelector(selector)?.getAttribute('content') || '').trim()

      const ogTitle = readMeta('meta[property="og:title"]')
      const rawTitle = ogTitle || doc.querySelector('h1')?.textContent?.trim() || ''
      const title = rawTitle.replace(/\s+—\s+(?:Comuna|Тамбур)\s*$/i, '').trim()

      const previewText =
        readMeta('meta[property="og:description"]') ||
        readMeta('meta[name="description"]') ||
        ''
      const previewImageUrl = readMeta('meta[property="og:image"]')

      if (!title && !previewText && !previewImageUrl) return null

      return {
        post_id: postId,
        path,
        title,
        author_title: '',
        author_username: '',
        preview_text: previewText || undefined,
        preview_image_url: previewImageUrl || undefined,
      }
    } catch (error) {
      console.error('Failed to fetch post link snapshot from page', error)
      return null
    }
  }

  const hydratePostLinkCards = async () => {
    if (!browser || !element) return

    const wrappers = Array.from(
      element.querySelectorAll('[data-post-link-id][data-post-link-needs-hydration="1"]')
    ) as HTMLElement[]

    await Promise.all(
      wrappers.map(async (wrapper) => {
        const postId = Number(wrapper.getAttribute('data-post-link-id') || '')
        if (!Number.isFinite(postId) || postId <= 0) return

        const cached = hydratedPostLinkSnapshots.get(postId)
        if (cached) {
          applyHydratedPostLinkSnapshot(wrapper, cached)
          return
        }

        try {
          const anchor = wrapper.querySelector('.post-linked-material__card') as HTMLAnchorElement | null
          const path = (anchor?.getAttribute('href') || '').trim()
          const snapshot = await fetchPostLinkSnapshotFromPage(path, postId)
          if (!snapshot) return
          hydratedPostLinkSnapshots.set(postId, snapshot)
          applyHydratedPostLinkSnapshot(wrapper, snapshot)
        } catch (error) {
          console.error('Failed to hydrate post link card', error)
        }
      })
    )
  }

  // Функция для добавления preload в head
  function addPreloadLink(url: string, srcset: string | null = null) {
    if (!browser) return;
    
    // Удаляем предыдущий preload, если он есть
    const existingLink = document.querySelector('link[rel="preload"][as="image"][data-post-image]');
    if (existingLink) {
      existingLink.remove();
    }

    const link = document.createElement('link');
    link.rel = 'preload';
    link.as = 'image';
    link.href = url;
    link.setAttribute('data-post-image', '');
    if (srcset) {
      link.setAttribute('imagesrcset', srcset);
    }
    // Добавляем высокий приоритет
    link.setAttribute('fetchpriority', 'high');
    document.head.appendChild(link);
  }

  function isJsonContent(content: string): boolean {
    return parseSerializedEditorModel(content) !== null
  }

  function processJsonBlock(
    block: any,
    index = -1,
    tocEntriesByIndex: Map<number, TocEntry> = new Map()
  ): string {
    const renderMapBlock = (raw: any): string => {
      const lat = Number(raw?.lat)
      const lng = Number(raw?.lng)
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return ''
      if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return ''
      const zoom = normalizeOpenStreetMapZoom(raw?.zoom, 14)
      const src = buildOpenStreetMapEmbedUrl(lat, lng, zoom)
      return `<div class="post-map">
        <iframe
          class="post-map__frame"
          src="${src}"
          loading="lazy"
          referrerpolicy="no-referrer-when-downgrade"
          allowfullscreen
          frameborder="0"
          title="Карта OpenStreetMap"
        ></iframe>
        <div class="post-map__hint">Нажмите, чтобы открыть карту</div>
      </div>`
    }

    const renderImageCompareBlock = (raw: any): string => {
      const beforeUrl = typeof raw?.before?.url === 'string' ? raw.before.url.trim() : ''
      const afterUrl = typeof raw?.after?.url === 'string' ? raw.after.url.trim() : ''
      if (!beforeUrl || !afterUrl) return ''

      const rawPosition = Number(raw?.position)
      const position = Number.isFinite(rawPosition)
        ? Math.min(95, Math.max(5, Math.round(rawPosition)))
        : 50

      const beforeAlt = escapeHtml(
        typeof raw?.before?.alt === 'string' && raw.before.alt.trim()
          ? raw.before.alt
          : 'Изображение до'
      )
      const beforeTitle = escapeHtml(typeof raw?.before?.title === 'string' ? raw.before.title : '')
      const afterAlt = escapeHtml(
        typeof raw?.after?.alt === 'string' && raw.after.alt.trim()
          ? raw.after.alt
          : 'Изображение после'
      )
      const afterTitle = escapeHtml(typeof raw?.after?.title === 'string' ? raw.after.title : '')
      const caption =
        typeof raw?.caption === 'string' && raw.caption.trim()
          ? `<figcaption class="post-image-compare__caption">${escapeHtml(raw.caption)}</figcaption>`
          : ''

      return `<figure class="post-image-compare" data-compare-position="${position}">
        <div class="post-image-compare__viewport">
          <img
            src="${beforeUrl}"
            alt="${beforeAlt}"
            title="${beforeTitle}"
            class="post-image-compare__image post-image-compare__image--before"
          >
          <div class="post-image-compare__overlay">
            <img
              src="${afterUrl}"
              alt="${afterAlt}"
              title="${afterTitle}"
              class="post-image-compare__image post-image-compare__image--after"
            >
          </div>
          <div class="post-image-compare__divider" aria-hidden="true">
            <span class="post-image-compare__knob"></span>
          </div>
        </div>
        ${caption}
      </figure>`
    }

    const renderMovieCardBlock = (_raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'movie_card')) return ''
      if (!isMovieReviewTemplate(template)) return ''

      const movie = template.data
      const displayTitle = (movie.title || title || '').trim()
      const displayOriginalTitle = (movie.original_title || '').trim()
      const displayGenre = movieReviewGenreLabel(movie.genre)
      const releaseLabel = formatMovieReviewReleaseDate(movie.release_date)
      const authorRatingLabel = movieReviewAuthorRatingLabel(movie.author_rating)
      const authorRatingTone = movieReviewAuthorRatingTone(movie.author_rating)
      const watchWhereLabels = movieReviewWatchWhereLabels(movie.watch_where)
      const contentKindLabel = movieReviewKindLabel(movie.content_kind)
      const imdbUrl = (movie.imdb_url || '').trim()
      const posterUrl = (movie.poster_url || '').trim()

      if (
        !displayTitle &&
        !displayOriginalTitle &&
        !displayGenre &&
        !releaseLabel &&
        !watchWhereLabels.length &&
        !imdbUrl &&
        !posterUrl
      ) {
        return ''
      }

      let imdbHost = 'IMDb'
      if (imdbUrl) {
        try {
          imdbHost = new URL(imdbUrl).hostname.replace(/^www\./, '') || 'IMDb'
        } catch {
          imdbHost = 'IMDb'
        }
      }

      const chips: string[] = []
      if (contentKindLabel) {
        chips.push(`<span class="post-movie-card__chip">${escapeHtml(contentKindLabel)}</span>`)
      }
      if (displayGenre) {
        chips.push(`<span class="post-movie-card__chip">${escapeHtml(displayGenre)}</span>`)
      }
      if (releaseLabel) {
        chips.push(`<span class="post-movie-card__chip">Премьера: ${escapeHtml(releaseLabel)}</span>`)
      }
      if (authorRatingLabel) {
        const ratingClass =
          authorRatingTone === 'green'
            ? ' post-movie-card__chip--green'
            : authorRatingTone === 'yellow'
              ? ' post-movie-card__chip--yellow'
              : authorRatingTone === 'red'
                ? ' post-movie-card__chip--red'
                : ''
        chips.push(
          `<span class="post-movie-card__chip post-movie-card__chip--rating${ratingClass}">Оценка автора: ${escapeHtml(authorRatingLabel)}</span>`
        )
      }

      const watchWhereHtml = watchWhereLabels.length
        ? `<div class="post-movie-card__meta-item">
            <span class="post-movie-card__meta-label">Где посмотреть</span>
            <span class="post-movie-card__meta-value">${escapeHtml(watchWhereLabels.join(', '))}</span>
          </div>`
        : ''
      const imdbHtml = imdbUrl
        ? `<div class="post-movie-card__meta-item">
            <span class="post-movie-card__meta-label">IMDb</span>
            <a href="${escapeHtml(imdbUrl)}" target="_blank" rel="nofollow noopener" class="post-movie-card__meta-link">
              Открыть на ${escapeHtml(imdbHost)}
            </a>
          </div>`
        : ''

      const originalTitleHtml =
        displayOriginalTitle &&
        displayOriginalTitle.toLowerCase() !== displayTitle.toLowerCase()
          ? `<p class="post-movie-card__subtitle">${escapeHtml(displayOriginalTitle)}</p>`
          : ''

      const posterHtml = posterUrl
        ? `<div class="post-movie-card__poster">
            <img src="${escapeHtml(posterUrl)}" alt="${escapeHtml(displayTitle || 'Постер')}" loading="lazy" />
          </div>`
        : ''

      const chipsHtml = chips.length
        ? `<div class="post-movie-card__chips">${chips.join('')}</div>`
        : ''
      const titleHtml = displayTitle
        ? `<p class="post-movie-card__title">${escapeHtml(displayTitle)}</p>`
        : ''
      const metaHtml =
        watchWhereHtml || imdbHtml
          ? `<div class="post-movie-card__meta">${watchWhereHtml}${imdbHtml}</div>`
          : ''

      return `<div class="post-movie-card">
        ${posterHtml}
        <div class="post-movie-card__content">
          ${chipsHtml}
          ${titleHtml}
          ${originalTitleHtml}
          ${metaHtml}
        </div>
      </div>`
    }

    const renderPostLinkBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'post_link')) return ''

      const normalized = normalizePostLinkBlockData(raw)
      const snapshot = normalized.snapshot as PostLinkSnapshot | null
      const normalizedRef = normalizeInternalPostReference(
        normalized.url || snapshot?.path || '',
        snapshot?.title
      )
      const resolvedPostId = normalizedRef.postId || snapshot?.post_id || normalized.post_id || null
      const href = escapeHtml(
        normalizedRef.path || snapshot?.path || normalized.url || '#'
      )
      const announcement = escapeHtml(normalized.announcement || '')
      const titleText = escapeHtml(
        snapshot?.title || (resolvedPostId ? `Материал #${resolvedPostId}` : 'Материал Тамбур')
      )
      const authorText = escapeHtml(snapshot?.author_title || snapshot?.author_username || '')
      const previewText = escapeHtml(snapshot?.preview_text || '')
      const previewImage = escapeHtml(snapshot?.preview_image_url || '')
      const needsHydration = !snapshot?.title || !snapshot?.preview_text || !snapshot?.preview_image_url

      if (!resolvedPostId) return ''

      const announcementHtml = announcement
        ? `<div class="post-linked-material__note">
            <p>${announcement}</p>
          </div>`
        : ''
      const imageHtml = previewImage
        ? `<div class="post-linked-material__image">
            <img src="${previewImage}" alt="${titleText}" loading="lazy" />
          </div>`
        : ''
      const authorHtml = authorText
        ? `<span class="post-linked-material__author">${authorText}</span>`
        : ''
      const metaHtml =
        authorHtml
          ? `<div class="post-linked-material__meta">${authorHtml}</div>`
          : ''
      const previewTextHtml = previewText
        ? `<p class="post-linked-material__text" data-post-link-text>${previewText}</p>`
        : '<p class="post-linked-material__text" data-post-link-text hidden></p>'

      return `<div class="post-linked-material" data-post-link-id="${resolvedPostId}"${needsHydration ? ' data-post-link-needs-hydration="1"' : ''}>
        ${announcementHtml}
        <a href="${href}" class="post-linked-material__card${previewImage ? '' : ' post-linked-material__card--no-image'}">
          ${imageHtml || '<div class="post-linked-material__image" data-post-link-image hidden></div>'}
          <div class="post-linked-material__content">
            ${metaHtml}
            <div class="post-linked-material__title" data-post-link-title>${titleText}</div>
            ${previewTextHtml}
            <span class="post-linked-material__action">Открыть материал</span>
          </div>
        </a>
      </div>`
    }

    const renderAuthorBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'author')) return ''

      const normalized = normalizeAuthorBlockData(raw)
      const username = normalized.snapshot?.username || normalized.username || ''
      if (!username) return ''

      const displayTitle = normalized.snapshot?.title || username
      const href = escapeHtml(normalized.snapshot?.path || buildAuthorPublicPath(username) || '#')
      const titleText = escapeHtml(displayTitle)
      const captionText = escapeHtml(normalized.caption || '')
      const avatarUrl = escapeHtml(normalized.snapshot?.avatar_url || '')
      const initial = escapeHtml((displayTitle[0] || username[0] || 'A').toUpperCase())

      const avatarHtml = avatarUrl
        ? `<span class="post-author-card__avatar">
            <img src="${avatarUrl}" alt="${titleText}" loading="lazy" />
          </span>`
        : `<span class="post-author-card__avatar post-author-card__avatar--fallback">${initial}</span>`
      const captionHtml = captionText
        ? `<span class="post-author-card__caption">${captionText}</span>`
        : ''

      return `<div class="post-author-card">
        <span class="post-author-card__line"></span>
        <div class="post-author-card__body">
          ${avatarHtml}
          <div class="post-author-card__content">
            <a href="${href}" class="post-author-card__name">${titleText}</a>
            ${captionHtml}
          </div>
        </div>
        <span class="post-author-card__line"></span>
      </div>`
    }

    const renderCalloutBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'callout')) return ''

      const text = typeof raw?.text === 'string' ? raw.text.trim() : ''
      if (!text) return ''

      return `<div class="post-callout">
        <span class="post-callout__line" aria-hidden="true"></span>
        <div class="post-callout__body">
          <div class="post-callout__text">${escapeHtml(text).replace(/\r?\n/g, '<br>')}</div>
        </div>
      </div>`
    }

    const resolvePostRatingBlockId = (block: any, index: number): string => {
      const rawBlockId =
        (typeof block?.id === 'string' && block.id.trim()
          ? block.id
          : typeof block?.data?.block_id === 'string' && block.data.block_id.trim()
            ? block.data.block_id
            : `post-rating-${index + 1}`) || `post-rating-${index + 1}`
      return rawBlockId
        .trim()
        .replace(/[^A-Za-z0-9_-]+/g, '-')
        .replace(/^[-_]+|[-_]+$/g, '')
        .slice(0, 64) || `post-rating-${index + 1}`
    }

    const renderPostRatingBlock = (block: any, index: number): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'post_rating')) return ''

      const blockId = resolvePostRatingBlockId(block, index)
      const activeRating = clonePostRating(localPostRatings[blockId]) ?? {
        block_id: blockId,
        scale_min: 1,
        scale_max: 10,
        average_value: null,
        votes_count: 0,
        user_vote: null,
      }
      const scaleMin = Number(activeRating.scale_min ?? 1)
      const scaleMax = Number(activeRating.scale_max ?? 10)
      const selectedValue = Number(activeRating.user_vote ?? 0)
      const votesCount = Math.max(Number(activeRating.votes_count ?? 0), 0)
      const averageValue =
        typeof activeRating.average_value === 'number' ? activeRating.average_value : null
      const averageLabel =
        averageValue === null
          ? '—'
          : Number.isInteger(averageValue)
            ? String(averageValue)
            : averageValue.toFixed(1)
      const values = Array.from(
        { length: Math.max(scaleMax - scaleMin + 1, 0) },
        (_, offset) => scaleMin + offset
      )
      const itemsHtml = values
        .map((value) => {
          const selectedClass = selectedValue === value ? ' is-selected' : ''
          return `<button
            type="button"
            class="post-inline-rating__item${selectedClass}"
            data-rating-value="${value}"
            aria-pressed="${selectedValue === value ? 'true' : 'false'}"
          >${value}</button>`
        })
        .join('')

      return `<div class="post-inline-rating" data-rating-block-id="${escapeHtml(blockId)}">
        <div class="post-inline-rating__eyebrow">Рейтинг</div>
        <div class="post-inline-rating__content">
          <div class="post-inline-rating__scale" role="group" aria-label="Оценка материала от 1 до 10">
            ${itemsHtml}
          </div>
          <div class="post-inline-rating__stats" aria-live="polite">
            <div class="post-inline-rating__average">${escapeHtml(averageLabel)}</div>
            <div class="post-inline-rating__meta">
              <span>средняя оценка</span>
              <span>${escapeHtml(
                `${votesCount} ${votesCount === 1 ? 'голос' : votesCount < 5 ? 'голоса' : 'голосов'}`
              )}</span>
            </div>
          </div>
        </div>
      </div>`
    }

    const renderTocBlock = (): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'toc')) return ''
      const tocEntries = Array.from(tocEntriesByIndex.values())
      if (!tocEntries.length) return ''

      const itemsHtml = tocEntries
        .map(
          (entry) => `<li class="post-toc__item post-toc__item--level-${entry.level}">
            <a href="#${escapeHtml(entry.id)}" class="post-toc__link">${escapeHtml(entry.text)}</a>
          </li>`
        )
        .join('')

      return `<nav class="post-toc" aria-label="Оглавление">
        <div class="post-toc__title">Оглавление</div>
        <ol class="post-toc__list">${itemsHtml}</ol>
      </nav>`
    }

    const renderInlinePollBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'poll')) return ''

      const question = typeof raw?.question === 'string' ? raw.question.trim() : ''
      const allowsMultipleAnswers = Boolean(raw?.allows_multiple_answers)
      const options = Array.isArray(raw?.options)
        ? raw.options
            .map((item: unknown) => (typeof item === 'string' ? item.trim() : ''))
            .filter(Boolean)
            .slice(0, 10)
        : []
      if (!question || options.length < 2) return ''

      const pollId = typeof raw?.uid === 'string' && raw.uid.trim() ? raw.uid.trim() : ''
      const localPollId =
        localPoll && typeof localPoll.id === 'string' && localPoll.id.trim() ? localPoll.id.trim() : ''
      const activePoll =
        localPoll &&
        (
          (pollId && localPollId && localPollId === pollId) ||
          (
            !pollId &&
            normalizeTextForCompare(localPoll.question || '') === normalizeTextForCompare(question) &&
            Array.isArray(localPoll.options) &&
            matchesInlinePollOptionSet(localPoll.options, options)
          )
        )
          ? localPoll
          : null
      const selectedSet = new Set(activePoll?.user_selection || [])
      const hasUserVote = selectedSet.size > 0
      const totalVoters = Math.max(Number(activePoll?.total_voter_count || 0), 0)
      const modeLabel = allowsMultipleAnswers
        ? 'Можно выбрать несколько вариантов'
        : 'Можно выбрать только один вариант'
      const optionItems = options
        .map((option: string, index: number) => {
          const optionPayload = activePoll?.options?.[index]
          const count = Math.max(Number(optionPayload?.voter_count || 0), 0)
          const percent = totalVoters > 0 ? Math.round((count / totalVoters) * 100) : 0
          const isSelected = selectedSet.has(index)
          if (!hasUserVote) {
            return `<div class="post-poll-option post-inline-poll__option post-inline-poll__option--choice" data-option-index="${index}">
              <div class="post-inline-poll__control" aria-hidden="true">
                <span class="post-inline-poll__marker"></span>
              </div>
              <div class="post-inline-poll__option-main">
                <div class="post-inline-poll__option-row">
                  <span class="post-inline-poll__option-text">${escapeHtml(option)}</span>
                </div>
              </div>
            </div>`
          }

          const optionStateClass = ` post-inline-poll__option--locked post-inline-poll__option--result${isSelected ? ' post-inline-poll__option--selected-vote' : ''}`
          const leadingControl = isSelected
            ? `<div class="post-inline-poll__checkmark" aria-hidden="true">✓</div>`
            : `<div class="post-inline-poll__checkmark post-inline-poll__checkmark--empty" aria-hidden="true"></div>`
          return `<div class="post-poll-option post-inline-poll__option${isSelected ? ' is-selected' : ''}${optionStateClass}" data-option-index="${index}">
            ${leadingControl}
            <div class="post-inline-poll__option-main">
              <div class="post-inline-poll__option-row">
                <span class="post-inline-poll__option-text">${escapeHtml(option)}</span>
                <span class="post-inline-poll__option-percent">${percent}%</span>
              </div>
              <progress class="post-inline-poll__progress${isSelected ? ' is-selected' : ''}" value="${percent}" max="100"></progress>
              <div class="post-inline-poll__option-meta">
                <span>${formatPollVoteLabel(count)}</span>
                ${isSelected ? '<span class="post-inline-poll__option-badge">Ваш голос</span>' : ''}
              </div>
            </div>
          </div>`
        })
        .join('')
      const statusLabel = activePoll?.is_closed
        ? 'Опрос завершен'
        : hasUserVote
          ? 'Вы уже проголосовали'
          : 'Нажмите на вариант, чтобы проголосовать'
      const attrs = [
        `data-poll-multiple="${allowsMultipleAnswers ? '1' : '0'}"`,
        `data-poll-closed="${activePoll?.is_closed ? '1' : '0'}"`,
        `data-poll-locked="${hasUserVote ? '1' : '0'}"`,
        pollId ? `data-poll-id="${escapeHtml(pollId)}"` : '',
      ]
        .filter(Boolean)
        .join(' ')

      return `<div class="post-poll post-inline-poll" ${attrs}>
        <div class="post-inline-poll__head">
          <div class="post-inline-poll__eyebrow">Опрос</div>
          <div class="post-inline-poll__question">${escapeHtml(question)}</div>
          <div class="post-inline-poll__mode">${escapeHtml(modeLabel)}</div>
        </div>
        <div class="post-inline-poll__options">${optionItems}</div>
        <div class="post-inline-poll__footer${hasUserVote ? '' : ' post-inline-poll__footer--compact'}">
          <span>${escapeHtml(statusLabel)}</span>
          ${hasUserVote ? `<span>${formatPollVoteLabel(totalVoters)}</span>` : ''}
        </div>
      </div>`
    }

    const renderMovieTimeBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'movie_time')) return ''
      const rawTime = typeof raw?.time === 'string' ? raw.time.trim() : ''
      if (!rawTime) return ''

      const parseTimeToSeconds = (value: string): number | null => {
        if (!value) return null
        if (/^\d+$/.test(value)) {
          const totalSeconds = Number(value)
          if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return null
          return Math.floor(totalSeconds)
        }
        const parts = value.split(':').map((part) => part.trim())
        if (parts.length < 2 || parts.length > 3) return null
        if (parts.some((part) => !/^\d+$/.test(part))) return null
        if (parts.length === 2) {
          const minutes = Number(parts[0])
          const seconds = Number(parts[1])
          if (seconds >= 60) return null
          return minutes * 60 + seconds
        }
        const hours = Number(parts[0])
        const minutes = Number(parts[1])
        const seconds = Number(parts[2])
        if (minutes >= 60 || seconds >= 60) return null
        return hours * 3600 + minutes * 60 + seconds
      }

      const formatTimeFromSeconds = (totalSeconds: number, useHours: boolean): string => {
        const safe = Math.max(0, Math.floor(totalSeconds))
        const hours = Math.floor(safe / 3600)
        const minutes = Math.floor((safe % 3600) / 60)
        const seconds = safe % 60
        if (useHours || hours > 0) {
          return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
        }
        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      }

      const totalSeconds = parseTimeToSeconds(rawTime)
      if (totalSeconds === null) return ''

      const hasHoursInInput = rawTime.split(':').length === 3
      const displayTime = formatTimeFromSeconds(totalSeconds, hasHoursInInput || totalSeconds >= 3600)
      const sceneTitle = escapeHtml(
        typeof raw?.title === 'string' && raw.title.trim() ? raw.title : 'Ключевой момент'
      )
      const sceneNote = escapeHtml(typeof raw?.note === 'string' ? raw.note : '')
      const noteHtml = sceneNote
        ? `<span class="post-movie-time__note">${sceneNote}</span>`
        : ''

      return `<span class="post-movie-time">
        <span class="post-movie-time__trigger">
          <span class="post-movie-time__icon" aria-hidden="true">⏱</span>
          <span class="post-movie-time__stamp">${displayTime}</span>
          <span class="post-movie-time__details">
            <span class="post-movie-time__meta">Время в фильме</span>
            <span class="post-movie-time__scene">${sceneTitle}</span>
            ${noteHtml}
          </span>
        </span>
      </span>`
    }

    const renderLegacySpoilerBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'spoiler')) return ''

      const spoilerTitle =
        typeof raw?.title === 'string' && raw.title.trim() ? raw.title.trim() : 'Спойлер'
      const spoilerContent = typeof raw?.content === 'string' ? raw.content.trim() : ''
      if (!spoilerContent) return ''

      const spoilerBody = escapeHtml(spoilerContent).replace(/\r?\n/g, '<br>')
      return `<div class="post-spoiler" data-spoiler-open="0">
        <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
          <span class="post-spoiler__title">${escapeHtml(spoilerTitle)}</span>
          <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
        </div>
        <div class="post-spoiler__content">
          <p>${spoilerBody}</p>
        </div>
      </div>`
    }

    const renderMusicBlock = (raw: any): string => {
      if (!isTemplateEditorBlockEnabled(template?.type ?? '', 'music')) return ''

      const rawUrl = typeof raw?.url === 'string' ? raw.url.trim() : ''
      if (!rawUrl) return ''

      const normalizeExternalUrl = (value: string): string => {
        const candidate = value.trim()
        if (!candidate) return ''
        if (/^https?:\/\//i.test(candidate)) return candidate
        return `https://${candidate}`
      }

      const safeExternalUrl = normalizeExternalUrl(rawUrl)
      if (!safeExternalUrl) return ''

      const providerHint = typeof raw?.provider === 'string' ? raw.provider.trim().toLowerCase() : 'auto'
      const captionText =
        typeof raw?.caption === 'string' ? raw.caption.trim() : ''
      const figureCaption = captionText
        ? `<figcaption class="post-music__caption">${escapeHtml(captionText)}</figcaption>`
        : ''
      const fallbackCaption = captionText
        ? `<p class="post-music__caption">${escapeHtml(captionText)}</p>`
        : ''

      const buildYandexTrackEmbedUrl = (trackId: string, albumId: string): string =>
        `https://music.yandex.ru/iframe/album/${albumId}/track/${trackId}`

      const buildYandexPlaylistEmbedUrl = (owner: string, playlistId: string): string =>
        `https://music.yandex.ru/iframe/#playlist/${encodeURIComponent(owner)}/${playlistId}`

      const parseMusicEmbed = (
        value: string,
        hint: string
      ): {
        provider: string
        providerLabel: string
        embedUrl: string
        title: string
        frameClassName?: string
      } | null => {
        let parsed: URL
        try {
          parsed = new URL(value)
        } catch {
          return null
        }

        const host = parsed.hostname.replace(/^www\./i, '').toLowerCase()
        const path = parsed.pathname

        const spotifyMatch = path.match(/\/track\/([a-zA-Z0-9]+)(?:\/|$)/)
        if (
          spotifyMatch &&
          (hint === 'auto' || hint === 'spotify') &&
          (host === 'open.spotify.com' || host.endsWith('.spotify.com'))
        ) {
          const trackId = spotifyMatch[1]
          return {
            provider: 'spotify',
            providerLabel: 'Spotify',
            embedUrl: `https://open.spotify.com/embed/track/${trackId}?utm_source=comuna`,
            title: 'Плеер Spotify',
          }
        }

        const spotifyPlaylistMatch = path.match(/\/playlist\/([a-zA-Z0-9]+)(?:\/|$)/)
        if (
          spotifyPlaylistMatch &&
          (hint === 'auto' || hint === 'spotify') &&
          (host === 'open.spotify.com' || host.endsWith('.spotify.com'))
        ) {
          const playlistId = spotifyPlaylistMatch[1]
          return {
            provider: 'spotify',
            providerLabel: 'Spotify',
            embedUrl: `https://open.spotify.com/embed/playlist/${playlistId}?utm_source=comuna`,
            title: 'Плейлист Spotify',
            frameClassName: 'post-music__frame--playlist',
          }
        }

        const yandexAlbumTrackMatch = path.match(/\/album\/(\d+)\/track\/(\d+)(?:\/|$)/)
        if (
          yandexAlbumTrackMatch &&
          (hint === 'auto' || hint === 'yandex_music') &&
          (host === 'music.yandex.ru' || host === 'music.yandex.com')
        ) {
          const albumId = yandexAlbumTrackMatch[1]
          const trackId = yandexAlbumTrackMatch[2]
          return {
            provider: 'yandex_music',
            providerLabel: 'Яндекс Музыка',
            embedUrl: buildYandexTrackEmbedUrl(trackId, albumId),
            title: 'Плеер Яндекс Музыки',
          }
        }

        const yandexIframeAlbumTrackMatch = path.match(
          /\/iframe\/album\/(\d+)\/track\/(\d+)(?:\/|$)/i
        )
        if (
          yandexIframeAlbumTrackMatch &&
          (hint === 'auto' || hint === 'yandex_music') &&
          (host === 'music.yandex.ru' || host === 'music.yandex.com')
        ) {
          const albumId = yandexIframeAlbumTrackMatch[1]
          const trackId = yandexIframeAlbumTrackMatch[2]
          return {
            provider: 'yandex_music',
            providerLabel: 'Яндекс Музыка',
            embedUrl: buildYandexTrackEmbedUrl(trackId, albumId),
            title: 'Плеер Яндекс Музыки',
          }
        }

        const yandexTrackMatch = path.match(/\/track\/(\d+)(?:\/|$)/)
        if (
          yandexTrackMatch &&
          (hint === 'auto' || hint === 'yandex_music') &&
          (host === 'music.yandex.ru' || host === 'music.yandex.com')
        ) {
          const trackId = yandexTrackMatch[1]
          const albumId = parsed.searchParams.get('album_id') || parsed.searchParams.get('albumId')
          if (albumId) {
            return {
              provider: 'yandex_music',
              providerLabel: 'Яндекс Музыка',
              embedUrl: buildYandexTrackEmbedUrl(trackId, albumId),
              title: 'Плеер Яндекс Музыки',
            }
          }
        }

        const yandexPlaylistMatch = path.match(/\/users\/([^/]+)\/playlists\/(\d+)(?:\/|$)/i)
        if (
          yandexPlaylistMatch &&
          (hint === 'auto' || hint === 'yandex_music') &&
          (host === 'music.yandex.ru' || host === 'music.yandex.com')
        ) {
          const owner = decodeURIComponent(yandexPlaylistMatch[1])
          const playlistId = yandexPlaylistMatch[2]
          return {
            provider: 'yandex_music',
            providerLabel: 'Яндекс Музыка',
            embedUrl: buildYandexPlaylistEmbedUrl(owner, playlistId),
            title: 'Плейлист Яндекс Музыки',
            frameClassName: 'post-music__frame--playlist',
          }
        }

        const yandexIframePlaylistMatch = parsed.hash.match(/#playlist\/([^/]+)\/(\d+)(?:\/|$)/i)
        if (
          yandexIframePlaylistMatch &&
          (hint === 'auto' || hint === 'yandex_music') &&
          (host === 'music.yandex.ru' || host === 'music.yandex.com')
        ) {
          const owner = decodeURIComponent(yandexIframePlaylistMatch[1])
          const playlistId = yandexIframePlaylistMatch[2]
          return {
            provider: 'yandex_music',
            providerLabel: 'Яндекс Музыка',
            embedUrl: buildYandexPlaylistEmbedUrl(owner, playlistId),
            title: 'Плейлист Яндекс Музыки',
            frameClassName: 'post-music__frame--playlist',
          }
        }

        if (
          (hint === 'auto' || hint === 'soundcloud') &&
          (host === 'soundcloud.com' || host.endsWith('.soundcloud.com') || host === 'snd.sc')
        ) {
          return {
            provider: 'soundcloud',
            providerLabel: 'SoundCloud',
            embedUrl: `https://w.soundcloud.com/player/?url=${encodeURIComponent(value)}&auto_play=false&hide_related=false&show_comments=false&show_user=true&show_reposts=false`,
            title: 'Плеер SoundCloud',
          }
        }

        return null
      }

      const parsedEmbed = parseMusicEmbed(safeExternalUrl, providerHint)
      if (!parsedEmbed) {
        return `<div class="post-music post-music--link-only">
          <div class="post-music__header">
            <span class="post-music__badge">Музыка</span>
            <a
              href="${escapeHtml(safeExternalUrl)}"
              target="_blank"
              rel="nofollow noopener"
              class="post-music__open-link"
            >
              Открыть трек
            </a>
          </div>
          <p class="post-music__fallback">
            Для этой ссылки встроенный плеер недоступен. Поддержка: Spotify, Яндекс Музыка, SoundCloud.
          </p>
          ${fallbackCaption}
        </div>`
      }

      return `<figure class="post-music" data-music-provider="${parsedEmbed.provider}">
        <div class="post-music__header">
          <span class="post-music__badge">Музыка</span>
          <span class="post-music__provider">${parsedEmbed.providerLabel}</span>
          <a
            href="${escapeHtml(safeExternalUrl)}"
            target="_blank"
            rel="nofollow noopener"
            class="post-music__open-link"
          >
            Открыть трек
          </a>
        </div>
          <iframe
          class="post-music__frame${parsedEmbed.frameClassName ? ` ${parsedEmbed.frameClassName}` : ''}"
          src="${escapeHtml(parsedEmbed.embedUrl)}"
          loading="lazy"
          title="${escapeHtml(parsedEmbed.title)}"
          frameborder="0"
          allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
        ></iframe>
        ${figureCaption}
      </figure>`
    }

    const renderEmbedBlock = (raw: any): string => {
      const embedUrl = String(raw?.embed || '').trim()
      if (!embedUrl || !/^https:\/\//i.test(embedUrl)) return ''
      const captionText = typeof raw?.caption === 'string' ? raw.caption.trim() : ''
      const captionHtml = captionText
        ? `<div class="image-alt-text">${escapeHtml(captionText)}</div>`
        : ''
      return `<div class="post-embed">
        <div class="post-embed__responsive">
          <iframe
            src="${escapeHtml(embedUrl)}"
            loading="lazy"
            title="Встроенное видео"
            frameborder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowfullscreen
          ></iframe>
        </div>
        ${captionHtml}
      </div>`
    }

    const renderTableBlock = (raw: any): string => {
      const sourceRows = Array.isArray(raw?.content) ? raw.content : []
      const rows = sourceRows
        .map((row: unknown) =>
          Array.isArray(row)
            ? row.map((cell) => escapeHtml(String(cell ?? '')).replace(/\r?\n/g, '<br>'))
            : []
        )
        .filter((row: string[]) => row.length > 0)

      if (!rows.length) return ''

      const withHeadings = Boolean(raw?.withHeadings)
      const headRow = withHeadings ? rows[0] : null
      const bodyRows = withHeadings ? rows.slice(1) : rows

      const headHtml = headRow?.length
        ? `<thead><tr>${headRow.map((cell: string) => `<th>${cell || '&nbsp;'}</th>`).join('')}</tr></thead>`
        : ''
      const bodyHtml = bodyRows.length
        ? `<tbody>${bodyRows
            .map((row: string[]) => `<tr>${row.map((cell) => `<td>${cell || '&nbsp;'}</td>`).join('')}</tr>`)
            .join('')}</tbody>`
        : ''

      return `<div class="post-table-wrap"><table>${headHtml}${bodyHtml}</table></div>`
    }

    switch (block.type) {
      case 'paragraph':
        return `<p>${block.data.text}</p>`;
      case 'header':
        const headingLevel = Number(block?.data?.level)
        const safeHeadingLevel =
          Number.isInteger(headingLevel) && headingLevel >= 1 && headingLevel <= 6
            ? headingLevel
            : 2
        const tocEntry = tocEntriesByIndex.get(index)
        const headingId = tocEntry?.id ? ` id="${escapeHtml(tocEntry.id)}"` : ''
        return `<h${safeHeadingLevel}${headingId}>${block.data.text}</h${safeHeadingLevel}>`;
      case 'list':
        const listClass = block.data.style === 'checklist' ? 'checklist' : '';
        const items = block.data.items.map((item: any) => 
          `<li>${block.data.style === 'checklist' 
            ? `<input type="checkbox" ${item.meta.checked ? 'checked' : ''} disabled> `
            : ''}${item.content}</li>`
        ).join('');
        return block.data.style === 'ordered' 
          ? `<ol>${items}</ol>` 
          : `<ul class="${listClass}">${items}</ul>`;
      case 'table':
        return renderTableBlock(block.data)
      case 'quote':
        return renderQuoteBlockHtml(block.data)
      case 'callout':
        return renderCalloutBlock(block.data)
      case 'code':
        return `<pre><code>${block.data.code}</code></pre>`;
      case 'poll':
        return renderInlinePollBlock(block.data)
      case 'toc':
      case 'tableofcontents':
        return renderTocBlock()
      case 'post_rating':
      case 'postrating':
        return renderPostRatingBlock(block, index)
      case 'delimiter':
      case 'divider':
        return '<div class="post-divider" aria-hidden="true"></div>'
      case 'image': {
        const file = block.data?.file || {}
        const url = file.url || block.data?.url || ''
        const alt = block.data?.alt || file.alt || ''
        const title = file.title || block.data?.title || ''
        const caption =
          (typeof block.data?.caption === 'string' ? block.data.caption.trim() : '') ||
          (typeof file.caption === 'string' ? file.caption.trim() : '')
        return processImage(url, '', alt, title, caption)
      }
      case 'gallery':
        if (
          template?.type === 'tweet' &&
          Array.isArray(block.data?.images) &&
          block.data.images.length === 1
        ) {
          const firstImage = block.data.images[0]
          return processImage(
            firstImage?.url || '',
            '',
            firstImage?.alt || '',
            firstImage?.title || '',
            ''
          )
        }
        return `<div class="post-gallery">
          ${block.data.images.map((img: any) => 
            `<img src="${img.url}" alt="${img.alt || ''}" title="${img.title || ''}">`
          ).join('')}
        </div>`;
      case 'map':
        return renderMapBlock(block.data)
      case 'imageCompare':
      case 'compare':
        return renderImageCompareBlock(block.data)
      case 'movie_time':
      case 'movieTime':
        return renderMovieTimeBlock(block.data)
      case 'movie_card':
      case 'movieCard':
        return renderMovieCardBlock(block.data)
      case 'post_link':
      case 'postlink':
        return renderPostLinkBlock(block.data)
      case 'author':
        return renderAuthorBlock(block.data)
      case 'spoiler':
        return renderLegacySpoilerBlock(block.data)
      case 'music':
      case 'musicTrack':
        return renderMusicBlock(block.data)
      case 'embed':
        return renderEmbedBlock(block.data)
      case 'link':
      case 'customLink':
        const url = block.data.url || '#';
        const text = block.data.text || block.data.title || url;
        const isExternal = url.startsWith('http');
        const target = isExternal ? ' target="_blank" rel="noopener"' : '';
        const linkStyle = block.data.style || 'link';
        return `<p class="text-center"><a href="${url}"${target} class="${linkStyle}">${text}</a></p>`;
      default:
        return '';
    }
  }

  function convertJsonToHtml(jsonContent: string): string {
    try {
      const content = parseSerializedEditorModel(jsonContent)
      if (!content.blocks) return '';
      const { byIndex: tocEntriesByIndex } = buildTocEntries(content.blocks)
      
      // Обложка / врезка (Editor.js additional) — сразу в HTML, не <preview-image> (иначе URL текстом)
      const previewImageUrl = String(content.additional?.previewImage || '').trim()
      const previewImage = previewImageUrl
        ? processImage(previewImageUrl, '', 'Preview image', '', '')
        : ''
      const previewDescriptionText = String(content.additional?.previewDescription || '').trim()
      const previewDescription = previewDescriptionText
        ? buildPreviewParagraphFromText(previewDescriptionText)
        : ''
      const metaTitle = content.additional?.metaTitle
        ? `<meta-title>${content.additional.metaTitle}</meta-title>`
        : ''
      const metaDescription = content.additional?.metaDescription
        ? `<meta-description>${content.additional.metaDescription}</meta-description>`
        : ''
        
      const renderSpoilerContainer = (spoilerTitle: string, spoilerHtml: string): string => {
        if (!spoilerHtml.trim()) return ''
        return `<div class="post-spoiler" data-spoiler-open="0">
          <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
            <span class="post-spoiler__title">${escapeHtml(spoilerTitle || 'Спойлер')}</span>
            <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
          </div>
          <div class="post-spoiler__content">
            ${spoilerHtml}
          </div>
        </div>`
      }

      const htmlParts: string[] = []
      const spoilerStack: Array<{ title: string; parts: string[] }> = []

      const appendHtmlToCurrentScope = (html: string, blockType: string) => {
        if (!html) return
        const targetParts =
          spoilerStack.length > 0 ? spoilerStack[spoilerStack.length - 1].parts : htmlParts
        const normalizedType = blockType.toLowerCase()
        if (
          (normalizedType === 'movie_time' || normalizedType === 'movietime') &&
          targetParts.length > 0 &&
          /<\/p>\s*$/i.test(targetParts[targetParts.length - 1])
        ) {
          targetParts[targetParts.length - 1] = targetParts[targetParts.length - 1].replace(
            /<\/p>\s*$/i,
            ` ${html}</p>`
          )
          return
        }
        targetParts.push(html)
      }

      for (const [index, block] of content.blocks.entries()) {
        const blockType = String(block?.type || '').toLowerCase()
        if (blockType === 'spoiler') {
          const rawData = block?.data || {}
          const legacyContent =
            typeof rawData?.content === 'string' ? rawData.content.trim() : ''
          if (legacyContent) {
            const html = processJsonBlock(block, index, tocEntriesByIndex)
            appendHtmlToCurrentScope(html, blockType)
            continue
          }
          const markerCandidate =
            typeof rawData?.marker === 'string'
              ? rawData.marker.trim().toLowerCase()
              : typeof rawData?.mode === 'string'
                ? rawData.mode.trim().toLowerCase()
                : ''
          if (markerCandidate === 'end' || markerCandidate === 'close') {
            const completedSpoiler = spoilerStack.pop()
            if (!completedSpoiler) continue
            const wrappedSpoiler = renderSpoilerContainer(
              completedSpoiler.title,
              completedSpoiler.parts.join('\n')
            )
            appendHtmlToCurrentScope(wrappedSpoiler, 'spoiler')
            continue
          }
          const spoilerTitle =
            typeof rawData?.title === 'string' && rawData.title.trim()
              ? rawData.title.trim()
              : 'Спойлер'
          spoilerStack.push({
            title: spoilerTitle,
            parts: [],
          })
          continue
        }

        const html = processJsonBlock(block, index, tocEntriesByIndex)
        appendHtmlToCurrentScope(html, blockType)
      }

      while (spoilerStack.length > 0) {
        const unclosedSpoiler = spoilerStack.pop()
        if (!unclosedSpoiler) break
        const wrappedSpoiler = renderSpoilerContainer(
          unclosedSpoiler.title,
          unclosedSpoiler.parts.join('\n')
        )
        appendHtmlToCurrentScope(wrappedSpoiler, 'spoiler')
      }

      const htmlContent = htmlParts.join('\n');
        
      return `${previewImage}${previewDescription}${metaTitle}${metaDescription}${htmlContent}`;
    } catch (error) {
      console.error('Error converting JSON to HTML:', error);
      return '';
    }
  }

  function processImage(imgUrl: string, content: string = '', alt: string = '', title: string = '', caption: string = '') {
    if (imgUrl.includes('pictrs')) {
      // Очищаем URL от всех параметров
      const baseUrl = imgUrl.split('?')[0];
      
      // Базовые параметры для всех изображений
      const baseParams = 'format=webp&quality=80';
      
      // Формируем URL с параметрами
      const getImageUrl = (size: number) => {
        return `${baseUrl}?${baseParams}&thumbnail=${size}`;
      };
      
      // Используем минимальный размер для src
      const minSize = 240;
      const minImageUrl = getImageUrl(minSize);
      
      // Оптимизированные размеры для разных устройств
      // 240px для мобильных (1x)
      // 480px для стандартных экранов (достаточно для max-width: 640px)
      // 960px для ретина-дисплеев (2x)
      const sizes = [240, 480, 960];
      const srcset = sizes
        .map(size => `${getImageUrl(size)} ${size}w`)
        .join(', ');
      
      // Указываем точные размеры для разных брейкпоинтов
      // (max-width: 640px) - мобильные устройства
      // (min-width: 641px) - планшеты и десктопы
      const sizesAttr = '(max-width: 640px) 240px, (min-width: 641px) 480px';
      
      // In feed cards all inline images are lazy, including images loaded after expand.
      const forceLazyImages = collapsible && !showFullBody;
      let loadingAttrs = 'decoding="async"';
      
      if (forceLazyImages) {
        loadingAttrs = 'loading="lazy" decoding="async"';
      } else if (isFirstImage) {
        // Первое изображение загружаем с высоким приоритетом и без ленивой загрузки
        loadingAttrs = 'fetchpriority="high" decoding="async"';
        firstImageUrl = minImageUrl;
        firstImageSrcset = srcset;
      } else {
        // Для остальных изображений используем ленивую загрузку
        // Но только если они не в первых 1000 символах контента
        const imagePosition = content.indexOf(imgUrl);
        if (imagePosition > 1000) {
          loadingAttrs = 'loading="lazy" decoding="async"';
        }
      }
      
      isFirstImage = false;
      
      // Добавляем alt, title и caption к атрибутам
      const altAttr = alt ? `alt="${alt}"` : 'alt="Post image"';
      const titleAttr = title ? `title="${title}"` : '';
      const captionHtml = caption ? `<div class="image-alt-text">${caption}</div>` : '';
      const expandedImageUrl = `${baseUrl}?format=webp&quality=90`;
      
      const imgHtml = `<img 
        src="${minImageUrl}" 
        srcset="${srcset}" 
        sizes="${sizesAttr}" 
        data-expandable-image="1"
        data-expandable-src="${expandedImageUrl}"
        ${loadingAttrs}
        ${altAttr}
        ${titleAttr}
        class="w-full h-auto">
        ${captionHtml}`;

      return imgHtml;
    }
    const loadingAttrs = collapsible && !showFullBody
      ? 'loading="lazy" decoding="async"'
      : 'decoding="async"';
    const captionHtml = caption
      ? `<div class="image-alt-text">${escapeHtml(caption)}</div>`
      : '';
    return `<img src="${imgUrl}" data-expandable-image="1" data-expandable-src="${imgUrl}" ${loadingAttrs} ${alt ? `alt="${alt}"` : 'alt="Post image"'} ${title ? `title="${title}"` : ''} class="w-full h-auto">${captionHtml}`;
  }

  // Добавляем функцию для определения, находится ли изображение выше сгиба
  function isAboveTheFold(imageUrl: string, content: string): boolean {
    // Если это первое изображение, считаем его выше сгиба
    if (isFirstImage) return true;
    
    // Проверяем позицию изображения в контенте
    const imagePosition = content.indexOf(imageUrl);
    // Если изображение находится в первых 1000 символах, считаем его выше сгиба
    return imagePosition <= 1000;
  }

  function trimPreviewText(rawText: string): { text: string; trimmed: boolean } {
    let paragraphText = rawText.trim();
    if (!paragraphText) {
      return { text: '', trimmed: false };
    }
    if (title) {
      const titleText = title.trim();
      if (titleText && paragraphText.toLowerCase().startsWith(titleText.toLowerCase())) {
        paragraphText = paragraphText
          .slice(titleText.length)
          .replace(/^[:\-–—.!?\s]+/, '')
          .trim();
      }
    }
    if (!paragraphText) {
      return { text: '', trimmed: false };
    }
    if (paragraphText.length > maxPreviewLength) {
      previewWasTrimmed = true;
      return { text: `${paragraphText.slice(0, maxPreviewLength).trim()}...`, trimmed: true };
    }
    return { text: paragraphText, trimmed: false };
  }

  function removeTitlePrefixFromText(rawText: string): string {
    let text = rawText.trim();
    if (!text || !title) return text;
    const titleText = title.trim();
    if (!titleText || !text.toLowerCase().startsWith(titleText.toLowerCase())) return text;
    return text
      .slice(titleText.length)
      .replace(/^[:\-–—.!?\s]+/, '')
      .trim();
  }

  function normalizePreviewCompareText(rawText: string): string {
    return removeTitlePrefixFromText(stripHtmlTags(rawText))
      .replace(/\.\.\.$/, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function looksTrimmedPreview(rawText: string): boolean {
    return /(?:\.{3}|…)\s*(?:<\/p>)?\s*$/i.test((rawText || '').trim());
  }

  function collectEditorText(value: any): string {
    if (!value) return '';
    if (typeof value === 'string') return stripHtmlTags(value);
    if (Array.isArray(value)) return value.map(collectEditorText).filter(Boolean).join(' ');
    if (typeof value !== 'object') return '';

    const chunks: string[] = [];
    for (const key of ['text', 'caption', 'title', 'description', 'quote', 'message']) {
      if (typeof value[key] === 'string') chunks.push(stripHtmlTags(value[key]));
    }
    for (const key of ['blocks', 'data', 'items', 'content', 'rows', 'images', 'file', 'before', 'after']) {
      const nested = value[key];
      if (Array.isArray(nested) || (nested && typeof nested === 'object')) {
        chunks.push(collectEditorText(nested));
      }
    }
    return chunks.filter(Boolean).join(' ');
  }

  function extractSourcePlainText(rawContent: string): string {
    const editorContent = parseSerializedEditorModel(rawContent);
    if (editorContent) {
      return normalizePreviewCompareText(collectEditorText(editorContent));
    }
    return normalizePreviewCompareText(
      rawContent
        .replace(/<preview-image>.*?<\/preview-image>/gis, '')
        .replace(/<preview-description>.*?<\/preview-description>/gis, '')
    );
  }

  function buildPreviewParagraphFromText(rawText: string): string {
    const { text } = trimPreviewText(rawText);
    if (!text) return '';
    return `<p>${escapeHtml(text).replace(/\r\n|\r|\n/g, '<br>')}</p>`;
  }

  function buildPreviewParagraphFromHtml(paragraphHtml: string, paragraphText: string): string {
    const { text, trimmed } = trimPreviewText(paragraphText);
    if (!text) return '';
    if (!trimmed && paragraphHtml && text === paragraphText.trim()) {
      return `<p>${paragraphHtml}</p>`;
    }
    return `<p>${escapeHtml(text)}</p>`;
  }

  function extractPreviewParagraphFromHtml(html: string): string {
    if (browser) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      const paragraphs = Array.from(tempDiv.querySelectorAll('p'));
      for (const paragraph of paragraphs) {
        const paragraphText = stripHtmlTags(paragraph.innerHTML);
        if (!paragraphText.trim()) continue;
        const preview = buildPreviewParagraphFromHtml(paragraph.innerHTML, paragraphText);
        if (preview) {
          return preview;
        }
      }
      const text = tempDiv.textContent || '';
      return buildPreviewParagraphFromText(text);
    }
    return buildPreviewParagraphFromText(stripHtmlTags(html));
  }

  function extractPreviewImageFromJson(content: any): { url: string; alt: string; title: string } | null {
    const blocks = content?.blocks ?? [];
    for (const block of blocks) {
      if (block.type === 'image') {
        const url = block.data?.file?.url || block.data?.url;
        if (url) {
          return {
            url,
            alt: block.data?.file?.alt || block.data?.alt || '',
            title: block.data?.file?.title || block.data?.title || ''
          };
        }
      }
      if (block.type === 'gallery') {
        const first = block.data?.images?.[0];
        if (first?.url) {
          return {
            url: first.url,
            alt: first.alt || '',
            title: first.title || ''
          };
        }
      }
      if (block.type === 'imageCompare' || block.type === 'compare') {
        const before = block.data?.before;
        const after = block.data?.after;
        const source = before?.url ? before : after;
        if (source?.url) {
          return {
            url: source.url,
            alt: source.alt || '',
            title: source.title || ''
          };
        }
      }
    }
    return null;
  }

  function extractPreviewMovieCardFromJson(content: any): string {
    const blocks = Array.isArray(content?.blocks) ? content.blocks : []
    for (const block of blocks) {
      if (!block || typeof block !== 'object') continue
      if (block.type !== 'movie_card' && block.type !== 'movieCard') continue
      const html = processJsonBlock(block)
      if (html) return html
    }
    return ''
  }

  function extractPreviewPostLinkFromJson(content: any): string {
    const blocks = Array.isArray(content?.blocks) ? content.blocks : []
    for (const block of blocks) {
      if (!block || typeof block !== 'object') continue
      if (block.type !== 'post_link' && block.type !== 'postLink') continue
      const html = processJsonBlock(block)
      if (html) return html
    }
    return ''
  }

  function extractFirstImageFromHtml(html: string): { url: string; alt: string; title: string } | null {
    if (browser) {
      const tempDiv = document.createElement('div');
      tempDiv.innerHTML = html;
      const img = tempDiv.querySelector('img');
      if (img) {
        return {
          url: img.getAttribute('src') || '',
          alt: img.getAttribute('alt') || '',
          title: img.getAttribute('title') || ''
        };
      }
      return null;
    }

    const imgMatch = html.match(/<img[^>]+src=["']([^"']+)["'][^>]*>/i);
    if (!imgMatch) return null;
    const tag = imgMatch[0];
    const altMatch = tag.match(/alt=["']([^"']*)["']/i);
    const titleMatch = tag.match(/title=["']([^"']*)["']/i);
    return {
      url: imgMatch[1],
      alt: altMatch ? altMatch[1] : '',
      title: titleMatch ? titleMatch[1] : ''
    };
  }

  function extractPreviewParagraphFromJson(content: any): string {
    const paragraphBlocks = (content?.blocks ?? []).filter(
      (block: any) => block.type === 'paragraph' && block.data?.text
    );
    for (const block of paragraphBlocks) {
      const paragraphHtml = block.data.text;
      const preview = buildPreviewParagraphFromHtml(paragraphHtml, stripHtmlTags(paragraphHtml));
      if (preview) {
        return preview;
      }
    }
    return '';
  }

  function buildJsonCardPreview(content: any): string {
    let previewContent = ''
    const previewMovieCard = extractPreviewMovieCardFromJson(content)
    const previewPostLink = extractPreviewPostLinkFromJson(content)
    const previewParagraph = extractPreviewParagraphFromJson(content)
    let previewText = ''
    let previewImageUrl = content?.additional?.previewImage?.trim() || ''
    let previewImageAlt = 'Preview image'
    let previewImageTitle = ''

    if (previewMovieCard) {
      previewContent += previewMovieCard
    }

    if (!previewContent && previewPostLink) {
      previewContent += previewPostLink
    }

    if (!previewMovieCard && !previewPostLink && !previewImageUrl) {
      const fallbackImage = extractPreviewImageFromJson(content)
      if (fallbackImage?.url) {
        previewImageUrl = fallbackImage.url
        previewImageAlt = fallbackImage.alt || previewImageAlt
        previewImageTitle = fallbackImage.title || ''
      }
    }

    if (!previewMovieCard && !previewPostLink && shouldRenderInlinePreviewImage(previewImageUrl)) {
      previewContent += processImage(previewImageUrl, '', previewImageAlt, previewImageTitle)
    }

    if (content?.additional?.previewDescription?.trim()) {
      previewText = buildPreviewParagraphFromText(content.additional.previewDescription.trim())
    }
    if (!previewText && previewParagraph) {
      previewText = previewParagraph
    }
    if (previewText) {
      previewContent += previewText
    }

    hasPreview = Boolean(previewContent)
    return previewContent
  }

  function buildHtmlCardPreview(html: string): string {
    const imageRegex = /<preview-image>(.*?)<\/preview-image>/is
    const descriptionRegex = /<preview-description>(.*?)<\/preview-description>/is
    const imageMatch = html.match(imageRegex)
    const descriptionMatch = html.match(descriptionRegex)

    let content = ''
    let previewText = ''
    let previewImageUrl = ''
    let previewImageAlt = ''
    let previewImageTitle = ''

    if (imageMatch && imageMatch[1].trim()) {
      previewImageUrl = imageMatch[1].trim()
    } else {
      const fallbackImage = extractFirstImageFromHtml(html)
      if (fallbackImage?.url) {
        previewImageUrl = fallbackImage.url
        previewImageAlt = fallbackImage.alt || ''
        previewImageTitle = fallbackImage.title || ''
      }
    }

    if (shouldRenderInlinePreviewImage(previewImageUrl)) {
      content += processImage(previewImageUrl, html, previewImageAlt, previewImageTitle)
    }

    if (descriptionMatch && descriptionMatch[1].trim()) {
      previewText = buildPreviewParagraphFromText(descriptionMatch[1].trim())
    }
    if (!previewText) {
      previewText = extractPreviewParagraphFromHtml(html)
    }
    if (previewText) {
      content += previewText
    }

    hasPreview = Boolean(content)
    return content
  }

  function extractPreviewContent(html: string) {
    if (showFullBody || (collapsible && expanded)) {
      const editorContent = parseSerializedEditorModel(html)
      const fullHtml = editorContent ? convertJsonToHtml(html) : html
      const contentHtml = stripLeadingTitleFromHtml(fullHtml)
      return showFullBody ? contentHtml : removeDuplicateLeadingPreviewImage(contentHtml)
    }

    if (collapsible) {
      const editorContent = parseSerializedEditorModel(html)
      if (!editorContent && looksLikeSerializedEditorModel(html)) return ''
      const previewHtml = editorContent ? buildJsonCardPreview(editorContent) : buildHtmlCardPreview(html)
      if (previewHtml) return removeDuplicateLeadingPreviewImage(stripLeadingTitleFromHtml(previewHtml))
      return ''
    }
    // Проверяем, является ли контент JSON или base64
    if (isJsonContent(html)) {
      try {
        const content = parseSerializedEditorModel(html)
        if (!content) return ''
        const previewContent = buildJsonCardPreview(content)

        if (previewContent) {
          return previewContent;
        }

        hasPreview = false;
        return extractPreviewParagraphFromJson(content) || convertJsonToHtml(html);
      } catch (error) {
        console.error('Error processing JSON content:', error);
        return looksLikeSerializedEditorModel(html) ? '' : html;
      }
    }

    // Существующая логика для HTML
    const imageRegex = /<preview-image>(.*?)<\/preview-image>/is;
    const descriptionRegex = /<preview-description>(.*?)<\/preview-description>/is;
    
    const imageMatch = html.match(imageRegex);
    const descriptionMatch = html.match(descriptionRegex);
    
    let content = '';
    let previewText = '';
    let previewImageUrl = '';
    let previewImageAlt = '';
    let previewImageTitle = '';
    
    // Сначала добавляем изображение, если оно есть
    if (imageMatch && imageMatch[1].trim()) {
      previewImageUrl = imageMatch[1].trim();
    } else {
      const fallbackImage = extractFirstImageFromHtml(html);
      if (fallbackImage?.url) {
        previewImageUrl = fallbackImage.url;
        previewImageAlt = fallbackImage.alt || '';
        previewImageTitle = fallbackImage.title || '';
      }
    }

    if (previewImageUrl) {
      content += processImage(previewImageUrl, html, previewImageAlt, previewImageTitle);
    }

    // Затем добавляем описание или первый абзац
    if (descriptionMatch && descriptionMatch[1].trim()) {
      previewText = buildPreviewParagraphFromText(descriptionMatch[1].trim());
    }
    if (!previewText) {
      previewText = extractPreviewParagraphFromHtml(html);
    }
    if (previewText) {
      content += previewText;
    }
    
    // Если есть превью теги, устанавливаем флаг hasPreview
    hasPreview = Boolean(content);
    
    // Если нет превью тегов, обрабатываем обычный HTML
    if (!content) {
      // Создаем временный div для парсинга HTML
      const tempDiv = browser ? document.createElement('div') : null;
      if (tempDiv) {
        tempDiv.innerHTML = html;
        
        // Ищем первое изображение
        const firstImg = tempDiv.querySelector('img');
        if (firstImg) {
          content += processImage(firstImg.src, html, firstImg.alt || '', firstImg.title || '');
        }
        
        const previewParagraph = extractPreviewParagraphFromHtml(tempDiv.innerHTML);
        if (previewParagraph) {
          content += previewParagraph;
        } else if (tempDiv.firstElementChild) {
          content += tempDiv.firstElementChild.outerHTML;
        } else {
          // Если нет разметки, берем первые 250 символов текста
          const text = tempDiv.textContent || '';
          content += `<p>${escapeHtml(text.slice(0, maxPreviewLength))}${text.length > maxPreviewLength ? '...' : ''}</p>`;
        }
      } else {
        // Для серверного рендеринга возвращаем оригинальный HTML
        content = html;
      }
    }
    
    return content || html;
  }

  function sanitizeHtml(html: string) {
    const withNoFollow = addTelegramNoFollow(html)
    const withCompactLinks = normalizeLongLinks(withNoFollow)
    if (browser && DOMPurify) {
      // Обрабатываем изображения
      const processedHtml = withCompactLinks.replace(/<img[^>]+src="([^"]+)"[^>]*>/gi, (match, src) => {
        return processImage(src, html);
      });

      return DOMPurify.sanitize(processedHtml, {
        ALLOWED_TAGS: [
          'p',
          'h1',
          'h2',
          'h3',
          'h4',
          'h5',
          'h6',
          'nav',
          'span',
          'b',
          'i',
          'em',
          'strong',
          'a',
          'button',
          'br',
          'ul',
          'ol',
          'li',
          'img',
          'audio',
          'source',
          'progress',
          'table',
          'thead',
          'tbody',
          'tr',
          'td',
          'th',
          'figure',
          'figcaption',
          'input',
          'blockquote',
          'footer',
          'div',
          'iframe',
        ],
        ALLOWED_ATTR: [
          'href',
          'target',
          'rel',
          'src',
          'srcset',
          'sizes',
          'loading',
          'alt',
          'width',
          'height',
          'value',
          'max',
          'class',
          'title',
          'allow',
          'allowfullscreen',
          'frameborder',
          'referrerpolicy',
          'controls',
          'preload',
          'type',
          'data-option-index',
          'data-compare-position',
          'data-poll-multiple',
          'data-poll-closed',
          'data-poll-locked',
          'data-poll-id',
          'data-rating-block-id',
          'data-rating-value',
          'data-music-provider',
          'data-spoiler-open',
          'data-expandable-image',
          'data-expandable-src',
          'data-post-link-id',
          'data-post-link-needs-hydration',
          'data-post-link-hydrated',
          'data-post-link-title',
          'data-post-link-text',
          'data-post-link-image',
          'data-glossary-term',
          'data-glossary-slug',
          'data-glossary-definition',
          'role',
          'tabindex',
          'aria-expanded',
          'aria-pressed',
          'hidden',
          'id',
          'aria-label',
        ],
      });
    }
    return sanitizePostHtmlUniversal(withCompactLinks);
  }

  function escapeHtml(value: string): string {
    return value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
  }

  function stripHtmlTags(value: string): string {
    if (browser) {
      const temp = document.createElement('div');
      temp.innerHTML = value;
      temp.querySelectorAll('br').forEach((br) => br.replaceWith('\n'));
      return temp.textContent || '';
    }
    return value.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]*>/g, '');
  }

  function slugifyHeadingText(value: string): string {
    const normalized = stripHtmlTags(value)
      .toLowerCase()
      .replace(/&[a-z0-9#]+;/gi, ' ')
      .replace(/[^a-zа-яё0-9]+/gi, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 64)
    return normalized || 'section'
  }

  function buildTocEntries(blocks: any[]): { items: TocEntry[]; byIndex: Map<number, TocEntry> } {
    const items: TocEntry[] = []
    const byIndex = new Map<number, TocEntry>()
    const slugCounts = new Map<string, number>()
    if (!Array.isArray(blocks)) return { items, byIndex }

    blocks.forEach((block, index) => {
      const blockType = String(block?.type || '').toLowerCase()
      if (blockType !== 'header') return
      const level = Number(block?.data?.level)
      if (level !== 2 && level !== 3) return

      const text = stripHtmlTags(String(block?.data?.text || '')).replace(/\s+/g, ' ').trim()
      if (!text) return

      const baseSlug = slugifyHeadingText(text)
      const slugIndex = slugCounts.get(baseSlug) ?? 0
      slugCounts.set(baseSlug, slugIndex + 1)

      const entry: TocEntry = {
        id: slugIndex > 0 ? `${baseSlug}-${slugIndex + 1}` : baseSlug,
        text,
        level: level as 2 | 3,
      }
      items.push(entry)
      byIndex.set(index, entry)
    })

    return { items, byIndex }
  }

  function addTelegramNoFollow(html: string): string {
    if (!html) return html
    if (browser) {
      const temp = document.createElement('div')
      temp.innerHTML = html
      const links = temp.querySelectorAll('a[href]')
      links.forEach((link) => {
        const href = link.getAttribute('href') || ''
        if (href.includes('t.me/')) {
          const rel = link.getAttribute('rel') || ''
          const relParts = new Set(rel.split(/\s+/).filter(Boolean))
          relParts.add('nofollow')
          relParts.add('noopener')
          link.setAttribute('rel', Array.from(relParts).join(' '))
        }
      })
      return temp.innerHTML
    }
    return html.replace(
      /<a\b([^>]*?)href=(["'])([^"']*t\.me\/[^"']*)\2([^>]*?)>/gi,
      (match, pre, quote, href, post) => {
        const hasRel = /\srel=/.test(match)
        if (hasRel) {
          return match.replace(/\srel=(["'])([^"']*)\1/i, (_m, q, rel) => {
            const relParts = new Set(rel.split(/\s+/).filter(Boolean))
            relParts.add('nofollow')
            relParts.add('noopener')
            return ` rel=${q}${Array.from(relParts).join(' ')}${q}`
          })
        }
        return `<a${pre}href=${quote}${href}${quote}${post} rel="nofollow noopener">`
      }
    )
  }

  function truncateMiddle(value: string, maxLength = 52): string {
    if (value.length <= maxLength) return value
    const visibleLength = Math.max(8, maxLength - 1)
    const leftLength = Math.ceil(visibleLength * 0.6)
    const rightLength = Math.max(4, visibleLength - leftLength)
    return `${value.slice(0, leftLength)}…${value.slice(-rightLength)}`
  }

  function normalizeComparableUrl(value: string): string {
    return value
      .trim()
      .replace(/^https?:\/\//i, '')
      .replace(/^www\./i, '')
      .replace(/\/+$/g, '')
      .replace(/\s+/g, '')
      .toLowerCase()
  }

  function buildCompactLinkLabel(href: string, maxLength = 52): string {
    try {
      const parsed = new URL(href)
      const host = parsed.hostname.replace(/^www\./i, '')
      const path = parsed.pathname === '/' ? '' : parsed.pathname
      const query = parsed.search || ''
      const hash = parsed.hash || ''
      const visible = `${host}${path}${query}${hash}`
      return truncateMiddle(visible, maxLength)
    } catch {
      return truncateMiddle(href, maxLength)
    }
  }

  function normalizeLongLinks(html: string): string {
    if (!html) return html

    if (browser) {
      const temp = document.createElement('div')
      temp.innerHTML = html
      temp.querySelectorAll('a[href]').forEach((link) => {
        const href = link.getAttribute('href') || ''
        const text = (link.textContent || '').trim()
        if (!href || !text) return
        if (normalizeComparableUrl(text) !== normalizeComparableUrl(href)) return

        const compactLabel = buildCompactLinkLabel(href)
        if (compactLabel === text) return

        link.textContent = compactLabel
        if (!link.getAttribute('title')) {
          link.setAttribute('title', href)
        }
      })
      return temp.innerHTML
    }

    return html.replace(
      /<a\b([^>]*?)href=(["'])([^"']+)\2([^>]*)>([^<]+)<\/a>/gi,
      (match, pre, quote, href, post, text) => {
        const plainText = String(text || '').trim()
        if (!plainText) return match
        if (normalizeComparableUrl(plainText) !== normalizeComparableUrl(href)) return match

        const compactLabel = buildCompactLinkLabel(href)
        if (compactLabel === plainText) return match

        const titleAttr = /\stitle=/.test(match) ? '' : ` title=${quote}${href}${quote}`
        return `<a${pre}href=${quote}${href}${quote}${post}${titleAttr}>${escapeHtml(compactLabel)}</a>`
      }
    )
  }

  $: {
    isFirstImage = true;
    firstImageUrl = null;
    firstImageSrcset = null;
    hasPreview = false;
    previewWasTrimmed = false;
    const renderBody = !showFullBody && collapsible && expanded && fullBody ? fullBody : body;
    processedBody = extractPreviewContent(renderBody);
    if (!showFullBody && collapsible && !expanded) {
      const previewText = normalizePreviewCompareText(processedBody);
      const sourceText = extractSourcePlainText(body);
      previewCanExpand =
        canExpandPreview ||
        previewWasTrimmed ||
        Boolean(postId && looksTrimmedPreview(processedBody)) ||
        Boolean(sourceText && sourceText.length > previewText.length + 8);
    } else {
      previewCanExpand = false;
    }
    void externalPreviewImageUrl
    void canExpandPreview
    void pollRenderState
    void postRatingsRenderState
    void expanded
    void fullBody
  }

  $: if (browser && allowPollVoting && postId && $siteToken) {
    void restoreInlinePollState()
  }

  // Сбрасываем состояние превью только при смене исходного контента/режима отображения
  $: {
    const nextBodySourceKey = `${postId ?? ''}:${body}`
    if (nextBodySourceKey !== bodySourceKey) {
      bodySourceKey = nextBodySourceKey
      fullBody = null
      fullBodyLoading = false
      fullBodyLoadFailed = false
      if (!showFullBody && collapsible) {
        expanded = false
        hasOverflow = false
        hadOverflow = false
      } else {
        expanded = true
        hasOverflow = false
        hadOverflow = false
      }
    }
    void showFullBody
    void collapsible
    void externalPreviewImageUrl
  }

  onMount(() => {
    if (!browser) return
    void restoreInlinePollState()
    const clickHandler = (event: Event) => {
      const target = event.target as HTMLElement | null
      const clickedImage = target?.closest('img') as HTMLImageElement | null
      if (isExpandableImage(clickedImage)) {
        event.preventDefault()
        event.stopPropagation()
        openExpandedImage(clickedImage)
        return
      }
      const spoilerTrigger = target?.closest('.post-spoiler__trigger') as HTMLElement | null
      if (spoilerTrigger && element?.contains(spoilerTrigger)) {
        const spoilerElement = spoilerTrigger.closest('.post-spoiler') as HTMLElement | null
        if (!spoilerElement || !element?.contains(spoilerElement)) return
        event.preventDefault()
        event.stopPropagation()
        toggleSpoilerBlock(spoilerElement)
        return
      }
      const mapElement = target?.closest('.post-map') as HTMLElement | null
      if (mapElement && element?.contains(mapElement)) {
        event.preventDefault()
        event.stopPropagation()
        openMapModal(mapElement)
        return
      }
      const ratingButton = target?.closest('.post-inline-rating__item') as HTMLElement | null
      if (ratingButton && element?.contains(ratingButton)) {
        void handlePostRatingClick(event)
        return
      }
      void handlePollClick(event)
    }
    const keydownHandler: EventListener = (event) => {
      const keyboardEvent = event as KeyboardEvent
      if (keyboardEvent.key !== 'Enter' && keyboardEvent.key !== ' ') return
      const target = keyboardEvent.target as HTMLElement | null
      const spoilerTrigger = target?.closest('.post-spoiler__trigger') as HTMLElement | null
      if (!spoilerTrigger || !element?.contains(spoilerTrigger)) return
      const spoilerElement = spoilerTrigger.closest('.post-spoiler') as HTMLElement | null
      if (!spoilerElement || !element?.contains(spoilerElement)) return
      keyboardEvent.preventDefault()
      keyboardEvent.stopPropagation()
      toggleSpoilerBlock(spoilerElement)
    }
    element?.addEventListener('click', clickHandler)
    element?.addEventListener('keydown', keydownHandler)
    setTimeout(setupGalleries, 0);
    setTimeout(setupImageComparisons, 0);
    void hydratePostLinkCards()
    setTimeout(() => {
      if (!element) return
      if (!collapsible || showFullBody) {
        hasOverflow = false
        return
      }
      // If it doesn't overflow in collapsed mode, show it fully.
      hasOverflow = element.scrollHeight > element.clientHeight + 4
      if (hasOverflow) {
        hadOverflow = true
      }
      if (!hasOverflow && !previewCanExpand) {
        expanded = true
      }
    }, 50)
    return () => {
      element?.removeEventListener('click', clickHandler)
      element?.removeEventListener('keydown', keydownHandler)
    }
  });

  afterUpdate(() => {
    if (!browser) return;
    if (processedBody !== lastProcessedBody) {
      lastProcessedBody = processedBody;
    }
    setTimeout(setupGalleries, 0);
    setTimeout(setupImageComparisons, 0);
    void hydratePostLinkCards()
    setTimeout(() => {
      if (!element) return
      if (!collapsible || showFullBody) {
        hasOverflow = false
        return
      }
      if (expanded) {
        hasOverflow = false
        return
      }
      hasOverflow = element.scrollHeight > element.clientHeight + 4
      if (hasOverflow) {
        hadOverflow = true
      }
      if (!hasOverflow && !previewCanExpand) {
        expanded = true
      }
    }, 0)
  });

  // Добавляем preload для первого изображения
  $: if (firstImageUrl && browser) {
    addPreloadLink(firstImageUrl, firstImageSrcset);
  }

  // Добавляем preload в head при SSR
  export function preloadData() {
    if (!browser && firstImageUrl) {
      return `
        <link 
          rel="preload" 
          as="image" 
          href="${firstImageUrl}" 
          ${firstImageSrcset ? `imagesrcset="${firstImageSrcset}"` : ''} 
          fetchpriority="high"
          data-post-image
        />
      `;
    }
    return '';
  }

</script>

<div class="post-body-wrapper relative">
  <svelte:element
    this={htmlElement}
    style={$$props.style ?? ''}
    class="post-content text-base {$$props.class ?? ''} {collapsible && !showFullBody && !expanded ? 'post-collapsed' : ''}"
    bind:this={element}
    use:glossaryTermClickHandler
  >
    {@html sanitizeHtml(processedBody)}
  </svelte:element>

  {#if collapsible && !showFullBody && expanded && hadOverflow}
    <button
      type="button"
      class="sr-only"
      data-post-action-toggle-expand
      on:click={toggleExpand}
      aria-label="Свернуть пост"
    >
      Свернуть пост
    </button>
  {/if}

  {#if collapsible && !showFullBody && !expanded && (hasOverflow || previewCanExpand || fullBodyLoadFailed)}
    <div class="post-expand-overlay pointer-events-none absolute inset-x-0 bottom-0 flex justify-center pt-16">
      <div class="pointer-events-auto flex justify-center w-full bg-gradient-to-b from-transparent to-white dark:to-zinc-900 pb-3">
        <button
          type="button"
          data-post-action-toggle-expand
          class="post-expand-button mt-6"
          on:click={toggleExpand}
          disabled={fullBodyLoading}
          aria-busy={fullBodyLoading}
          aria-label={fullBodyLoading ? 'Загружаем полный текст' : 'Показать полностью'}
        >
          {#if fullBodyLoading}
            <span class="post-expand-spinner" aria-hidden="true"></span>
          {:else}
            <Icon src={ChevronDown} size="20" mini />
          {/if}
        </button>
      </div>
    </div>
  {/if}
</div>

<style lang="postcss">
  .post-collapsed {
    max-height: 600px;
    overflow: hidden;
  }

  .post-expand-button {
    display: inline-flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    border: 1px solid rgb(226 232 240);
    background: rgb(255 255 255 / 0.96);
    color: rgb(51 65 85);
    box-shadow: 0 6px 18px rgb(15 23 42 / 0.12);
    transition:
      transform 0.15s ease,
      box-shadow 0.15s ease,
      border-color 0.15s ease;
  }

  .post-expand-button:hover {
    transform: translateY(1px);
    border-color: rgb(203 213 225);
    box-shadow: 0 8px 24px rgb(15 23 42 / 0.16);
  }

  .post-expand-button:disabled {
    cursor: wait;
    opacity: 0.78;
    transform: none;
  }

  .post-expand-spinner {
    width: 1rem;
    height: 1rem;
    border-radius: 999px;
    border: 2px solid currentColor;
    border-right-color: transparent;
    animation: post-expand-spin 0.7s linear infinite;
  }

  @keyframes post-expand-spin {
    to {
      transform: rotate(360deg);
    }
  }

  :global(.dark) .post-expand-button {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27 / 0.96);
    color: rgb(228 228 231);
    box-shadow: 0 6px 18px rgb(0 0 0 / 0.3);
  }
  
  .custom-gradient {
    background: linear-gradient(to bottom, 
      rgb(243 244 246) 0%, 
      rgb(229 231 235) 50%, 
      rgb(156 163 175) 100%
    ) !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    color: transparent !important;
  }

  :global(.dark) .custom-gradient {
    background: linear-gradient(to bottom, 
      rgb(243 244 246) 0%, 
      rgb(229 231 235) 30%, 
      rgb(156 163 175) 70%, 
      rgb(107 114 128) 100%
    ) !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    color: transparent !important;
  }

  .test-gradient {
    background: linear-gradient(to bottom, 
      rgb(239 68 68) 0%, 
      rgb(234 179 8) 50%, 
      rgb(34 197 94) 100%
    ) !important;
    -webkit-background-clip: text !important;
    background-clip: text !important;
    color: transparent !important;
  }

  :global(.post-content pre) {
    @apply bg-slate-100 dark:bg-zinc-800 rounded-lg p-4 my-4 overflow-x-auto;
  }

  :global(.post-content pre code) {
    @apply font-mono text-sm text-slate-800 dark:text-zinc-200;
  }

  :global(.post-content blockquote) {
    @apply border-l-4 pl-4 my-4;
    border-left-color: rgb(234 88 12 / var(--tw-bg-opacity, 1));
  }

  :global(.dark .post-content blockquote) {
    @apply border-zinc-700;
  }

  /* Стили для параграфов в PostBody */
  :global(.post-content p) {
    margin: 1rem 0;
    overflow-wrap: break-word;
    word-wrap: break-word;
    word-break: break-word;
    min-width: 0;
  }

  :global(.post-content a) {
    overflow-wrap: anywhere;
    word-break: break-word;
  }

  :global(.post-content .image-alt-text) {
    @apply text-sm text-slate-600 dark:text-zinc-400 text-center mt-2;
  }

  :global(.post-content img:not(.post-image-compare__image):not(.post-quote__author-photo)) {
    cursor: zoom-in;
  }

  :global(.post-content .featured-gallery-thumb img) {
    cursor: pointer;
  }

  :global(.post-content blockquote footer) {
    @apply mt-2 text-sm text-slate-500 dark:text-zinc-400 not-italic;
  }

  :global(.post-content .post-quote__footer) {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  :global(.post-content .post-quote__caption) {
    color: inherit;
  }

  :global(.post-content .post-quote__author) {
    display: inline-flex;
    align-items: center;
    gap: 0.7rem;
  }

  :global(.post-content .post-quote__author-photo) {
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 999px;
    object-fit: cover;
    flex-shrink: 0;
    border: 1px solid rgba(148, 163, 184, 0.28);
  }

  :global(.post-content .post-quote__author-name) {
    color: rgb(15 23 42);
    font-weight: 500;
    line-height: 1.35;
  }

  :global(.dark .post-content .post-quote__author-name) {
    color: rgb(228 228 231);
  }

  :global(.post-content .post-gallery) {
    @apply my-4;
  }

  :global(.post-content .post-divider) {
    margin: 1.35rem 0;
    height: 1px;
    border-radius: 999px;
    background:
      linear-gradient(
        90deg,
        rgba(148, 163, 184, 0) 0%,
        rgba(251, 191, 36, 0.28) 18%,
        rgba(251, 191, 36, 0.68) 50%,
        rgba(251, 191, 36, 0.28) 82%,
        rgba(148, 163, 184, 0) 100%
      );
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.05);
  }

  :global(.dark .post-content .post-divider) {
    background:
      linear-gradient(
        90deg,
        rgba(63, 63, 70, 0) 0%,
        rgba(251, 191, 36, 0.22) 18%,
        rgba(251, 191, 36, 0.46) 50%,
        rgba(251, 191, 36, 0.22) 82%,
        rgba(63, 63, 70, 0) 100%
      );
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.05);
  }

  :global(.post-content .post-toc) {
    margin: 1rem 0 1.2rem;
    border-radius: 1rem;
    border: 1px solid rgba(251, 191, 36, 0.34);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.18), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.9rem 1rem 0.95rem;
  }

  :global(.post-content .post-toc__title) {
    color: #fde68a;
    font-size: 0.76rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 0.65rem;
  }

  :global(.post-content .post-toc__list) {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: 0.5rem;
  }

  :global(.post-content .post-toc__item) {
    margin: 0;
    padding: 0;
  }

  :global(.post-content .post-toc__item--level-3) {
    padding-left: 1rem;
  }

  :global(.post-content .post-toc__link) {
    display: inline-flex;
    align-items: flex-start;
    gap: 0.55rem;
    color: #f8fafc;
    font-size: 0.96rem;
    line-height: 1.4;
    text-decoration: none;
  }

  :global(.post-content .post-toc__link::before) {
    content: '';
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 999px;
    margin-top: 0.42rem;
    flex-shrink: 0;
    background: linear-gradient(135deg, rgba(251, 191, 36, 0.98), rgba(245, 158, 11, 0.92));
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.2);
  }

  :global(.post-content .post-toc__item--level-3 .post-toc__link::before) {
    width: 0.36rem;
    height: 0.36rem;
    margin-top: 0.48rem;
    opacity: 0.88;
  }

  :global(.post-content .post-toc__link:hover) {
    color: #fde68a;
    text-decoration: underline;
    text-underline-offset: 0.16em;
  }

  :global(.post-content h2[id]),
  :global(.post-content h3[id]) {
    scroll-margin-top: 6rem;
  }

  :global(.post-content .post-inline-rating) {
    margin: 1.1rem 0;
    border-radius: 1rem;
    border: 1px solid rgba(251, 191, 36, 0.34);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.2), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: #f8fafc;
    padding: 1rem 1.1rem;
  }

  :global(.post-content .post-inline-rating__eyebrow) {
    color: #fde68a;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  :global(.post-content .post-inline-rating__content) {
    margin-top: 0.55rem;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: center;
  }

  :global(.post-content .post-inline-rating__scale) {
    display: grid;
    grid-template-columns: repeat(10, minmax(0, 1fr));
    gap: 0.35rem;
    padding: 0.35rem;
    border-radius: 1rem;
    background: rgba(15, 23, 42, 0.26);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
  }

  :global(.post-content .post-inline-rating__item) {
    min-width: 0;
    height: 2.8rem;
    border: 0;
    border-radius: 0.8rem;
    background: rgba(255, 255, 255, 0.04);
    color: rgba(241, 245, 249, 0.9);
    font-size: 1rem;
    font-weight: 800;
    cursor: pointer;
    transition:
      transform 0.18s ease,
      background 0.18s ease,
      color 0.18s ease,
      box-shadow 0.18s ease;
  }

  :global(.post-content .post-inline-rating__item:hover) {
    transform: translateY(-1px);
    background: rgba(245, 191, 64, 0.18);
    color: #fff6d6;
    box-shadow: inset 0 0 0 1px rgba(245, 191, 64, 0.34);
  }

  :global(.post-content .post-inline-rating__item.is-selected) {
    background: linear-gradient(135deg, rgba(245, 191, 64, 0.92), rgba(251, 191, 36, 0.76));
    color: #1f2937;
    box-shadow:
      0 12px 26px rgba(245, 191, 64, 0.22),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }

  :global(.post-content .post-inline-rating__stats) {
    min-width: 9rem;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
    color: rgba(226, 232, 240, 0.86);
  }

  :global(.post-content .post-inline-rating__average) {
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 900;
    line-height: 0.95;
    color: #fff2bf;
  }

  :global(.post-content .post-inline-rating__meta) {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.05rem;
    font-size: 0.82rem;
    line-height: 1.3;
  }

  :global(.post-content .post-inline-poll) {
    margin: 1.1rem 0;
    border-radius: 1rem;
    border: 1px solid rgba(251, 191, 36, 0.34);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.18), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.9rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }

  :global(.post-content .post-inline-poll__head) {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  :global(.post-content .post-inline-poll__eyebrow) {
    color: #fde68a;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  :global(.post-content .post-inline-poll__question) {
    color: #fff;
    font-size: 1.02rem;
    font-weight: 700;
    line-height: 1.3;
  }

  :global(.post-content .post-inline-poll__mode) {
    color: #cbd5e1;
    font-size: 0.8rem;
    line-height: 1.4;
  }

  :global(.post-content .post-inline-poll__options) {
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  :global(.post-content .post-inline-poll__option) {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.72rem;
    align-items: start;
    padding: 0.7rem 0.78rem;
    border-radius: 0.82rem;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: rgba(15, 23, 42, 0.38);
    cursor: pointer;
    transition: border-color 0.18s ease, transform 0.18s ease, background 0.18s ease;
  }

  :global(.post-content .post-inline-poll__option:hover) {
    transform: translateY(-1px);
    border-color: rgba(251, 191, 36, 0.42);
    background: rgba(15, 23, 42, 0.48);
  }

  :global(.post-content .post-inline-poll__option--locked) {
    cursor: default;
  }

  :global(.post-content .post-inline-poll__option--locked:hover) {
    transform: none;
    border-color: rgba(255, 255, 255, 0.12);
    background: rgba(15, 23, 42, 0.38);
  }

  :global(.post-content .post-inline-poll__option--choice) {
    min-height: 3.25rem;
  }

  :global(.post-content .post-inline-poll__option--result) {
    cursor: default;
  }

  :global(.post .post-content .post-inline-poll__option.is-selected),
  :global(.post .post-content .post-inline-poll__option--selected-vote) {
    border-color: rgba(251, 191, 36, 0.46);
    background: rgba(30, 41, 59, 0.52);
  }

  :global(.post .post-content .post-inline-poll__option.is-selected:hover),
  :global(.post .post-content .post-inline-poll__option--selected-vote:hover) {
    border-color: rgba(251, 191, 36, 0.46);
    background: rgba(30, 41, 59, 0.52);
  }

  :global(.post-content .post-inline-poll__control) {
    position: relative;
    width: 1.15rem;
    height: 1.15rem;
    margin-top: 0.1rem;
    flex: 0 0 auto;
  }

  :global(.post-content .post-inline-poll__control input) {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
  }

  :global(.post-content .post-inline-poll__marker) {
    position: absolute;
    inset: 0;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.42);
    background: rgba(15, 23, 42, 0.5);
    transition: border-color 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
  }

  :global(.post-content .post-inline-poll__control input[type='checkbox'] + .post-inline-poll__marker) {
    border-radius: 0.35rem;
  }

  :global(.post-content .post-inline-poll__control input:checked + .post-inline-poll__marker) {
    border-color: rgba(251, 191, 36, 0.92);
    background:
      radial-gradient(circle at 50% 50%, rgba(251, 191, 36, 0.95) 0 34%, transparent 35%),
      rgba(251, 191, 36, 0.18);
    box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.14);
  }

  :global(.post-content .post-inline-poll__option.is-selected .post-inline-poll__marker) {
    border-color: rgba(251, 191, 36, 0.92);
    background:
      radial-gradient(circle at 50% 50%, rgba(251, 191, 36, 0.95) 0 34%, transparent 35%),
      rgba(251, 191, 36, 0.18);
    box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.14);
  }

  :global(.post-content .post-inline-poll__checkmark) {
    width: 1.15rem;
    height: 1.15rem;
    margin-top: 0.1rem;
    flex: 0 0 auto;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    background: rgba(251, 191, 36, 0.18);
    color: #fde68a;
    font-size: 0.78rem;
    font-weight: 800;
    line-height: 1;
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.28);
  }

  :global(.post-content .post-inline-poll__checkmark--empty) {
    background: transparent;
    box-shadow: none;
    color: transparent;
  }

  :global(.post-content .post-inline-poll__option-main) {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  :global(.post-content .post-inline-poll__option-row) {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 0.75rem;
  }

  :global(.post-content .post-inline-poll__option-text) {
    color: #f8fafc;
    font-size: 0.92rem;
    line-height: 1.45;
  }

  :global(.post-content .post-inline-poll__option-percent) {
    flex: 0 0 auto;
    color: #fde68a;
    font-size: 0.84rem;
    font-weight: 700;
    line-height: 1.2;
  }

  :global(.post-content .post-inline-poll__progress) {
    width: 100%;
    height: 0.5rem;
    appearance: none;
    border: none;
    overflow: hidden;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.2);
  }

  :global(.post-content .post-inline-poll__progress::-webkit-progress-bar) {
    background: rgba(148, 163, 184, 0.2);
    border-radius: 999px;
  }

  :global(.post-content .post-inline-poll__progress::-webkit-progress-value) {
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(252, 211, 77, 0.72), rgba(245, 158, 11, 0.98));
  }

  :global(.post-content .post-inline-poll__progress::-moz-progress-bar) {
    border-radius: 999px;
    background: linear-gradient(90deg, rgba(252, 211, 77, 0.72), rgba(245, 158, 11, 0.98));
  }

  :global(.post-content .post-inline-poll__progress.is-selected::-webkit-progress-value) {
    background: linear-gradient(90deg, rgba(252, 211, 77, 0.84), rgba(251, 191, 36, 1));
  }

  :global(.post-content .post-inline-poll__progress.is-selected::-moz-progress-bar) {
    background: linear-gradient(90deg, rgba(252, 211, 77, 0.84), rgba(251, 191, 36, 1));
  }

  :global(.post-content .post-inline-poll__option-meta) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    color: rgba(226, 232, 240, 0.76);
    font-size: 0.78rem;
    line-height: 1.35;
  }

  :global(.post-content .post-inline-poll__option-badge) {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border-radius: 999px;
    padding: 0.16rem 0.48rem;
    background: rgba(251, 191, 36, 0.16);
    color: #fde68a;
    font-weight: 600;
  }

  :global(.post-content .post-inline-poll__footer) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    color: rgba(226, 232, 240, 0.72);
    font-size: 0.8rem;
    line-height: 1.4;
  }

  :global(.post-content .post-inline-poll__footer--compact) {
    justify-content: flex-start;
  }

  :global(.dark .post-content .post-inline-poll) {
    border-color: rgba(251, 191, 36, 0.22);
  }

  @media (max-width: 720px) {
    :global(.post-content .post-inline-rating__content) {
      grid-template-columns: 1fr;
    }

    :global(.post-content .post-inline-rating__stats) {
      align-items: flex-start;
    }

    :global(.post-content .post-inline-rating__meta) {
      align-items: flex-start;
    }

    :global(.post-content .post-inline-rating__scale) {
      grid-template-columns: repeat(5, minmax(0, 1fr));
    }
  }

  :global(.post-content .post-gallery img) {
    @apply w-full h-auto block object-cover;
  }

  :global(.post-content .post-gallery.featured-gallery) {
    @apply flex flex-col gap-3;
  }

  :global(.post-content .featured-gallery-main img) {
    @apply w-full rounded-lg bg-slate-100 dark:bg-zinc-800 object-cover;
    height: 450px;
  }

  :global(.post-content .featured-gallery-thumbs) {
    @apply grid grid-cols-5 gap-2;
  }

  :global(.post-content .featured-gallery-thumb) {
    @apply cursor-pointer rounded-lg border-0 bg-transparent p-0;
  }

  :global(.post-content .featured-gallery-thumb img) {
    @apply w-full h-20 rounded-lg object-cover bg-slate-100 dark:bg-zinc-800;
  }

  :global(.post-content .featured-gallery-thumb.active img) {
    @apply ring-2 ring-blue-500;
  }

  :global(.post-content .post-image-compare) {
    margin: 1rem 0;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  :global(.post-content .post-image-compare__viewport) {
    position: relative;
    border-radius: 0.9rem;
    overflow: hidden;
    border: 1px solid rgb(226 232 240);
    background: rgb(248 250 252);
    aspect-ratio: 16 / 9;
  }

  :global(.dark .post-content .post-image-compare__viewport) {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
  }

  :global(.post-content .post-image-compare__image) {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  :global(.post-content .post-image-compare__overlay) {
    position: absolute;
    inset: 0;
    width: 100%;
    overflow: hidden;
    clip-path: inset(0 50% 0 0);
    -webkit-clip-path: inset(0 50% 0 0);
    pointer-events: none;
  }

  :global(.post-content .post-image-compare__divider) {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 2px;
    transform: translateX(-50%);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.18);
    pointer-events: auto;
    cursor: ew-resize;
    touch-action: none;
    z-index: 2;
  }

  :global(.post-content .post-image-compare__knob) {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 2.15rem;
    height: 2.15rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.75);
    background: rgba(255, 255, 255, 0.95);
    transform: translate(-50%, -50%);
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.28);
  }

  :global(.dark .post-content .post-image-compare__knob) {
    border-color: rgba(113, 113, 122, 0.85);
    background: rgba(24, 24, 27, 0.95);
  }

  :global(.post-content .post-image-compare__viewport) {
    cursor: ew-resize;
    touch-action: none;
  }

  :global(.post-content .post-image-compare[data-compare-dragging='1']) {
    user-select: none;
  }

  :global(.post-content .post-image-compare__caption) {
    margin: 0;
    font-size: 0.86rem;
    color: rgb(71 85 105);
    text-align: center;
  }

  :global(.dark .post-content .post-image-compare__caption) {
    color: rgb(161 161 170);
  }

  :global(.post-content .post-movie-card) {
    margin: 1rem 0;
    border-radius: 0.95rem;
    border: 1px solid rgba(251, 191, 36, 0.4);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.24), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.85rem;
    display: grid;
    grid-template-columns: minmax(0, 124px) minmax(0, 1fr);
    gap: 0.75rem;
    align-items: start;
  }

  :global(.post-content .post-movie-card__poster) {
    width: 100%;
    border-radius: 0.75rem;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(15, 23, 42, 0.5);
  }

  :global(.post-content .post-movie-card__poster img) {
    display: block;
    width: 100%;
    height: auto;
    object-fit: cover;
    aspect-ratio: 2 / 3;
  }

  :global(.post-content .post-movie-card__content) {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  :global(.post-content .post-movie-card__chips) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  :global(.post-content .post-movie-card__chip) {
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.38);
    background: rgba(15, 23, 42, 0.42);
    color: #fde68a;
    font-size: 0.72rem;
    line-height: 1.1;
    padding: 0.24rem 0.58rem;
  }

  :global(.post-content .post-movie-card__chip--rating) {
    font-weight: 700;
  }

  :global(.post-content .post-movie-card__chip--green) {
    border-color: rgba(34, 197, 94, 0.45);
    background: rgba(22, 101, 52, 0.25);
    color: #86efac;
  }

  :global(.post-content .post-movie-card__chip--yellow) {
    border-color: rgba(250, 204, 21, 0.5);
    background: rgba(161, 98, 7, 0.24);
    color: #fde68a;
  }

  :global(.post-content .post-movie-card__chip--red) {
    border-color: rgba(239, 68, 68, 0.46);
    background: rgba(153, 27, 27, 0.24);
    color: #fca5a5;
  }

  :global(.post-content .post-movie-card__title) {
    margin: 0;
    color: #fff;
    font-size: 1.2rem;
    line-height: 1.2;
    font-weight: 700;
  }

  :global(.post-content .post-movie-card__subtitle) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.92rem;
    line-height: 1.35;
  }

  :global(.post-content .post-movie-card__meta) {
    display: grid;
    gap: 0.45rem;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  }

  :global(.post-content .post-movie-card__meta-item) {
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 0.7rem;
    background: rgba(15, 23, 42, 0.42);
    padding: 0.48rem 0.62rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  :global(.post-content .post-movie-card__meta-label) {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: #94a3b8;
  }

  :global(.post-content .post-movie-card__meta-value) {
    color: #f8fafc;
    font-size: 0.86rem;
    line-height: 1.35;
  }

  :global(.post-content .post-movie-card__meta-link) {
    color: #f59e0b;
    font-size: 0.86rem;
    line-height: 1.35;
    text-decoration: underline;
    text-underline-offset: 2px;
  }

  :global(.post-content .post-movie-card__meta-link:hover) {
    color: #fbbf24;
  }

  :global(.post-content .post-linked-material) {
    margin: 1rem 0;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
  }

  :global(.post-content .post-linked-material__card) {
    display: grid;
    grid-template-columns: minmax(0, 144px) minmax(0, 1fr);
    gap: 0.85rem;
    align-items: stretch;
    border-radius: 1rem;
    border: 1px solid rgba(251, 191, 36, 0.4);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.24), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: inherit;
    text-decoration: none;
    overflow: hidden;
    transition:
      transform 0.18s ease,
      border-color 0.18s ease,
      box-shadow 0.18s ease;
  }

  :global(.post-content .post-linked-material__card--no-image) {
    grid-template-columns: minmax(0, 1fr);
  }

  :global(.post-content .post-linked-material__card:hover) {
    transform: translateY(-1px);
    border-color: rgba(251, 191, 36, 0.5);
    box-shadow: 0 16px 30px rgba(15, 23, 42, 0.16);
    text-decoration: none;
  }

  :global(.post-content .post-linked-material__image) {
    min-height: 140px;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    background: rgba(15, 23, 42, 0.5);
  }

  :global(.post-content .post-linked-material__image img) {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  :global(.post-content .post-linked-material__content) {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
    padding: 0.9rem;
  }

  :global(.post-content .post-linked-material__meta) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem 0.8rem;
    align-items: center;
  }

  :global(.post-content .post-linked-material__author) {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.72rem;
    line-height: 1.2;
    border-radius: 999px;
    padding: 0.24rem 0.58rem;
    background: rgba(15, 23, 42, 0.42);
  }

  :global(.post-content .post-linked-material__author) {
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.14);
  }

  :global(.post-content .post-linked-material__title) {
    margin: 0;
    color: #fff;
    font-size: 1.2rem;
    line-height: 1.2;
    font-weight: 700;
  }

  :global(.post-content .post-linked-material__text) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.55;
  }

  :global(.post-content .post-linked-material__note) {
    border: 1px solid rgba(251, 191, 36, 0.24);
    border-radius: 0.7rem;
    background: rgba(15, 23, 42, 0.58);
    padding: 0.48rem 0.62rem;
  }

  :global(.post-content .post-linked-material__note p) {
    margin: 0;
    color: #f8fafc;
    font-size: 0.86rem;
    line-height: 1.35;
  }

  :global(.post-content .post-linked-material__action) {
    display: inline-flex;
    width: fit-content;
    align-items: center;
    gap: 0.4rem;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.38);
    background: rgba(15, 23, 42, 0.42);
    color: #fde68a;
    font-size: 0.76rem;
    line-height: 1.1;
    font-weight: 700;
    padding: 0.36rem 0.68rem;
  }

  :global(.post-content .post-author-card) {
    margin: 1rem 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    gap: 0.95rem;
    align-items: center;
  }

  :global(.post-content .post-author-card__line) {
    height: 1px;
    background:
      linear-gradient(90deg, rgba(251, 191, 36, 0), rgba(251, 191, 36, 0.6), rgba(251, 191, 36, 0));
  }

  :global(.post-content .post-author-card__body) {
    min-width: 0;
    display: inline-grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.85rem;
    align-items: center;
    padding: 0.48rem 0.9rem 0.48rem 0.48rem;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.36);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.18), rgba(251, 191, 36, 0) 62%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    box-shadow: 0 12px 26px rgba(15, 23, 42, 0.12);
  }

  :global(.post-content .post-author-card__avatar) {
    width: 3rem;
    height: 3rem;
    border-radius: 999px;
    overflow: hidden;
    border: 1px solid rgba(251, 191, 36, 0.36);
    background: rgba(15, 23, 42, 0.58);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: #fde68a;
    font-weight: 800;
    flex-shrink: 0;
  }

  :global(.post-content .post-author-card__avatar img) {
    width: 100%;
    height: 100%;
    display: block;
    object-fit: cover;
  }

  :global(.post-content .post-author-card__content) {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.08rem;
  }

  :global(.post-content .post-author-card__name) {
    color: #fff;
    font-size: 0.98rem;
    line-height: 1.2;
    font-weight: 700;
    text-decoration: underline;
    text-decoration-color: rgba(251, 191, 36, 0.45);
    text-underline-offset: 0.15em;
  }

  :global(.post-content .post-author-card__name:hover) {
    color: #fde68a;
    text-decoration-color: rgba(251, 191, 36, 0.72);
  }

  :global(.post-content .post-author-card__caption) {
    color: #cbd5e1;
    font-size: 0.82rem;
    line-height: 1.35;
  }

  :global(.post-content .post-callout) {
    margin: 1.1rem 0;
    display: grid;
    grid-template-columns: 0.36rem minmax(0, 1fr);
    gap: 0.95rem;
    align-items: stretch;
  }

  :global(.post-content .post-callout__line) {
    width: 100%;
    border-radius: 999px;
    background:
      linear-gradient(180deg, rgba(251, 191, 36, 0.16), rgba(251, 191, 36, 0.85), rgba(251, 191, 36, 0.16));
    box-shadow: 0 0 0 1px rgba(251, 191, 36, 0.12);
  }

  :global(.post-content .post-callout__body) {
    min-width: 0;
    border-radius: 1rem;
    border: 1px solid rgba(251, 191, 36, 0.32);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.18), rgba(251, 191, 36, 0) 62%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    box-shadow: 0 12px 26px rgba(15, 23, 42, 0.12);
    padding: 1rem 1.05rem;
    display: flex;
    flex-direction: column;
    gap: 0.42rem;
  }

  :global(.post-content .post-callout__text) {
    color: #f8fafc;
    font-size: 1rem;
    line-height: 1.7;
    font-weight: 500;
  }

  :global(.post-content .post-movie-time) {
    margin: 0 0.28rem;
    display: inline-flex;
    position: relative;
    vertical-align: baseline;
  }

  :global(.post-content .post-movie-time__trigger) {
    display: inline-flex;
    align-items: center;
    gap: 0.42rem;
    overflow: visible;
    position: relative;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.42);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.2), rgba(251, 191, 36, 0) 62%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: #fde68a;
    padding: 0.28rem 0.62rem 0.28rem 0.42rem;
    cursor: default;
    transition:
      box-shadow 0.2s ease,
      border-color 0.2s ease,
      background 0.2s ease;
  }

  :global(.post-content .post-movie-time__icon) {
    width: 1.32rem;
    height: 1.32rem;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.42);
    background: rgba(15, 23, 42, 0.5);
    display: grid;
    place-items: center;
    font-size: 0.78rem;
    line-height: 1;
    flex-shrink: 0;
  }

  :global(.post-content .post-movie-time__stamp) {
    color: #fde68a;
    font-size: 0.86rem;
    line-height: 1.15;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  :global(.post-content .post-movie-time__details) {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 0.3rem;
    position: absolute;
    left: 0;
    top: calc(100% + 0.38rem);
    z-index: 24;
    padding: 0.56rem 0.66rem;
    border-radius: 0.74rem;
    border: 1px solid rgba(251, 191, 36, 0.38);
    background:
      radial-gradient(120% 140% at 0% 0%, rgba(251, 191, 36, 0.24), rgba(251, 191, 36, 0) 62%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.98), rgba(30, 41, 59, 0.96));
    box-shadow: 0 12px 24px rgba(15, 23, 42, 0.34);
    width: min(15.5rem, calc(100vw - 2.5rem));
    min-height: 5.35rem;
    white-space: normal;
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
    transform: translateY(6px);
    transition:
      opacity 0.18s ease,
      transform 0.24s ease,
      visibility 0s linear 0.24s;
  }

  :global(.post-content .post-movie-time:hover .post-movie-time__trigger) {
    border-color: rgba(251, 191, 36, 0.65);
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.24);
  }

  :global(.post-content .post-movie-time:hover .post-movie-time__details),
  :global(.post-content .post-movie-time:focus-within .post-movie-time__details) {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
    transition-delay: 0s;
  }

  :global(.post-content .post-movie-time__meta) {
    display: block;
    font-size: 0.7rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: #cbd5e1;
    opacity: 0.88;
  }

  :global(.post-content .post-movie-time__scene) {
    display: block;
    color: #f8fafc;
    font-size: 0.82rem;
    line-height: 1.28;
    font-weight: 600;
    width: 100%;
    word-break: break-word;
  }

  :global(.post-content .post-movie-time__note) {
    display: block;
    color: #cbd5e1;
    font-size: 0.78rem;
    line-height: 1.26;
    width: 100%;
    word-break: break-word;
  }

  :global(.post-content .post-spoiler) {
    margin: 1rem 0;
    border-radius: 0.9rem;
    border: 1px solid rgba(251, 191, 36, 0.34);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.16), rgba(251, 191, 36, 0) 62%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    overflow: hidden;
  }

  :global(.post-content .post-spoiler__trigger) {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.55rem;
    padding: 0.62rem 0.72rem;
    cursor: pointer;
    user-select: none;
  }

  :global(.post-content .post-spoiler__trigger:focus-visible) {
    outline: 2px solid rgba(251, 191, 36, 0.9);
    outline-offset: -2px;
  }

  :global(.post-content .post-spoiler__title) {
    color: #f8fafc;
    font-size: 0.87rem;
    line-height: 1.3;
    font-weight: 700;
  }

  :global(.post-content .post-spoiler__hint) {
    color: #fde68a;
    font-size: 0.75rem;
    line-height: 1.2;
    white-space: nowrap;
  }

  :global(.post-content .post-spoiler__content) {
    position: relative;
    padding: 0 0.72rem 0.72rem;
    transition: filter 0.2s ease, max-height 0.2s ease;
    max-height: 1000px;
  }

  :global(.post-content .post-spoiler__content p) {
    color: #e2e8f0;
    font-size: 0.9rem;
    line-height: 1.5;
  }

  :global(.post-content .post-spoiler__content > :first-child) {
    margin-top: 0;
  }

  :global(.post-content .post-spoiler__content > :last-child) {
    margin-bottom: 0;
  }

  :global(.post-content .post-spoiler:not(.is-open) .post-spoiler__content) {
    filter: blur(7px);
    max-height: 120px;
    overflow: hidden;
    pointer-events: none;
    user-select: none;
  }

  :global(.post-content .post-spoiler:not(.is-open) .post-spoiler__content::after) {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.04), rgba(15, 23, 42, 0.62));
  }

  :global(.post-content .post-spoiler.is-open .post-spoiler__hint) {
    color: #cbd5e1;
  }

  :global(.post-content .post-music) {
    margin: 1rem 0;
    border-radius: 0.95rem;
    border: 1px solid rgba(251, 191, 36, 0.34);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.18), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.78rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  :global(.post-content .post-music__header) {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    flex-wrap: wrap;
  }

  :global(.post-content .post-music__badge) {
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.38);
    background: rgba(15, 23, 42, 0.45);
    color: #fde68a;
    font-size: 0.7rem;
    line-height: 1.1;
    padding: 0.23rem 0.54rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    font-weight: 700;
  }

  :global(.post-content .post-music__provider) {
    font-size: 0.78rem;
    line-height: 1.2;
    color: #f8fafc;
    font-weight: 600;
  }

  :global(.post-content .post-music__open-link) {
    margin-left: auto;
    color: #f59e0b;
    font-size: 0.78rem;
    text-decoration: underline;
    text-underline-offset: 2px;
    font-weight: 600;
  }

  :global(.post-content .post-music__open-link:hover) {
    color: #fbbf24;
  }

  :global(.post-content .post-music__frame) {
    width: 100%;
    min-height: 152px;
    border: 0;
    border-radius: 0.72rem;
    background: rgba(2, 6, 23, 0.45);
  }

  :global(.post-content .post-music[data-music-provider='yandex_music'] .post-music__frame) {
    min-height: 200px;
  }

  :global(.post-content .post-music__frame--playlist) {
    min-height: 352px;
  }

  :global(.post-content .post-music[data-music-provider='yandex_music'] .post-music__frame--playlist) {
    min-height: 340px;
  }

  :global(.post-content .post-music__caption) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.8rem;
    line-height: 1.35;
  }

  :global(.post-content .post-music--link-only .post-music__fallback) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.8rem;
    line-height: 1.35;
  }

  @media (max-width: 640px) {
    :global(.post-content .post-toc) {
      padding: 0.82rem 0.85rem 0.88rem;
    }

    :global(.post-content .post-toc__item--level-3) {
      padding-left: 0.8rem;
    }

    :global(.post-content .post-linked-material__card) {
      grid-template-columns: 1fr;
    }

    :global(.post-content .post-linked-material__image) {
      min-height: 180px;
    }

    :global(.post-content .post-linked-material__content) {
      padding: 0 0.85rem 0.85rem;
    }

    :global(.post-content .post-movie-card) {
      grid-template-columns: 1fr;
      gap: 0.6rem;
    }

    :global(.post-content .post-movie-card__poster) {
      max-width: 150px;
    }

    :global(.post-content .post-author-card) {
      grid-template-columns: 1fr;
      gap: 0.55rem;
    }

    :global(.post-content .post-author-card__body) {
      width: 100%;
      border-radius: 1rem;
    }

    :global(.post-content .post-callout) {
      grid-template-columns: 1fr;
      gap: 0.55rem;
    }

    :global(.post-content .post-callout__line) {
      height: 4px;
      background:
        linear-gradient(90deg, rgba(251, 191, 36, 0.16), rgba(251, 191, 36, 0.85), rgba(251, 191, 36, 0.16));
    }
  }

  :global(.post-content .post-embed) {
    @apply my-4;
  }

  :global(.post-content .post-embed__responsive) {
    @apply w-full overflow-hidden rounded-lg;
    aspect-ratio: 16 / 9;
  }

  :global(.post-content .post-embed iframe) {
    @apply w-full h-full;
    border: 0;
    display: block;
  }

  :global(.post-content .post-map) {
    position: relative;
    margin: 1rem 0;
    border-radius: 0.9rem;
    overflow: hidden;
    border: 1px solid rgb(226 232 240);
    background: rgb(248 250 252);
    cursor: zoom-in;
  }

  :global(.dark .post-content .post-map) {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
  }

  :global(.post-content .post-map__frame) {
    width: 100%;
    height: 300px;
    border: 0;
    display: block;
    pointer-events: none;
  }

  :global(.post-content .post-map__hint) {
    position: absolute;
    right: 0.75rem;
    bottom: 0.75rem;
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 0.3rem 0.65rem;
    font-size: 0.75rem;
    font-weight: 600;
    color: rgb(30 41 59);
    background: rgba(255, 255, 255, 0.92);
    border: 1px solid rgb(226 232 240);
    pointer-events: none;
  }

  :global(.dark .post-content .post-map__hint) {
    color: rgb(228 228 231);
    background: rgba(24, 24, 27, 0.9);
    border-color: rgb(82 82 91);
  }

  :global(.post-map-modal) {
    position: fixed;
    inset: 0;
    z-index: 3000;
    display: grid;
    place-items: center;
  }

  :global(.post-map-modal__backdrop) {
    position: absolute;
    inset: 0;
    background: rgba(2, 6, 23, 0.65);
    backdrop-filter: blur(2px);
  }

  :global(.post-map-modal__content) {
    position: relative;
    z-index: 1;
    width: min(1200px, 94vw);
    height: min(84vh, 760px);
    border-radius: 1rem;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgb(255 255 255);
    box-shadow: 0 28px 80px rgba(15, 23, 42, 0.28);
  }

  :global(.dark .post-map-modal__content) {
    background: rgb(9 9 11);
    border-color: rgba(82, 82, 91, 0.9);
  }

  :global(.post-map-modal__frame) {
    width: 100%;
    height: 100%;
    border: 0;
    display: block;
  }

  :global(.post-map-modal__close) {
    position: absolute;
    top: 0.7rem;
    right: 0.7rem;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.6);
    background: rgba(255, 255, 255, 0.88);
    color: rgb(15 23 42);
    font-size: 1rem;
    font-weight: 700;
    line-height: 1;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  :global(.dark .post-map-modal__close) {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(24, 24, 27, 0.9);
    color: rgb(228 228 231);
  }

  :global(.post-content .post-audio) {
    @apply my-4;
  }

  :global(.post-content .post-audio audio) {
    @apply w-full;
  }

  :global(.post-content .post-audio-fallback) {
    @apply my-4 text-sm;
  }

  :global(.post-content .post-audio-fallback a) {
    @apply text-blue-600 dark:text-blue-400 hover:underline;
  }

  @media (max-width: 640px) {
    :global(.post-content .post-map__frame) {
      height: 240px;
    }
  }

  @media (max-width: 768px) {
    :global(.post-content .featured-gallery-main img) {
      height: 260px;
    }
  }

  @media (max-width: 640px) {
    :global(.post-content .featured-gallery-thumbs) {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }
  }

  :global(.post-content ul) {
    @apply list-disc list-outside pl-6 my-4;
  }

  :global(.post-content ol) {
    @apply list-decimal list-outside pl-6 my-4;
  }

  :global(.post-content ul li + li),
  :global(.post-content ol li + li) {
    margin-top: 0.5rem;
  }

  :global(.post-content ul.checklist) {
    @apply list-none;
  }

  :global(.post-content ul.checklist li) {
    @apply flex items-start;
  }

  :global(.post-content ul.checklist li input[type="checkbox"]) {
    @apply -ml-6 mr-2 rounded border-slate-300 dark:border-zinc-600 
    text-blue-600 dark:text-blue-400
    focus:ring-blue-500 dark:focus:ring-blue-400;
  }

  :global(.post-content .link) {
    @apply text-blue-600 dark:text-blue-400 hover:underline;
  }

  :global(.post-content .btn-primary) {
    background-color: var(--btn-primary-background);
    color: var(--btn-primary-color);
    border: 1px solid var(--btn-primary-border);
    border-radius: var(--btn-primary-border-radius);
    padding: var(--btn-primary-padding-y) var(--btn-primary-padding-x);
    font-size: var(--btn-primary-font-size);
    font-weight: var(--btn-primary-font-weight);
    line-height: var(--btn-primary-line-height);
    transition: var(--btn-primary-transition);
    box-shadow: var(--btn-primary-shadow);
    width: var(--btn-primary-width);
    display: var(--btn-primary-display);
    align-items: var(--btn-primary-align-items);
    justify-content: var(--btn-primary-justify-content);
  }

  :global(.post-content .btn-primary:hover) {
    background-color: var(--btn-primary-background-hover);
    color: var(--btn-primary-color);
    text-decoration: none;
    box-shadow: var(--btn-primary-shadow-hover);
  }

  :global(.post-content .post-glossary-term) {
    --post-glossary-tooltip-width: min(22rem, calc(100vw - 24px));
    --post-glossary-tooltip-shift-x: 0px;
    display: inline-flex;
    align-items: center;
    position: relative;
    vertical-align: baseline;
    border-radius: 0.18em;
    border-bottom: 1px dashed rgb(14 165 233 / 0.7);
    background: rgb(14 165 233 / 0.08);
    color: rgb(15 118 110);
    padding: 0 0.08em;
    line-height: 1.18;
    cursor: help;
    transition: background-color 0.18s ease, color 0.18s ease;
  }

  :global(.dark .post-content .post-glossary-term) {
    border-bottom-color: rgb(74 222 128 / 0.65);
    background: rgb(34 197 94 / 0.14);
    color: rgb(187 247 208);
  }

  :global(.post-content .post-glossary-term:hover) {
    background: rgb(14 165 233 / 0.16);
  }

  :global(.dark .post-content .post-glossary-term:hover) {
    background: rgb(34 197 94 / 0.22);
  }

  :global(.post-content .post-glossary-term::after) {
    content: attr(data-glossary-definition);
    position: absolute;
    left: 50%;
    bottom: calc(100% + 0.7rem);
    z-index: 20;
    width: var(--post-glossary-tooltip-width);
    transform: translateX(calc(-50% + var(--post-glossary-tooltip-shift-x)));
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.96);
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.22);
    color: white;
    padding: 0.7rem 0.85rem;
    font-size: 0.82rem;
    line-height: 1.45;
    opacity: 0;
    pointer-events: none;
    white-space: normal;
    transition: opacity 0.18s ease, transform 0.18s ease;
  }

  :global(.post-content .post-glossary-term:hover::after),
  :global(.post-content .post-glossary-term.post-glossary-term--active::after) {
    opacity: 1;
    transform: translateX(calc(-50% + var(--post-glossary-tooltip-shift-x))) translateY(-2px);
  }
</style>
