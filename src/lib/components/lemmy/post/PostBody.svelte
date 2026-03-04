<script lang="ts">
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import type { View } from '$lib/settings'
  import { Button, toast } from 'mono-svelte'
  import { ChevronDown, Icon } from 'svelte-hero-icons'
  import { browser } from '$app/environment'
  import { afterUpdate, createEventDispatcher, onMount, tick } from 'svelte'
  import { page } from '$app/stores'
  import { deserializeEditorModel, buildOpenStreetMapEmbedUrl, normalizeOpenStreetMapZoom } from '$lib/util'
  import { buildPostPollVoteUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import {
    isTemplateEditorBlockEnabled,
    type SitePostTemplate,
  } from '$lib/postTemplates'
  
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
            if (!isTelegram && !isOpenStreetMap) {
              node.remove()
              return
            }
            node.setAttribute('loading', 'lazy')
            node.setAttribute(
              'referrerpolicy',
              isOpenStreetMap ? 'no-referrer-when-downgrade' : 'no-referrer'
            )
          }
        })
        purifyConfigured = true
      }
    })
  }

  export let body: string
  export let postId: number | null = null
  export let allowPollVoting = false
  export let title: string | undefined = undefined
  export let template: SitePostTemplate | null | undefined = null
  export let view: View = 'cozy'
  export let clickThrough = false
  export let showFullBody = false
  export let collapsible = false
  
  let htmlElement = 'div'

  export { htmlElement as element }

  const dispatch = createEventDispatcher<{ expand: void }>()

  let expanded = false
  let hasOverflow = false
  let hadOverflow = false
  let element: Element
  let isFirstImage = true;
  let firstImageUrl: string | null = null;
  let firstImageSrcset: string | null = null;
  let hasPreview = false;
  let lastProcessedBody = '';
  let processedBody = '';
  const maxPreviewLength = 250;

  const normalizeTextForCompare = (value: string): string =>
    value
      .replace(/\s+/g, ' ')
      .trim()
      .replace(/[.!?]+$/g, '')
      .trim()
      .toLowerCase()

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
      const firstSrcset = getImgAttr(first, 'srcset');
      if (firstSrcset) {
        mainImage.setAttribute('srcset', firstSrcset);
      }
      const firstSizes = getImgAttr(first, 'sizes');
      if (firstSizes) {
        mainImage.setAttribute('sizes', firstSizes);
      }
      mainImage.alt = getImgAttr(first, 'alt');
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

  const expand = async (event?: Event) => {
    event?.preventDefault()
    event?.stopPropagation()
    if (expanded) return
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

    pollElement.setAttribute('data-poll-voting', '1')
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
        throw new Error(data?.error || 'Не удалось проголосовать')
      }
      if (typeof data.poll_html === 'string' && data.poll_html.trim()) {
        pollElement.outerHTML = data.poll_html
      }
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось проголосовать',
        type: 'error',
      })
    } finally {
      const currentPoll = element?.querySelector<HTMLElement>('.post-poll')
      currentPoll?.removeAttribute('data-poll-voting')
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

    if (pollElement.getAttribute('data-poll-voting') === '1') return
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
    // Пропускаем пустые строки
    if (!content || content.trim() === '') {
      return false;
    }

    // Если контент начинается с < и заканчивается на >, это вероятно HTML
    if (content.trim().startsWith('<') && content.trim().endsWith('>')) {
      return false;
    }

    try {
      // Сначала пробуем парсить как обычный JSON
      const parsed = JSON.parse(content);
      return parsed && typeof parsed === 'object' && 'blocks' in parsed;
    } catch {
      try {
        // Проверяем, похоже ли это на base64
        const isBase64 = /^[A-Za-z0-9+/]*={0,2}$/.test(content);
        
        if (!isBase64) {
          return false;
        }
        
        // Если похоже на base64, пробуем десериализовать
        const decoded = deserializeEditorModel(content);
        return decoded && typeof decoded === 'object' && 'blocks' in decoded;
      } catch {
        return false;
      }
    }
  }

  function processJsonBlock(block: any): string {
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
        ? `<p class="post-movie-time__note">${sceneNote}</p>`
        : ''

      return `<aside class="post-movie-time">
        <div class="post-movie-time__icon" aria-hidden="true">⏱</div>
        <div class="post-movie-time__content">
          <div class="post-movie-time__meta">Таймкод</div>
          <div class="post-movie-time__headline">
            <span class="post-movie-time__stamp">${displayTime}</span>
            <span class="post-movie-time__scene">${sceneTitle}</span>
          </div>
          ${noteHtml}
        </div>
      </aside>`
    }

    switch (block.type) {
      case 'paragraph':
        return `<p>${block.data.text}</p>`;
      case 'header':
        return `<h${block.data.level}>${block.data.text}</h${block.data.level}>`;
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
      case 'quote':
        return `<blockquote>
          <p>${block.data.text}</p>
          ${block.data.caption ? `<footer>${block.data.caption}</footer>` : ''}
        </blockquote>`;
      case 'code':
        return `<pre><code>${block.data.code}</code></pre>`;
      case 'image':
        return processImage(block.data.file.url, '', block.data.file.alt || '', block.data.file.title || '', block.data.file.caption || '');
      case 'gallery':
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
      let content;
      
      // Пробуем парсить как обычный JSON
      try {
        content = JSON.parse(jsonContent);
      } catch {
        // Если не получилось, пробуем десериализовать из base64
        content = deserializeEditorModel(jsonContent);
      }
      
      if (!content.blocks) return '';
      
      // Обрабатываем мета-информацию
      const previewImage = content.additional?.previewImage 
        ? `<preview-image>${content.additional.previewImage}</preview-image>` 
        : '';
      const previewDescription = content.additional?.previewDescription 
        ? `<preview-description>${content.additional.previewDescription}</preview-description>` 
        : '';
      const metaTitle = content.additional?.metaTitle 
        ? `<meta-title>${content.additional.metaTitle}</meta-title>` 
        : '';
      const metaDescription = content.additional?.metaDescription 
        ? `<meta-description>${content.additional.metaDescription}</meta-description>` 
        : '';
        
      const htmlContent = content.blocks
        .map((block: any) => processJsonBlock(block))
        .join('\n');
        
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
      
      // Определяем атрибуты загрузки в зависимости от позиции изображения
      let loadingAttrs = '';
      
      if (isFirstImage) {
        // Первое изображение загружаем с высоким приоритетом и без ленивой загрузки
        loadingAttrs = 'fetchpriority="high"';
        firstImageUrl = minImageUrl;
        firstImageSrcset = srcset;
      } else {
        // Для остальных изображений используем ленивую загрузку
        // Но только если они не в первых 1000 символах контента
        const imagePosition = content.indexOf(imgUrl);
        if (imagePosition > 1000) {
          loadingAttrs = 'loading="lazy"';
        }
      }
      
      isFirstImage = false;
      
      // Добавляем alt, title и caption к атрибутам
      const altAttr = alt ? `alt="${alt}"` : 'alt="Post image"';
      const titleAttr = title ? `title="${title}"` : '';
      const captionHtml = caption ? `<div class="image-alt-text">${caption}</div>` : '';
      
      const imgHtml = `<img 
        src="${minImageUrl}" 
        srcset="${srcset}" 
        sizes="${sizesAttr}" 
        ${loadingAttrs}
        ${altAttr}
        ${titleAttr}
        class="w-full h-auto">
        ${captionHtml}`;

      return imgHtml;
    }
    return `<img src="${imgUrl}" ${alt ? `alt="${alt}"` : 'alt="Post image"'} ${title ? `title="${title}"` : ''} class="w-full h-auto">`;
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
      return { text: `${paragraphText.slice(0, maxPreviewLength).trim()}...`, trimmed: true };
    }
    return { text: paragraphText, trimmed: false };
  }

  function buildPreviewParagraphFromText(rawText: string): string {
    const { text } = trimPreviewText(rawText);
    if (!text) return '';
    return `<p>${escapeHtml(text)}</p>`;
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
        if (!paragraph.textContent) continue;
        const preview = buildPreviewParagraphFromHtml(paragraph.innerHTML, paragraph.textContent);
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

  function extractPreviewContent(html: string) {
    if (showFullBody || collapsible) {
      if (isJsonContent(html)) {
        return stripLeadingTitleFromHtml(convertJsonToHtml(html));
      }
      return stripLeadingTitleFromHtml(html);
    }
    // Проверяем, является ли контент JSON или base64
    if (isJsonContent(html)) {
      try {
        let content;
        
        // Пробуем парсить как обычный JSON
        try {
          content = JSON.parse(html);
        } catch {
          // Если не получилось, пробуем десериализовать из base64
          content = deserializeEditorModel(html);
        }
        
        let previewContent = '';
        const previewParagraph = extractPreviewParagraphFromJson(content);
        let previewText = '';
        let previewImageUrl = content?.additional?.previewImage?.trim() || '';
        let previewImageAlt = 'Preview image';
        let previewImageTitle = '';

        // Сначала добавляем изображение превью, если оно есть
        if (!previewImageUrl) {
          const fallbackImage = extractPreviewImageFromJson(content);
          if (fallbackImage?.url) {
            previewImageUrl = fallbackImage.url;
            previewImageAlt = fallbackImage.alt || previewImageAlt;
            previewImageTitle = fallbackImage.title || '';
          }
        }

        if (previewImageUrl) {
          previewContent += processImage(
            previewImageUrl,
            '',
            previewImageAlt,
            previewImageTitle
          );
        }

        // Затем добавляем описание превью или первый абзац
        if (content?.additional?.previewDescription?.trim()) {
          previewText = buildPreviewParagraphFromText(content.additional.previewDescription.trim());
        }
        if (!previewText && previewParagraph) {
          previewText = previewParagraph;
        }
        if (previewText) {
          previewContent += previewText;
        }

        if (previewContent) {
          hasPreview = true;
          return previewContent;
        }

        hasPreview = false;
        return previewParagraph || convertJsonToHtml(html);
      } catch (error) {
        console.error('Error processing JSON content:', error);
        return html;
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
    if (browser && DOMPurify) {
      // Обрабатываем изображения
      const processedHtml = withNoFollow.replace(/<img[^>]+src="([^"]+)"[^>]*>/gi, (match, src) => {
        return processImage(src, html);
      });

      return DOMPurify.sanitize(processedHtml, {
        ALLOWED_TAGS: [
          'p',
          'b',
          'i',
          'em',
          'strong',
          'a',
          'br',
          'ul',
          'ol',
          'li',
          'img',
          'audio',
          'source',
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
          'class',
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
          'data-poll-id',
        ],
      });
    }
    // Если мы на сервере или DOMPurify еще не загружен, возвращаем исходный HTML
    return withNoFollow;
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
      return temp.textContent || '';
    }
    return value.replace(/<[^>]*>/g, '');
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

  // Сбрасываем флаг при изменении body
  $: {
    isFirstImage = true;
    firstImageUrl = null;
    firstImageSrcset = null;
    hasPreview = false;
    processedBody = extractPreviewContent(body);
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

  onMount(() => {
    if (!browser) return
    const clickHandler = (event: Event) => {
      const target = event.target as HTMLElement | null
      const mapElement = target?.closest('.post-map') as HTMLElement | null
      if (mapElement && element?.contains(mapElement)) {
        event.preventDefault()
        event.stopPropagation()
        openMapModal(mapElement)
        return
      }
      void handlePollClick(event)
    }
    element?.addEventListener('click', clickHandler)
    setTimeout(setupGalleries, 0);
    setTimeout(setupImageComparisons, 0);
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
      if (!hasOverflow) {
        expanded = true
      }
    }, 50)
    return () => {
      element?.removeEventListener('click', clickHandler)
    }
  });

  afterUpdate(() => {
    if (!browser) return;
    if (processedBody !== lastProcessedBody) {
      lastProcessedBody = processedBody;
    }
    setTimeout(setupGalleries, 0);
    setTimeout(setupImageComparisons, 0);
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
      if (!hasOverflow) {
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
    class:pointer-events-none={!showFullBody && !(collapsible && expanded)}
    bind:this={element}
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

  {#if collapsible && !showFullBody && !expanded && hasOverflow}
    <div class="post-expand-overlay pointer-events-none absolute inset-x-0 bottom-0 flex justify-center pt-16">
      <div class="pointer-events-auto flex justify-center w-full bg-gradient-to-b from-transparent to-white dark:to-zinc-900 pb-3">
        <button
          type="button"
          data-post-action-toggle-expand
          class="mt-6 rounded-xl border border-slate-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-200 shadow-sm hover:shadow-md transition"
          on:click={toggleExpand}
        >
          Показать полностью
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

  :global(.post-content blockquote footer) {
    @apply mt-2 text-sm text-slate-500 dark:text-zinc-400 not-italic;
  }

  :global(.post-content .post-gallery) {
    @apply my-4;
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

  :global(.post-content .post-movie-time) {
    margin: 1rem 0;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.75rem;
    border-radius: 0.95rem;
    border: 1px solid rgba(251, 191, 36, 0.45);
    background:
      radial-gradient(130% 140% at 0% 0%, rgba(251, 191, 36, 0.24), rgba(251, 191, 36, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.93));
    color: #e2e8f0;
    padding: 0.8rem 0.9rem;
  }

  :global(.post-content .post-movie-time__icon) {
    width: 2.05rem;
    height: 2.05rem;
    border-radius: 999px;
    border: 1px solid rgba(251, 191, 36, 0.45);
    background: rgba(15, 23, 42, 0.42);
    color: #fde68a;
    display: grid;
    place-items: center;
    font-size: 1rem;
    line-height: 1;
  }

  :global(.post-content .post-movie-time__content) {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  :global(.post-content .post-movie-time__meta) {
    font-size: 0.7rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #94a3b8;
  }

  :global(.post-content .post-movie-time__headline) {
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    align-items: baseline;
  }

  :global(.post-content .post-movie-time__stamp) {
    color: #fde68a;
    font-size: 1.02rem;
    line-height: 1.15;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
  }

  :global(.post-content .post-movie-time__scene) {
    color: #f8fafc;
    font-size: 0.92rem;
    line-height: 1.3;
    font-weight: 600;
  }

  :global(.post-content .post-movie-time__note) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.88rem;
    line-height: 1.45;
  }

  @media (max-width: 640px) {
    :global(.post-content .post-movie-time) {
      grid-template-columns: 1fr;
      gap: 0.55rem;
    }

    :global(.post-content .post-movie-time__icon) {
      width: 1.8rem;
      height: 1.8rem;
    }
  }

  :global(.post-content .post-embed) {
    @apply my-4;
  }

  :global(.post-content .post-embed iframe) {
    @apply w-full rounded-lg;
    border: 0;
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
    @apply list-disc list-outside pl-6 my-4 space-y-2;
  }

  :global(.post-content ol) {
    @apply list-decimal list-outside pl-6 my-4 space-y-2;
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
</style>
