<script lang="ts">
  import { buildCommentsTree } from '$lib/components/lemmy/comment/comments.js'
  import { isImage } from '$lib/ui/image.js'
  import { client, getClient } from '$lib/lemmy.js'
  import CommentForm from '$lib/components/lemmy/comment/CommentForm.svelte'
  import { onMount } from 'svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import { page } from '$app/stores'
  import PostActions from '$lib/components/lemmy/post/PostActions.svelte'
  import {
    ArrowLeft,
    ArrowPath,
    ChevronDoubleUp,
    Icon,
    InformationCircle,
    Home,
    PlusCircle,
    ChatBubbleLeftRight,
    Bookmark,
    BookmarkSlash,
    ArrowUp,
    ArrowDown,
    ChevronLeft,
    ChevronRight,
  } from 'svelte-hero-icons'
  import PostMeta from '$lib/components/lemmy/post/PostMeta.svelte'
  import { Select, removeToast, toast } from 'mono-svelte'
  import type { CommentSortType } from 'lemmy-js-client'
  import { profile } from '$lib/auth.js'
  import { instance } from '$lib/instance.js'
  import { afterNavigate, goto } from '$app/navigation'
  import FormattedNumber from '$lib/components/util/FormattedNumber.svelte'
  import { Button } from 'mono-svelte'
  import EndPlaceholder from '$lib/components/ui/EndPlaceholder.svelte'
  import { userSettings } from '$lib/settings.js'
  import { publishedToDate } from '$lib/components/util/date.js'
  import PostMedia from '$lib/components/lemmy/post/media/PostMedia.svelte'
  import { mediaType } from '$lib/components/lemmy/post/helpers.js'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import Expandable from '$lib/components/ui/Expandable.svelte'
  import { Popover } from 'mono-svelte'
  import { t } from '$lib/translations.js'
  import { resumables } from '$lib/lemmy/item.js'
  import { contentPadding } from '$lib/components/ui/layout/Shell.svelte'
  import Placeholder from '$lib/components/ui/Placeholder.svelte'
  import CommentListVirtualizer from '$lib/components/lemmy/comment/CommentListVirtualizer.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { browser } from '$app/environment'
  import VirtualFeed from '$lib/components/lemmy/post/feed/VirtualFeed.svelte'
  import PostFeed from '$lib/components/lemmy/post/feed/PostFeed.svelte'
  import { postFeed } from '$lib/lemmy/postfeed'
  import {
    parseSerializedEditorModel,
    looksLikeSerializedEditorModel,
    buildOpenStreetMapEmbedUrl,
    normalizeOpenStreetMapZoom,
  } from '$lib/util'
  import { buildPostReadUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'

  export let data

  let ogImage: string | null;

  $: type = mediaType(data.post.post_view.post.url, 'cozy')
  $: featuredPost = data.recommendations?.communityPosts?.posts
    .filter(p => 
      p.post.featured_community && 
      p.community.id === data.post.post_view.community.id &&
      p.post.id !== data.post.post_view.post.id
    )
    .sort((a, b) => 
      new Date(b.post.published).getTime() - new Date(a.post.published).getTime()
    )[0]

  const updateActions = () => {
    // @ts-ignore
    data.contextual = {
      actions: [
        {
          name: $t('post.actions.vote.upvote'),
          icon: ArrowUp,
          handle: async () => {
            data.post.post_view.my_vote = (
              await client().likePost({
                post_id: data.post.post_view.post.id,
                score: data.post.post_view.my_vote == 1 ? 0 : 1,
              })
            ).post_view.my_vote
          },
        },
        {
          name: $t('post.actions.vote.downvote'),
          icon: ArrowDown,
          handle: async () => {
            data.post.post_view.my_vote = (
              await client().likePost({
                post_id: data.post.post_view.post.id,
                score: data.post.post_view.my_vote == -1 ? 0 : -1,
              })
            ).post_view.my_vote
          },
        },
        {
          name: data.post.post_view.saved
            ? $t('post.actions.unsave')
            : $t('post.actions.save'),
          handle: async () => {
            data.post.post_view.saved = (
              await client().savePost({
                post_id: data.post.post_view.post.id,
                save: !data.post.post_view.saved,
              })
            ).post_view.saved
          },
          icon: data.post.post_view.saved ? BookmarkSlash : Bookmark,
        },
      ],
    }
  }

  $: if (data.post) updateActions()

  // Добавляем функцию для создания слага из названия
  function createSlug(title: string): string {
    return title
      .toLowerCase()
      .replace(/[^\wа-яё]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }
  
  // Определяем, является ли текущий URL каноническим (со слагом)
  $: postId = $page.params.slug.split('-')[0];
  $: hasSlug = $page.params.slug.includes('-');
  $: canonicalUrl = hasSlug 
    ? $page.url.toString() 
    : new URL(`/post/${data.post.post_view.post.id}-${createSlug(data.post.post_view.post.name)}`, $page.url.origin).toString();
  const getTelegramSubscribeUrl = (creator: any): string | null => {
    if (!creator) return null
    const actorId = creator.actor_id || ''
    if (actorId.includes('t.me/')) return actorId
    const username = creator.name || ''
    return username ? `https://t.me/${username}` : null
  }
  $: authorSubscribeUrl = getTelegramSubscribeUrl(data?.post?.post_view?.creator)

  onMount(async () => {
    const token = $siteToken
    if (token && data?.post?.post_view?.post?.id) {
      try {
        await fetch(buildPostReadUrl(data.post.post_view.post.id), {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
        })
      } catch (error) {
        console.error('Failed to mark post as read:', error)
      }
    }
    if (
      !(data.post.post_view.read && $userSettings.markPostsAsRead) &&
      $profile?.jwt
    ) {
      getClient().markPostAsRead({
        read: $userSettings.markPostsAsRead,
        post_ids: [data.post.post_view.post.id],
      })
    }

    resumables.add({
      name: data.post.post_view.post.name,
      type: 'post',
      url: $page.url.toString(),
      avatar: data.post.post_view.post.thumbnail_url,
    })

    // Добавляем прокрутку к якорю после рендеринга
    if (browser && $page.url.hash) {
      setTimeout(() => {
        const element = document.querySelector($page.url.hash);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }, 100);
    }

    // await processPostBody();
  })

  afterNavigate(async () => {
    // reactivity hack
    data.post = data.post
    await processPostBody();
  })

  const fetchOnHome = async (jwt: string) => {
    const id = toast({
      content: $t('toast.fetchPostOnHome'),
      loading: true,
    })

    try {
      const res = await getClient().resolveObject({
        q: data.post.post_view.post.ap_id,
      })

      if (res.post) {
        removeToast(id)
        goto(`/post/${$instance}/${res.post.post.id}`, {}).then(() =>
          removeToast(id)
        )
      }
    } catch (err) {
      removeToast(id)
    }
  }

  let commentsPage = 1
  let commentSort: CommentSortType = data.commentSort
  let loading = false

  async function reloadComments() {
    loading = true
    data.comments = await getClient().getComments({
      page: 1,
      limit: 25,
      type_: 'All',
      post_id: data.post.post_view.post.id,
      sort: commentSort,
      max_depth: data.post.post_view.counts.comments > 100 ? 1 : 3,
    })
    loading = false
    data.thread.singleThread = false
    commentsPage = 1
  }

  let commenting = false

  let DOMPurify: any
  let processedContent = ''

  // Функция для проверки JSON контента
  function isJsonContent(content: string): boolean {
    return parseSerializedEditorModel(content) !== null
  }

  // Функция для извлечения превью изображения из контента
  function extractPreviewImage(content: string): string | null {
    if (!content) return null;

    if (isJsonContent(content)) {
      try {
        const parsed = parseSerializedEditorModel(content)
        if (!parsed) return null
        
        if (parsed.additional?.previewImage) {
          return parsed.additional.previewImage.trim();
        }

        const blocks = Array.isArray(parsed?.blocks) ? parsed.blocks : []
        for (const block of blocks) {
          if (block?.type === 'image') {
            const url = block?.data?.file?.url || block?.data?.url
            if (typeof url === 'string' && url.trim()) {
              return url.trim()
            }
          }
          if (block?.type === 'gallery') {
            const url = block?.data?.images?.[0]?.url
            if (typeof url === 'string' && url.trim()) {
              return url.trim()
            }
          }
          if (block?.type === 'imageCompare' || block?.type === 'compare') {
            const beforeUrl = block?.data?.before?.url
            const afterUrl = block?.data?.after?.url
            const candidate = beforeUrl || afterUrl
            if (typeof candidate === 'string' && candidate.trim()) {
              return candidate.trim()
            }
          }
        }
      } catch (error) {
        console.error('Error parsing JSON content:', error);
      }
    }

    // Поиск в HTML формате
    const imageRegex = /<preview-image>(.*?)<\/preview-image>/is;
    const match = content.match(imageRegex);
    return match ? match[1].trim() : null;
  }

  const renderMapBlock = (raw: any, anchorId = ''): string => {
    const lat = Number(raw?.lat)
    const lng = Number(raw?.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return ''
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return ''
    const zoom = normalizeOpenStreetMapZoom(raw?.zoom, 14)
    const src = buildOpenStreetMapEmbedUrl(lat, lng, zoom)

    return `<div class="post-map"${anchorId}>
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

  const escapeHtmlAttr = (value: string): string =>
    value
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')

  const renderImageCompareBlock = (raw: any, anchorId = ''): string => {
    const beforeUrl = typeof raw?.before?.url === 'string' ? raw.before.url.trim() : ''
    const afterUrl = typeof raw?.after?.url === 'string' ? raw.after.url.trim() : ''
    if (!beforeUrl || !afterUrl) return ''

    const rawPosition = Number(raw?.position)
    const position = Number.isFinite(rawPosition)
      ? Math.min(95, Math.max(5, Math.round(rawPosition)))
      : 50

    const beforeAlt = escapeHtmlAttr(
      typeof raw?.before?.alt === 'string' && raw.before.alt.trim()
        ? raw.before.alt
        : 'Изображение до'
    )
    const beforeTitle = escapeHtmlAttr(
      typeof raw?.before?.title === 'string' ? raw.before.title : ''
    )
    const afterAlt = escapeHtmlAttr(
      typeof raw?.after?.alt === 'string' && raw.after.alt.trim()
        ? raw.after.alt
        : 'Изображение после'
    )
    const afterTitle = escapeHtmlAttr(
      typeof raw?.after?.title === 'string' ? raw.after.title : ''
    )
    const caption =
      typeof raw?.caption === 'string' && raw.caption.trim()
        ? `<figcaption class="post-image-compare__caption">${escapeHtmlAttr(raw.caption)}</figcaption>`
        : ''

    return `<figure class="post-image-compare"${anchorId} data-compare-position="${position}">
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

  const setupImageCompareElements = () => {
    if (!browser) return
    const comparisons = document.querySelectorAll('.post-content .post-image-compare')

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

  const openMapModal = (source: string) => {
    if (!browser || !source) return
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

  function processJsonBlock(block: any): string {
    // Извлекаем якорь из tunes блока
    const anchorText = block?.tunes?.anchorInput?.text || 
                      block?.tunes?.customInput?.text;
    
    // Создаем атрибут id если есть якорь
    const anchorId = anchorText ? ` id="${anchorText}"` : '';
    const escapeSpoilerText = (value: string): string =>
      value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
    
    switch (block.type) {
      case 'paragraph':
        return `<p${anchorId}>${block.data.text}</p>`;
      case 'header':
        return `<h${block.data.level}${anchorId}>${block.data.text}</h${block.data.level}>`;
      case 'list':
        const listClass = block.data.style === 'checklist' ? 'checklist' : '';
        const items = block.data.items.map((item: any) => 
          `<li>${block.data.style === 'checklist' 
            ? `<input type="checkbox" ${item.meta.checked ? 'checked' : ''} disabled> `
            : ''}${item.content}</li>`
        ).join('');
        return block.data.style === 'ordered' 
          ? `<ol${anchorId}>${items}</ol>` 
          : `<ul${anchorId} class="${listClass}">${items}</ul>`;
      case 'quote':
        const cleanCaption = block.data.caption?.trim();
        return `<blockquote${anchorId}>
          <p>${block.data.text}</p>
          ${cleanCaption ? `<footer>${cleanCaption}</footer>` : ''}
        </blockquote>`;
      case 'code':
        return `<pre${anchorId}><code>${block.data.code}</code></pre>`;
      case 'spoiler':
        const spoilerTitle =
          typeof block.data?.title === 'string' && block.data.title.trim()
            ? block.data.title.trim()
            : 'Спойлер'
        const spoilerContent =
          typeof block.data?.content === 'string' ? block.data.content.trim() : ''
        if (!spoilerContent) return ''
        return `<div class="post-spoiler"${anchorId} data-spoiler-open="0">
          <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
            <span class="post-spoiler__title">${escapeSpoilerText(spoilerTitle)}</span>
            <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
          </div>
          <div class="post-spoiler__content">
            <p>${escapeSpoilerText(spoilerContent).replace(/\r?\n/g, '<br>')}</p>
          </div>
        </div>`;
      case 'link':
      case 'customLink':
        const url = block.data.url || '#';
        const text = block.data.text || block.data.title || url;
        const title = block.data.title ? ` title="${block.data.title}"` : '';
        const isExternal = url.startsWith('http');
        const target = isExternal ? ' target="_blank" rel="noopener noreferrer"' : '';
        const linkStyle = block.data.style || 'link';
        return `<p${anchorId}><a href="${url}"${title}${target} class="${linkStyle}">${text}</a></p>`;
      case 'embed':
        const embedCaption = block.data.caption ? `<div class="embed-caption">${block.data.caption}</div>` : '';
        return `<div class="embed-container"${anchorId}>
          <div class="embed-responsive" style="padding-bottom: ${(block.data.height / block.data.width * 100).toFixed(2)}%">
            <iframe 
              src="${block.data.embed}" 
              frameborder="0" 
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
              allowfullscreen
              loading="lazy"
            ></iframe>
          </div>
          ${embedCaption}
        </div>`;
      case 'image':
        const imageWithAnchor = anchorId 
          ? `<div class="image-wrapper"${anchorId}>
          <img src="${block.data.file.url}" 
            alt="${block.data.file.alt || ''}" 
            title="${block.data.file.title || ''}"
            ${block.data.caption ? `data-caption="${block.data.caption}"` : ''}>
          ${block.data.caption ? `<div class="image-alt-text">${block.data.caption}</div>` : ''}
        </div>`
          : `<div class="image-wrapper">
          <img src="${block.data.file.url}" 
            alt="${block.data.file.alt || ''}" 
            title="${block.data.file.title || ''}"
            ${block.data.caption ? `data-caption="${block.data.caption}"` : ''}>
          ${block.data.caption ? `<div class="image-alt-text">${block.data.caption}</div>` : ''}
        </div>`;
        return imageWithAnchor;
      case 'gallery':
        const images = block.data.images.map((img: any, index: number) => 
          `<div class="gallery-item loaded" ${index > 0 ? 'style="display: none;"' : ''}>
            <img src="${img.url}" alt="${img.alt || ''}" title="${img.title || ''}">
            ${img.title ? `<div class="gallery-alt-text">${img.title}</div>` : ''}
          </div>`
        ).join('');
        return `<div class="post-gallery"${anchorId}>
          <div class="gallery-images">${images}</div>
        </div>`;
      case 'map':
        return renderMapBlock(block.data, anchorId)
      case 'imageCompare':
      case 'compare':
        return renderImageCompareBlock(block.data, anchorId)
      default:
        return '';
    }
  }

  function convertJsonToHtml(jsonContent: string): string {
    try {
      const content = parseSerializedEditorModel(jsonContent)
      if (!content.blocks) return '';
      
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
        
      const escapeSpoilerText = (value: string): string =>
        value
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;')
      const renderSpoilerContainer = (spoilerTitle: string, spoilerHtml: string): string => {
        if (!spoilerHtml.trim()) return ''
        return `<div class="post-spoiler" data-spoiler-open="0">
          <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
            <span class="post-spoiler__title">${escapeSpoilerText(spoilerTitle || 'Спойлер')}</span>
            <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
          </div>
          <div class="post-spoiler__content">
            ${spoilerHtml}
          </div>
        </div>`
      }

      const htmlParts: string[] = []
      const spoilerStack: Array<{ title: string; parts: string[] }> = []

      const appendHtmlToCurrentScope = (html: string) => {
        if (!html) return
        if (spoilerStack.length > 0) {
          spoilerStack[spoilerStack.length - 1].parts.push(html)
          return
        }
        htmlParts.push(html)
      }

      for (const block of content.blocks) {
        const blockType = String(block?.type || '').toLowerCase()
        if (blockType === 'spoiler') {
          const rawData = block?.data || {}
          const legacyContent =
            typeof rawData?.content === 'string' ? rawData.content.trim() : ''
          if (legacyContent) {
            appendHtmlToCurrentScope(processJsonBlock(block))
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
            appendHtmlToCurrentScope(
              renderSpoilerContainer(completedSpoiler.title, completedSpoiler.parts.join('\n'))
            )
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

        appendHtmlToCurrentScope(processJsonBlock(block))
      }

      while (spoilerStack.length > 0) {
        const unclosedSpoiler = spoilerStack.pop()
        if (!unclosedSpoiler) break
        appendHtmlToCurrentScope(
          renderSpoilerContainer(unclosedSpoiler.title, unclosedSpoiler.parts.join('\n'))
        )
      }

      const htmlContent = htmlParts.join('\n');
      
      console.log(`${previewImage}${previewDescription}${metaTitle}${metaDescription} + html`);

      return `${previewImage}${previewDescription}${metaTitle}${metaDescription}${htmlContent}`;
    } catch (error) {
      console.error('Error converting JSON to HTML:', error);
      return '';
    }
  }

  async function processPostBody() {
    if (browser && data.post.post_view.post.body) {
      const module = await import('dompurify');
      DOMPurify = module.default;
      let content = data.post.post_view.post.body;
      
      try {
        // Определяем формат контента и обрабатываем соответственно
        if (isJsonContent(content)) {
          content = convertJsonToHtml(content);
        }
        
        console.log('content before');
        console.log(content);

        // Удаляем мета-теги из контента
        content = content
          .replace(/<preview-image>.*?<\/preview-image>/gs, '')
          .replace(/<preview-description>.*?<\/preview-description>/gs, '')
          .replace(/<meta-title>.*?<\/meta-title>/gs, '')
          .replace(/<meta-description>.*?<\/meta-description>/gs, '');
        
        console.log('content after');
        console.log(content);

        processedContent = DOMPurify.sanitize(content, {
          ALLOWED_TAGS: ['p', 'b', 'i', 'em', 'strong', 'a', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'img', 'figure', 'figcaption', 'div', 'blockquote', 'pre', 'code', 'input', 'iframe', 'footer'],
          ALLOWED_ATTR: ['href', 'target', 'rel', 'src', 'alt', 'title', 'width', 'height', 'loading', 'class', 'data-index', 'data-url', 'type', 'checked', 'disabled', 'data-caption', 'data-compare-position', 'id', 'style', 'frameborder', 'allowfullscreen', 'allow', 'referrerpolicy']
        });
      } catch (error) {
        console.error('Error processing post body:', error);
        // В случае ошибки возвращаем оригинальный контент
        processedContent = content;
      }

      if (browser) {
        setTimeout(() => {

          // Находим все элементы image-wrapper без изображений внутри и удаляем их
          const emptyWrappers = document.querySelectorAll('.post-content .image-wrapper:not(:has(img))');
          emptyWrappers.forEach(wrapper => {
            wrapper.remove();
          });

          // Изменяем селектор для поиска изображений
          const images = document.querySelectorAll('.post-content img:not(.gallery-item img)')
          images.forEach(img => {
            const imgSrc = img.getAttribute('src')
            const dataUrl = img.getAttribute('data-url')
            
            if (!imgSrc) return

            // Удаляем существующий alt-текст, если он есть
            const existingAltText = img.nextElementSibling
            if (existingAltText?.className === 'image-alt-text') {
              existingAltText.remove()
            }

            if (dataUrl) {
              // Для изображений с data-url создаем только ссылку
              const wrapper = document.createElement('a')
              wrapper.href = dataUrl
              wrapper.target = '_blank'
              wrapper.rel = 'noopener noreferrer'
              img.parentNode?.insertBefore(wrapper, img)
              wrapper.appendChild(img)
            } else {
              // Для обычных изображений создаем обертку с увеличением
              const wrapper = document.createElement('div')
              wrapper.className = 'image-wrapper'
              wrapper.style.position = 'relative'
              wrapper.style.display = 'inline-block'
              
              // Создаем функцию открытия модального окна
              const openModal = (e: Event) => {
                e.stopPropagation() // Предотвращаем всплытие события

                const modal = document.createElement('div')
                modal.className = 'fullscreen-modal'
                
                const fullscreenImg = img.cloneNode(true) as HTMLImageElement
                
                // Кнопка закрытия
                const closeBtn = document.createElement('button')
                closeBtn.className = 'fullscreen-close'
                closeBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/></svg>`
                
                closeBtn.onclick = () => modal.remove()
                
                modal.appendChild(fullscreenImg)
                modal.appendChild(closeBtn)

                // Добавляем alt-текст в модальное окно
                if (img instanceof HTMLImageElement && img.title) {
                  const modalAltText = document.createElement('div')
                  modalAltText.className = 'fullscreen-alt-text'
                  modalAltText.textContent = img.title
                  modal.appendChild(modalAltText)
                }

                document.body.appendChild(modal)
                
                // Добавляем обработчик Escape
                const handleKeydown = (e: KeyboardEvent) => {
                  if (e.key === 'Escape') {
                    modal.remove()
                    document.removeEventListener('keydown', handleKeydown)
                  }
                }
                document.addEventListener('keydown', handleKeydown)
              }

              // Добавляем обработчик для открытия в полноэкранном режиме
              wrapper.addEventListener('click', openModal)
              
              // Оборачиваем изображение
              img.parentNode?.insertBefore(wrapper, img)
              wrapper.appendChild(img)

              // Добавляем alt-текст под изображением
              if (img instanceof HTMLImageElement && img.title) {
                const altText = document.createElement('div')
                altText.className = 'image-alt-text'
                altText.textContent = img.title
                wrapper.appendChild(altText)
              }
              
              // Добавляем иконку увеличения
              const zoomIcon = document.createElement('div')
              zoomIcon.className = 'zoom-icon'
              zoomIcon.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>`
              wrapper.appendChild(zoomIcon)
            }
          })

          const galleries = document.querySelectorAll('.post-content .post-gallery')
          galleries.forEach((gallery) => {
            const images = Array.from(gallery.querySelectorAll('img'))
            if (!images.length) return

            const imageData = images.map((img) => ({
              src: img.getAttribute('src') || '',
              alt: img.getAttribute('alt') || '',
              title: img.getAttribute('title') || '',
            }))

            const grid = document.createElement('div')
            grid.className = 'gallery-grid'

            let modal: HTMLElement | null = null
            let modalImage: HTMLImageElement | null = null
            let modalCaption: HTMLElement | null = null
            let currentIndex = 0

            const updateModal = (index: number) => {
              currentIndex = (index + imageData.length) % imageData.length
              const current = imageData[currentIndex]
              if (modalImage) {
                modalImage.src = current.src
                modalImage.alt = current.alt
              }
              if (modalCaption) {
                modalCaption.textContent = current.title || current.alt || ''
              }
            }

            const closeModal = () => {
              modal?.remove()
              modal = null
              modalImage = null
              modalCaption = null
              document.removeEventListener('keydown', onKeydown)
            }

            const onKeydown = (e: KeyboardEvent) => {
              if (!modal) return
              if (e.key === 'Escape') {
                closeModal()
              } else if (e.key === 'ArrowLeft') {
                updateModal(currentIndex - 1)
              } else if (e.key === 'ArrowRight') {
                updateModal(currentIndex + 1)
              }
            }

            const openModal = (index: number) => {
              if (!modal) {
                modal = document.createElement('div')
                modal.className = 'gallery-modal'
                modal.innerHTML = `
                  <div class="gallery-modal-backdrop"></div>
                  <div class="gallery-modal-content">
                    <img class="gallery-modal-image" />
                    <div class="gallery-modal-caption"></div>
                  </div>
                  <button class="gallery-modal-close" aria-label="Закрыть">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M6 18L18 6M6 6l12 12" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                  <button class="gallery-modal-prev" aria-label="Предыдущее">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                  <button class="gallery-modal-next" aria-label="Следующее">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                      <path d="M9 18l6-6-6-6" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </button>
                `

                document.body.appendChild(modal)
                modalImage = modal.querySelector('.gallery-modal-image')
                modalCaption = modal.querySelector('.gallery-modal-caption')

                const backdrop = modal.querySelector('.gallery-modal-backdrop')
                backdrop?.addEventListener('click', closeModal)
                modal.querySelector('.gallery-modal-close')?.addEventListener('click', closeModal)
                modal.querySelector('.gallery-modal-prev')?.addEventListener('click', () => updateModal(currentIndex - 1))
                modal.querySelector('.gallery-modal-next')?.addEventListener('click', () => updateModal(currentIndex + 1))

                if (imageData.length <= 1) {
                  modal.querySelector('.gallery-modal-prev')?.classList.add('hidden')
                  modal.querySelector('.gallery-modal-next')?.classList.add('hidden')
                }

                document.addEventListener('keydown', onKeydown)
              }

              updateModal(index)
            }

            images.forEach((img, index) => {
              const thumb = document.createElement('button')
              thumb.type = 'button'
              thumb.className = 'gallery-thumb'
              thumb.appendChild(img)
              thumb.addEventListener('click', () => openModal(index))
              grid.appendChild(thumb)
            })

            gallery.innerHTML = ''
            gallery.appendChild(grid)
          })

          const maps = document.querySelectorAll('.post-content .post-map')
          maps.forEach((mapElement) => {
            if (!(mapElement instanceof HTMLElement)) return
            if (mapElement.getAttribute('data-map-ready') === '1') return
            mapElement.setAttribute('data-map-ready', '1')
            mapElement.addEventListener('click', (event) => {
              event.preventDefault()
              event.stopPropagation()
              const frame = mapElement.querySelector('iframe')
              const source = frame?.getAttribute('src') || ''
              if (source) {
                openMapModal(source)
              }
            })
          })

          const spoilerTriggers = document.querySelectorAll('.post-content .post-spoiler__trigger')
          const toggleSpoiler = (trigger: HTMLElement) => {
            const spoiler = trigger.closest('.post-spoiler') as HTMLElement | null
            if (!spoiler) return
            const isOpen = spoiler.classList.toggle('is-open')
            spoiler.setAttribute('data-spoiler-open', isOpen ? '1' : '0')
            trigger.setAttribute('aria-expanded', isOpen ? 'true' : 'false')
            const hint = trigger.querySelector('.post-spoiler__hint') as HTMLElement | null
            if (hint) {
              hint.textContent = isOpen ? 'Нажмите, чтобы скрыть' : 'Нажмите, чтобы раскрыть'
            }
          }
          spoilerTriggers.forEach((triggerElement) => {
            if (!(triggerElement instanceof HTMLElement)) return
            if (triggerElement.getAttribute('data-spoiler-ready') === '1') return
            triggerElement.setAttribute('data-spoiler-ready', '1')
            triggerElement.addEventListener('click', (event) => {
              event.preventDefault()
              event.stopPropagation()
              toggleSpoiler(triggerElement)
            })
            triggerElement.addEventListener('keydown', (event: KeyboardEvent) => {
              if (event.key !== 'Enter' && event.key !== ' ') return
              event.preventDefault()
              event.stopPropagation()
              toggleSpoiler(triggerElement)
            })
          })

          setupImageCompareElements()
        }, 0)
      }
    }
  }

  // Функция для рендеринга контента из JSON/base64 формата
  function renderContent(content: any): string {
    if (!content?.blocks) return '';
    const escapeSpoilerText = (value: string): string =>
      value
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')

    const renderSpoilerContainer = (
      spoilerTitle: string,
      spoilerHtml: string,
      anchorId: string
    ): string => {
      if (!spoilerHtml.trim()) return ''
      return `<div class="post-spoiler"${anchorId} data-spoiler-open="0">
        <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
          <span class="post-spoiler__title">${escapeSpoilerText(spoilerTitle || 'Спойлер')}</span>
          <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
        </div>
        <div class="post-spoiler__content">
          ${spoilerHtml}
        </div>
      </div>`
    }

    const renderRegularBlock = (block: any): string => {
      const anchorText = block?.tunes?.anchorInput?.text || block?.tunes?.customInput?.text;
      const anchorId = anchorText ? ` id="${anchorText}"` : '';

      switch (block.type) {
        case 'paragraph':
          return `<p${anchorId}>${block.data.text}</p>`;
        case 'header':
          return `<h${block.data.level}${anchorId}>${block.data.text}</h${block.data.level}>`;
        case 'list':
          const items = block.data.items.map((item: any) => 
            `<li>${block.data.style === 'checklist' 
              ? `<input type="checkbox" ${item.meta?.checked ? 'checked' : ''} disabled> `
              : ''}${item.content}</li>`
          ).join('');
          return block.data.style === 'ordered' 
            ? `<ol${anchorId}>${items}</ol>` 
            : `<ul${anchorId} class="${block.data.style === 'checklist' ? 'checklist' : ''}">${items}</ul>`;
        case 'quote':
          const cleanCaption = block.data.caption?.trim();
          return `<blockquote${anchorId}>
            <p>${block.data.text}</p>
            ${cleanCaption ? `<footer>${cleanCaption}</footer>` : ''}
          </blockquote>`;
        case 'code':
          return `<pre${anchorId}><code>${block.data.code}</code></pre>`;
        case 'spoiler':
          const spoilerTitle =
            typeof block.data?.title === 'string' && block.data.title.trim()
              ? block.data.title.trim()
              : 'Спойлер'
          const spoilerContent =
            typeof block.data?.content === 'string' ? block.data.content.trim() : ''
          if (!spoilerContent) return ''
          return `<div class="post-spoiler"${anchorId} data-spoiler-open="0">
            <div class="post-spoiler__trigger" role="button" tabindex="0" aria-expanded="false">
              <span class="post-spoiler__title">${escapeSpoilerText(spoilerTitle)}</span>
              <span class="post-spoiler__hint">Нажмите, чтобы раскрыть</span>
            </div>
            <div class="post-spoiler__content">
              <p>${escapeSpoilerText(spoilerContent).replace(/\r?\n/g, '<br>')}</p>
            </div>
          </div>`;
        case 'image':
          return `<div class="image-wrapper"${anchorId}>
            <img src="${block.data.file.url}" 
              alt="${block.data.file.alt || ''}" 
              title="${block.data.file.title || ''}"
              ${block.data.caption ? `data-caption="${block.data.caption}"` : ''}>
            ${block.data.caption ? `<div class="image-alt-text">${block.data.caption}</div>` : ''}
          </div>`;
        case 'gallery':
          const images = block.data.images.map(
            (img: any) =>
              `<img src="${img.url}" alt="${img.alt || ''}" title="${img.title || ''}">`
          ).join('');
          return `<div class="post-gallery"${anchorId}>
            ${images}
          </div>`;
        case 'map':
          return renderMapBlock(block.data, anchorId)
        case 'imageCompare':
        case 'compare':
          return renderImageCompareBlock(block.data, anchorId)
        case 'link':
        case 'customLink':
          const url = block.data.url || '#';
          const text = block.data.text || block.data.title || url;
          const title = block.data.title ? ` title="${block.data.title}"` : '';
          const isExternal = url.startsWith('http');
          const target = isExternal ? ' target="_blank" rel="noopener noreferrer"' : '';
          const linkStyle = block.data.style || 'link';
          return `<p${anchorId}><a href="${url}"${title}${target} class="${linkStyle}">${text}</a></p>`;
        case 'embed':
          const embedCaption = block.data.caption ? `<div class="embed-caption">${block.data.caption}</div>` : '';
          return `<div class="embed-container"${anchorId}>
            <div class="embed-responsive" style="padding-bottom: ${(block.data.height / block.data.width * 100).toFixed(2)}%">
              <iframe 
                src="${block.data.embed}" 
                frameborder="0" 
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                allowfullscreen
                loading="lazy"
              ></iframe>
            </div>
            ${embedCaption}
          </div>`;
        default:
          return '';
      }
    }

    const htmlParts: string[] = []
    const spoilerStack: Array<{ title: string; parts: string[]; anchorId: string }> = []

    const appendHtmlToCurrentScope = (html: string) => {
      if (!html) return
      if (spoilerStack.length > 0) {
        spoilerStack[spoilerStack.length - 1].parts.push(html)
        return
      }
      htmlParts.push(html)
    }

    for (const block of content.blocks) {
      const blockType = String(block?.type || '').toLowerCase()
      if (blockType === 'spoiler') {
        const rawData = block?.data || {}
        const legacyContent =
          typeof rawData?.content === 'string' ? rawData.content.trim() : ''
        if (legacyContent) {
          appendHtmlToCurrentScope(renderRegularBlock(block))
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
          appendHtmlToCurrentScope(
            renderSpoilerContainer(
              completedSpoiler.title,
              completedSpoiler.parts.join('\n'),
              completedSpoiler.anchorId
            )
          )
          continue
        }
        const spoilerTitle =
          typeof rawData?.title === 'string' && rawData.title.trim()
            ? rawData.title.trim()
            : 'Спойлер'
        const anchorText = block?.tunes?.anchorInput?.text || block?.tunes?.customInput?.text;
        spoilerStack.push({
          title: spoilerTitle,
          parts: [],
          anchorId: anchorText ? ` id="${anchorText}"` : '',
        })
        continue
      }

      appendHtmlToCurrentScope(renderRegularBlock(block))
    }

    while (spoilerStack.length > 0) {
      const unclosedSpoiler = spoilerStack.pop()
      if (!unclosedSpoiler) break
      appendHtmlToCurrentScope(
        renderSpoilerContainer(
          unclosedSpoiler.title,
          unclosedSpoiler.parts.join('\n'),
          unclosedSpoiler.anchorId
        )
      )
    }

    return htmlParts.join('\n');
  }

  // Функция для санитизации HTML
  function sanitizeHtml(html: string, isMetaContent = false): string {
    if (browser && DOMPurify) {
      return DOMPurify.sanitize(html, {
        ALLOWED_TAGS: isMetaContent ? [] : [
          'p', 'b', 'i', 'em', 'strong', 'a', 'br', 
          'ul', 'ol', 'li', 'h1', 'h2', 'h3', 
          'img', 'figure', 'figcaption', 'div', 
          'blockquote', 'pre', 'code', 'input', 'footer',
          'iframe'
        ],
        ALLOWED_ATTR: isMetaContent ? [] : [
          'href', 'target', 'rel', 'src', 'alt', 
          'title', 'width', 'height', 'loading', 
          'class', 'data-caption', 'data-compare-position', 'id', 'checked', 
          'disabled', 'style', 'frameborder',
          'data-spoiler-open', 'role', 'tabindex', 'aria-expanded',
          'allowfullscreen', 'allow', 'referrerpolicy'
        ]
      });
    }
    
    // Для SSR или когда DOMPurify недоступен
    if (isMetaContent) {
      return html
        .replace(/<[^>]*>/g, '') // Удаляем все HTML теги
        .replace(/&nbsp;/g, ' ') // Заменяем неразрывные пробелы
        .replace(/\s+/g, ' ') // Заменяем множественные пробелы на один
        .trim(); // Удаляем пробелы в начале и конце
    }
    
    return html;
  }

  function stripHtml(html: string | undefined): string {
    if (!html) return '';
    
    try {
      // Удаляем мета-теги
      const cleanHtml = html
        .replace(/<preview-image>.*?<\/preview-image>/gs, '')
        .replace(/<preview-description>.*?<\/preview-description>/gs, '')
        .replace(/<meta-description>.*?<\/meta-description>/gs, '')
        .replace(/<meta-title>.*?<\/meta-title>/gs, '');
      
      // Проверяем, является ли контент JSON или base64
      if (isJsonContent(cleanHtml)) {
        try {
          const parsed = parseSerializedEditorModel(cleanHtml)
          if (!parsed) return ''
          const renderedContent = renderContent(parsed);
          return sanitizeHtml(renderedContent, type === 'meta' as any);
        } catch (error) {
          console.error('Error parsing JSON/base64 content:', error);
          return looksLikeSerializedEditorModel(cleanHtml)
            ? ''
            : sanitizeHtml(cleanHtml, type === 'meta' as any);
        }
      }
      
      return sanitizeHtml(cleanHtml, type === 'meta' as any);
    } catch (error) {
      console.error('Error in stripHtml:', error);
      return looksLikeSerializedEditorModel(html) ? '' : html;
    }
  }

  $: remoteView = false

  $: combinedPosts = (() => {
    if (!data.recommendations) return []
    
    // Получаем ID текущего поста
    const currentPostId = data.post.post_view.post.id
    
    // Сначала берем локальные посты из сообщества
    const communityPostsFiltered = (data.recommendations.communityPosts?.posts || [])
      .filter((p) => 
        p.post.id !== currentPostId && 
        p.post.local
      )
    
    // Затем добавляем локальные глобальные посты
    const globalPostsFiltered = (data.recommendations.globalPosts?.posts?.posts || [])
      .filter((p) => 
        p.post.id !== currentPostId && 
        !communityPostsFiltered.some((cp) => cp.post.id === p.post.id) &&
        p.community.id !== data.post.post_view.community.id &&
        p.post.local
      )
    
    // Объединяем массивы
    return [...communityPostsFiltered, ...globalPostsFiltered]
  })()

  // Рекламные посты (если есть в ENV)
  $: adPosts = (() => {
    if (!data.recommendations?.adPosts?.length) return []

    const currentPostId = data.post.post_view.post.id

    return data.recommendations.adPosts
      .filter((p) => p.post.id !== currentPostId && p.post.local)
  })()

  // Итоговая лента: рекламные посты, чередующиеся с похожими постами
  $: finalPosts = (() => {
    const hasCombined = combinedPosts && combinedPosts.length
    const hasAds = adPosts && adPosts.length

    if (!hasCombined && !hasAds) return []
    if (!hasCombined && hasAds) return adPosts
    if (hasCombined && !hasAds) return combinedPosts

    const filteredCombined = combinedPosts.filter(
      (p) => !adPosts.some((ad) => ad.post.id === p.post.id)
    )

    const result: typeof combinedPosts = []
    let adIndex = 0
    let postIndex = 0

    // Чередуем: реклама -> похожий пост -> реклама -> похожий пост ...
    while (adIndex < adPosts.length || postIndex < filteredCombined.length) {
      if (adIndex < adPosts.length) {
        result.push(adPosts[adIndex])
        adIndex += 1
      }

      if (postIndex < filteredCombined.length) {
        result.push(filteredCombined[postIndex])
        postIndex += 1
      }
    }

    return result
  })()

  function getMetaTitle(post: any): string {
    if (!post) return '';
    
    // Проверяем, является ли контент JSON или base64
    if (isJsonContent(post.body)) {
      try {
        const parsed = parseSerializedEditorModel(post.body)
        if (!parsed) return 'Пост'
        if (parsed.additional?.metaTitle) {
          return parsed.additional.metaTitle.trim();
        }
      } catch (error) {
        console.error('Error parsing meta title:', error);
      }
    }
    
    // Проверяем HTML формат
    const metaTitleMatch = post.body?.match(/<meta-title>(.*?)<\/meta-title>/s);
    const metaTitle = metaTitleMatch?.[1]?.trim();
    const cleanMetaTitle =
      metaTitle && metaTitle !== 'undefined' && metaTitle !== 'null' ? metaTitle : '';
    const fallbackTitle = stripHtml(post.name || post.title || '').trim();

    const baseTitle = cleanMetaTitle || fallbackTitle || 'Пост';
    const separators = ['.', '!', '?'];
    let cutIndex = -1;
    separators.forEach((separator) => {
      const idx = baseTitle.indexOf(separator);
      if (idx > 0 && (cutIndex === -1 || idx < cutIndex)) {
        cutIndex = idx;
      }
    });
    return (cutIndex > 0 ? baseTitle.slice(0, cutIndex) : baseTitle).trim() || 'Пост';
  }

  function getMetaDescription(post: any): string {
    if (!post?.body) return '';
    
    // Проверяем, является ли контент JSON или base64
    if (isJsonContent(post.body)) {
      try {
        const parsed = parseSerializedEditorModel(post.body)
        if (!parsed) return ''
        // Если есть метаописание в дополнительных данных, используем его
        if (parsed.additional?.metaDescription) {
          return stripHtml(parsed.additional.metaDescription.trim());
        }

        // Если нет метаописания, но есть блоки, берем текст из первого текстового блока
        if (parsed.blocks && parsed.blocks.length > 0) {
          for (const block of parsed.blocks) {
            if (block.type === 'paragraph' && block.data.text) {
              const cleanText = stripHtml(block.data.text);
              if (cleanText) {
                return cleanText.slice(0, 170);
              }
            }
          }
        }

        // Если не нашли подходящего текста, возвращаем пустую строку
        return '';
      } catch (error) {
        console.error('Error parsing meta description:', error);
        // В случае ошибки парсинга возвращаем пустую строку вместо base64
        return '';
      }
    }
    
    // Проверяем HTML формат
    const metaDescMatch = post.body.match(/<meta-description>(.*?)<\/meta-description>/s);
    const metaDesc = metaDescMatch?.[1]?.trim();
    
    if (metaDesc) {
      return stripHtml(metaDesc);
    }

    // Удаляем все HTML-теги и лишние пробелы
    const cleanBody = stripHtml(post.body)
      .replace(/\s+/g, ' ') // Заменяем множественные пробелы на один
      .trim(); // Удаляем пробелы в начале и конце

    return cleanBody.slice(0, 170);
  }

  // Исправляем тип данных для feedData
  $: feedDataForComponent = {
    posts: {
      posts: finalPosts
    },
    cursor: { next: undefined },
    sort: 'Hot' as const
  }

  // Функция для получения og изображения
  function getOgImage(post: any): string | null {
    // Сначала проверяем превью изображение в контенте
    if (post.body) {
      const previewImage = extractPreviewImage(post.body);
      if (previewImage) return previewImage;
    }
    
    // Если нет превью, используем URL изображения поста
    if (isImage(post.url)) {
      return post.url;
    }
    
    
    return post.thumbnail_url || null;
  }
</script>

<svelte:head>
  <title>{getMetaTitle(data.post.post_view.post)}</title>
  <meta property="og:title" content={getMetaTitle(data.post.post_view.post)} />
  <meta property="twitter:title" content={getMetaTitle(data.post.post_view.post)} />
  <meta property="og:url" content={$page.url.toString()} />

  <meta name="description" content={getMetaDescription(data.post.post_view.post)} />
  <meta property="og:description" content={getMetaDescription(data.post.post_view.post)} />
  <meta property="twitter:description" content={getMetaDescription(data.post.post_view.post)} />

  <!-- Добавляем каноническую ссылку -->
  <link rel="canonical" href={canonicalUrl} />
  
  {#if data.post.post_view.post}
    {@const ogImageValue = getOgImage(data.post.post_view.post)}
    {#if ogImageValue}
      <meta property="og:image" content={ogImageValue} />
      <meta property="twitter:card" content="summary_large_image" />
      <meta property="twitter:image" content={ogImageValue} />
    {/if}
  {/if}
  
</svelte:head>

<article class="flex flex-col mx-auto w-full max-w-[640px] bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 border-b-slate-300 dark:border-t-zinc-700 p-4 sm:p-6">
  {#if remoteView}
    <div
      class="sticky top-0 bg-slate-50 dark:bg-zinc-950 z-20
      border-b dark:border-zinc-800 border-slate-300
      -mx-4 -mt-4 md:-mt-6 md:-mx-6 sticky-header px-4 py-2
      flex items-center gap-2 mb-4 h-12
      "
    >
      <Popover openOnHover>
        <Icon
          src={InformationCircle}
          size="24"
          solid
          slot="target"
          class="bg-slate-200 dark:bg-zinc-700 p-0.5 rounded-full text-primary-900 dark:text-primary-100"
        />
        {$t('routes.post.instanceWarning')}
      </Popover>
      <span class="text-primary-900 dark:text-primary-100 font-bold">
        {$t('routes.post.remoteView')}
      </span>
      {#if $profile?.jwt}
        <Button
          class="ml-auto"
          on:click={() => {
            if ($profile?.jwt) {
              fetchOnHome($profile?.jwt)
            }
          }}
        >
          <Icon src={Home} mini size="16" />
          {$t('routes.post.localView')}
        </Button>
      {/if}
    </div>
  {/if}

  <header class="flex flex-col gap-2">
    <PostMeta
      community={data.post.post_view.community}
      user={data.post.post_view.creator}
      bind:subscribed={data.post.community_view.subscribed}
      badges={{
        deleted: data.post.post_view.post.deleted,
        removed: data.post.post_view.post.removed,
        locked: data.post.post_view.post.locked,
        featured:
          data.post.post_view.post.featured_community ||
          data.post.post_view.post.featured_local,
        nsfw: data.post.post_view.post.nsfw,
        saved: data.post.post_view.saved,
        admin: data.post.post_view.creator_is_admin,
        moderator: data.post.post_view.creator_is_moderator,
      }}
      published={publishedToDate(data.post.post_view.post.published)}
      edited={data.post.post_view.post.updated}
      title={undefined}
    />
    <!-- Заголовок для отображения и SEO -->
    <h1 class="text-2xl font-bold text-slate-900 dark:text-zinc-50">
      {data.post.post_view.post.name}
    </h1>
  </header>
  <PostMedia
    type={mediaType(data.post.post_view.post.url)}
    post={data.post.post_view.post}
    opened
    view="cozy"
  />
  {#if data.post.post_view.post.body}
    <div class="text-base text-slate-800 dark:text-zinc-200 leading-[1.5] post post-content">
      {#if processedContent}
        {@html processedContent}
      {:else}
        {@html stripHtml(data.post.post_view.post.body)}
      {/if}
    </div>
  {/if}
  {#if authorSubscribeUrl}
    <div class="mt-5">
      <Button
        size="sm"
        color="primary"
        href={authorSubscribeUrl}
        target="_blank"
        rel="nofollow noopener"
        class="h-10 !min-h-[2.5rem] dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110"
      >
        <span class="inline-flex items-center gap-2 text-white">
          <img
            src="/img/logos/telegram_logo.svg"
            alt="Telegram"
            class="w-4 h-4 dark:brightness-0 dark:invert"
          />
          Подписаться на телеграм автора
        </span>
      </Button>
    </div>
  {/if}
  <div class="w-full relative">
    <PostActions
      bind:post={data.post.post_view}
      on:edit={() =>
        toast({
          content: 'The post was edited successfully.',
          type: 'success',
        })}
      {type}
    />
  </div>
  {#if data.post.cross_posts?.length > 0}
    <Expandable
      class="text-base mt-2 w-full cursor-pointer"
      open={data.post.cross_posts?.length <= 3}
    >
      <div
        slot="title"
        class="inline-block w-full text-left text-base font-normal"
      >
        <span class="font-bold">{data.post.cross_posts.length}</span>
        {$t('routes.post.crosspostCount')}
      </div>
      <div
        class="!divide-y divide-slate-200 dark:divide-zinc-800 flex flex-col"
      >
        {#each data.post.cross_posts as crosspost}
          <Post view="compact" actions={false} post={crosspost} />
        {/each}
      </div>
    </Expandable>
  {/if}
</article>

{#if featuredPost}
  <div class="mt-4 flex flex-col gap-2 max-w-[640px] w-full mx-auto">
    <div class="bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 border-b-slate-300 dark:border-t-zinc-700 p-4 sm:p-6">
      <Post post={featuredPost} view="cozy" />
    </div>
  </div>
{/if}

{#if data.thread.showContext || data.thread.singleThread}
  <div
    class="sticky mx-auto z-50 max-w-lg w-full min-w-0 flex items-center overflow-auto gap-1
    bg-slate-50/50 dark:bg-zinc-900/50 backdrop-blur-xl border border-slate-200/50 dark:border-zinc-800/50
    p-1 rounded-full px-2.5 justify-between"
    style="top: max(1.5rem, {$contentPadding.top}px);"
  >
    <p class="font-medium text-sm flex items-center gap-2">
      <Icon src={InformationCircle} mini size="20" />
      {data.thread.showContext
        ? $t('routes.post.thread.part')
        : $t('routes.post.thread.single')}
    </p>
    <Button
      color="none"
      rounding="pill"
      {loading}
      disabled={loading}
      href={data.thread.showContext
        ? `/comment/${$page.params.instance}/${data.thread.showContext}`
        : undefined}
      class="hover:bg-white/50 dark:hover:bg-zinc-800/30"
      on:click={data.thread.singleThread ? reloadComments : undefined}
    >
      {data.thread.showContext
        ? $t('routes.post.thread.context')
        : $t('routes.post.thread.allComments')}
    </Button>
  </div>
{/if}
{#if !data.post.post_view.post.locked}
<section class="mt-4 flex flex-col gap-2 max-w-[640px] w-full mx-auto bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 border-b-slate-300 dark:border-t-zinc-700 p-4 sm:p-6" id="comments">
  <header>
    <div class="text-base">
      <span class="font-bold">
        <FormattedNumber number={data.post.post_view.counts.comments} />
      </span>
      {$t('routes.post.commentCount')}
    </div>
  </header>
  {#await data.comments}
    <div class="space-y-4">
      {#each new Array(10) as empty}
        <div class="animate-pulse flex flex-col gap-2 skeleton w-full">
          <div class="w-96 h-4" />
          <div class="w-full h-12" />
          <div class="w-48 h-4" />
        </div>
      {/each}
    </div>
  {:then comments}
    <CommentForm
      postId={data.post.post_view.post.id}
      autoFocus={data.reply}
      on:comment={(e) => {
        if (!$profile?.jwt) {
          goto('/login?redirect=' + encodeURIComponent($page.url.pathname));
          return;
        }
        comments.comments = [
          e.detail.comment_view,
          ...comments.comments,
        ];
      }}
      on:submit={() => {
        if (!$profile?.jwt) {
          goto('/login?redirect=' + encodeURIComponent($page.url.pathname));
          return;
        }
      }}
      locked={(data.post.post_view.post.locked &&
        !(
          $profile?.user?.local_user_view.local_user.admin ||
          $profile?.user?.moderates
            .map((c) => c.community.id)
            .includes(data.post.community_view.community.id)
        ))}
      banned={data.post.community_view.banned_from_community}
      on:focus={() => (commenting = true)}
      tools={true}
      preview={true}
      rows={7}
      placeholder={$t('routes.post.addComment')}
    />

    <div class="gap-2 flex items-center max-w-[640px]">
      <Select bind:value={commentSort} on:change={reloadComments}>
        <option value="Hot">{$t('filter.sort.hot')}</option>
        <option value="Top">{$t('filter.sort.top.label')}</option>
        <option value="New">{$t('filter.sort.new')}</option>
        <option value="Old">{$t('filter.sort.old')}</option>
        <option value="Controversial">
          {$t('filter.sort.controversial')}
        </option>
      </Select>
      <Button size="square-md" on:click={reloadComments}>
        <Icon src={ArrowPath} size="16" mini slot="prefix" />
      </Button>
    </div>
    <CommentListVirtualizer
      post={data.post.post_view.post}
      nodes={buildCommentsTree(
        comments.comments,
        undefined,
        (c) =>
          !(
            ($userSettings.hidePosts.deleted && c.comment.deleted) ||
            ($userSettings.hidePosts.removed && c.comment.removed)
          )
      )}
      scrollTo={data.thread.focus}
      autoReply={data.reply}
    />
    {#if comments.comments.length == 0}
      <Placeholder
        icon={ChatBubbleLeftRight}
        title={$t('routes.post.emptyComments.title')}
        description={$t('routes.post.emptyComments.description')}
      ></Placeholder>
    {/if}
  {/await}
  {#if data.post.post_view.counts.comments > 5}
    <EndPlaceholder>
      <span class="text-black dark:text-white font-bold">
        {data.post.post_view.counts.comments}
      </span>
      {$t('routes.post.commentCount')}

      <Button
        color="tertiary"
        on:click={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
        slot="action"
      >
        <Icon src={ChevronDoubleUp} mini size="16" slot="prefix" />
        {$t('routes.post.scrollToTop')}
      </Button>
    </EndPlaceholder>
  {/if}
</section>
{/if}

<section class="mt-4 flex flex-col gap-2 max-w-[640px] w-full mx-auto s-5pF0786g8dBR" id="recomendations">
  {#if !data.recommendations}
    <div class="space-y-4">
      {#each Array(3) as _}
        <div class="animate-pulse flex flex-col gap-2 skeleton w-full bg-white dark:bg-zinc-900 rounded-xl border border-slate-200 dark:border-zinc-800 border-b-slate-300 dark:border-t-zinc-700 p-4 sm:p-6">
          <div class="w-96 h-4" />
          <div class="w-full h-12" />
          <div class="w-48 h-4" />
        </div>
      {/each}
    </div>
  {:else}
    <div class="flex flex-col gap-4">
      <svelte:component
        this={browser ? VirtualFeed : PostFeed}
        posts={finalPosts}
        feedData={feedDataForComponent}
        feedId="recommendations"
      />
    </div>
  {/if}
</section>

<style lang="postcss">
  .skeleton * {
    @apply bg-slate-100 dark:bg-zinc-800 rounded-md;
  }

  :global(.post-content blockquote) {
    @apply border-l-4 pl-4 my-4;
    border-left-color: rgb(234 88 12);
  }

  :global(.post-content blockquote p) {
    @apply text-black dark:text-zinc-200;
  }

  /* Стили для заголовков */
  :global(.post-content h1) {
    font-weight: 500;
  }

  :global(.post-content h2) {
    font-size: 1.2em;
    font-weight: 500;
    line-height: 1.3;
    margin: 1rem 0;
    color: #1f2937;
  }

  :global(.post-content h3) {
    font-size: 1.1em;
    font-weight: 500;
    line-height: 1.4;
    margin: 1rem 0;
    color: #1f2937;
  }

  :global(.dark .post-content h2),
  :global(.dark .post-content h3) {
    color: #e5e7eb;
  }

  :global(.post-content .post-gallery) {
    @apply my-4;
  }

  :global(.post-content .post-gallery .gallery-grid) {
    @apply grid gap-3;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  }

  :global(.post-content .post-gallery .gallery-thumb) {
    @apply relative overflow-hidden rounded-xl bg-slate-100 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700;
  }

  :global(.post-content .post-gallery .gallery-thumb img) {
    @apply w-full h-full object-cover;
    aspect-ratio: 4/3;
    display: block;
  }

  :global(.post-content .post-gallery .gallery-thumb:hover) {
    @apply border-slate-300 dark:border-zinc-600;
  }

  :global(.post-content .post-image-compare) {
    @apply my-4 flex flex-col gap-2;
  }

  :global(.post-content .post-image-compare__viewport) {
    @apply relative overflow-hidden rounded-xl border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-900;
    aspect-ratio: 16/9;
  }

  :global(.post-content .post-image-compare__image) {
    @apply absolute inset-0 w-full h-full object-cover block;
  }

  :global(.post-content .post-image-compare__overlay) {
    @apply absolute inset-0 overflow-hidden;
    width: 100%;
    clip-path: inset(0 50% 0 0);
    -webkit-clip-path: inset(0 50% 0 0);
    pointer-events: none;
  }

  :global(.post-content .post-image-compare__divider) {
    @apply absolute inset-y-0;
    left: 50%;
    width: 2px;
    transform: translateX(-50%);
    background: rgba(255, 255, 255, 0.9);
    box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.2);
    pointer-events: auto;
    cursor: ew-resize;
    touch-action: none;
    z-index: 2;
  }

  :global(.post-content .post-image-compare__knob) {
    @apply absolute rounded-full border border-slate-300 dark:border-zinc-600 bg-white dark:bg-zinc-900;
    top: 50%;
    left: 50%;
    width: 2.15rem;
    height: 2.15rem;
    transform: translate(-50%, -50%);
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.28);
  }

  :global(.post-content .post-image-compare__viewport) {
    cursor: ew-resize;
    touch-action: none;
  }

  :global(.post-content .post-image-compare[data-compare-dragging='1']) {
    user-select: none;
  }

  :global(.post-content .post-image-compare__caption) {
    @apply text-sm text-slate-600 dark:text-zinc-400 text-center;
    margin: 0;
  }

  :global(.post-content .post-spoiler) {
    margin: 1rem 0;
    border-radius: 0.9rem;
    border: 1px solid rgba(148, 163, 184, 0.36);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(148, 163, 184, 0.16), rgba(148, 163, 184, 0) 62%),
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
    outline: 2px solid rgba(148, 163, 184, 0.9);
    outline-offset: -2px;
  }

  :global(.post-content .post-spoiler__title) {
    color: #f8fafc;
    font-size: 0.87rem;
    line-height: 1.3;
    font-weight: 700;
  }

  :global(.post-content .post-spoiler__hint) {
    color: #cbd5e1;
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
    color: #94a3b8;
  }

  :global(.gallery-modal) {
    @apply fixed inset-0 z-50 flex items-center justify-center;
  }

  :global(.gallery-modal-backdrop) {
    @apply absolute inset-0 bg-black/80;
  }

  :global(.gallery-modal-content) {
    @apply relative z-10 max-w-[92vw] max-h-[90vh] flex flex-col items-center gap-4;
  }

  :global(.gallery-modal-image) {
    @apply max-h-[78vh] max-w-[92vw] object-contain rounded-lg;
  }

  :global(.gallery-modal-caption) {
    @apply text-sm text-white/80 text-center;
  }

  :global(.gallery-modal-close) {
    @apply fixed top-6 right-6 text-white bg-black/60 p-3 rounded-full 
    hover:bg-black/80 transition-colors duration-200 z-50 cursor-pointer
    flex items-center justify-center;
  }

  :global(.gallery-modal-prev),
  :global(.gallery-modal-next) {
    @apply fixed top-1/2 -translate-y-1/2 text-white bg-black/50 p-3 rounded-full
    hover:bg-black/70 transition-colors duration-200 z-50 cursor-pointer
    flex items-center justify-center;
  }

  :global(.gallery-modal-prev) {
    @apply left-6;
  }

  :global(.gallery-modal-next) {
    @apply right-6;
  }

  :global(.gallery-modal svg) {
    @apply w-6 h-6;
  }

  :global(.post-content .post-map) {
    @apply relative my-4 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-900;
    cursor: zoom-in;
  }

  :global(.post-content .post-map__frame) {
    width: 100%;
    height: 340px;
    border: 0;
    display: block;
    pointer-events: none;
  }

  :global(.post-content .post-map__hint) {
    @apply absolute right-3 bottom-3 text-xs font-semibold rounded-full px-3 py-1.5 border border-slate-200 dark:border-zinc-700 bg-white/95 dark:bg-zinc-900/95 text-slate-700 dark:text-zinc-200;
    pointer-events: none;
  }

  :global(.post-map-modal) {
    @apply fixed inset-0 z-50 flex items-center justify-center;
  }

  :global(.post-map-modal__backdrop) {
    @apply absolute inset-0 bg-black/70 backdrop-blur-[2px];
  }

  :global(.post-map-modal__content) {
    @apply relative z-10 rounded-2xl overflow-hidden border border-slate-200/30 dark:border-zinc-700/70 bg-white dark:bg-zinc-950;
    width: min(94vw, 1200px);
    height: min(84vh, 760px);
  }

  :global(.post-map-modal__frame) {
    width: 100%;
    height: 100%;
    border: 0;
    display: block;
  }

  :global(.post-map-modal__close) {
    @apply absolute top-3 right-3 w-8 h-8 rounded-full border border-slate-200 dark:border-zinc-700 bg-white/90 dark:bg-zinc-900/90 text-slate-900 dark:text-zinc-100 text-base font-bold flex items-center justify-center cursor-pointer;
  }

  :global(.post-content .image-wrapper) {
    @apply cursor-zoom-in relative inline-block;
  }

  :global(.post-content .image-wrapper .zoom-icon) {
    @apply absolute top-2 right-2 bg-black/50 p-2 rounded-full 
    opacity-0 transition-opacity duration-200 z-10;
  }

  :global(.post-content .image-wrapper:hover .zoom-icon) {
    @apply opacity-100;
  }

  :global(.post-content .zoom-icon svg) {
    @apply w-4 h-4 text-white;
  }

  :global(.post-content .image-wrapper .image-alt-text) {
    @apply text-sm text-slate-600 dark:text-zinc-400 text-center;
  }

  :global(.post-content pre) {
    @apply bg-slate-100 dark:bg-zinc-800 rounded-lg p-4 my-4 overflow-x-auto;
  }

  :global(.post-content pre code) {
    @apply font-mono text-sm text-slate-800 dark:text-zinc-200;
  }

  :global(.post-content blockquote footer) {
    @apply mt-2 text-sm text-slate-500 dark:text-zinc-400 not-italic;
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

  /* Стили для embed блоков */
  :global(.post-content .embed-container) {
    @apply my-6 w-full;
  }

  :global(.post-content .embed-responsive) {
    @apply relative w-full overflow-hidden;
    height: 0;
  }

  :global(.post-content .embed-responsive iframe) {
    @apply absolute top-0 left-0 w-full h-full rounded-lg;
  }

  :global(.post-content .embed-caption) {
    @apply mt-2 text-sm text-slate-600 dark:text-zinc-400 text-center;
  }

  /* Стили для якорных ссылок */
  :global(.post-content [id]) {
    scroll-margin-top: 6rem;
  }

  :global(.post-content h1[id]),
  :global(.post-content h2[id]),
  :global(.post-content h3[id]),
  :global(.post-content h4[id]),
  :global(.post-content h5[id]),
  :global(.post-content h6[id]) {
    scroll-margin-top: 6rem;
  }

  /* Стили для ссылок */
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

  :global(.post-content p:has(.btn-primary)) {
    @apply flex justify-center;
  }

  /* Стили для параграфов в полном просмотре поста */
  :global(.post-content p) {
    margin: 1rem 0;
    overflow-wrap: break-word;
    word-wrap: break-word;
    word-break: break-word;
    min-width: 0;
  }

  /* Стили для жирного текста */
  :global(.post-content strong),
  :global(.post-content b) {
    font-weight: 500;
  }

  @media (max-width: 640px) {
    :global(.post-content .post-map__frame) {
      height: 250px;
    }
  }

</style>
