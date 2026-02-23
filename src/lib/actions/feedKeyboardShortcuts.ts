import { browser } from '$app/environment'

type Params = {
  postSelector?: string
}

const DEFAULT_POST_SELECTOR = '.feed-shortcut-post'

const isEditableTarget = (target: EventTarget | null): boolean => {
  const element = target as HTMLElement | null
  if (!element) return false
  if (element.isContentEditable) return true
  return Boolean(
    element.closest(
      'input, textarea, select, [contenteditable="true"], [contenteditable=""], .ce-popover, .ce-inline-toolbar'
    )
  )
}

export const feedKeyboardShortcuts = (node: HTMLElement, initialParams: Params = {}) => {
  if (!browser) {
    return {
      update() {},
      destroy() {},
    }
  }

  let params = initialParams
  let activeIndex: number | null = null
  let syncRaf: number | null = null

  const getSelector = () => params.postSelector || DEFAULT_POST_SELECTOR

  const getPosts = (): HTMLElement[] =>
    Array.from(node.querySelectorAll(getSelector())) as HTMLElement[]

  const isVisibleInViewport = (element: HTMLElement) => {
    const rect = element.getBoundingClientRect()
    return rect.bottom > 0 && rect.top < window.innerHeight
  }

  const nearestVisiblePostIndex = (): number | null => {
    const posts = getPosts()
    if (!posts.length) return null

    const viewportAnchor = window.innerHeight * 0.4
    let bestIndex = 0
    let bestDistance = Number.POSITIVE_INFINITY
    let foundVisible = false

    posts.forEach((post, index) => {
      const rect = post.getBoundingClientRect()
      const visible = rect.bottom > 0 && rect.top < window.innerHeight
      if (!visible) return
      foundVisible = true
      const center = rect.top + rect.height / 2
      const distance = Math.abs(center - viewportAnchor)
      if (distance < bestDistance) {
        bestDistance = distance
        bestIndex = index
      }
    })

    if (foundVisible) return bestIndex

    posts.forEach((post, index) => {
      const rect = post.getBoundingClientRect()
      const center = rect.top + rect.height / 2
      const distance = Math.abs(center - viewportAnchor)
      if (distance < bestDistance) {
        bestDistance = distance
        bestIndex = index
      }
    })

    return bestIndex
  }

  const applyActiveClass = () => {
    const posts = getPosts()
    posts.forEach((post, index) => {
      post.classList.toggle('keyboard-post-active', activeIndex === index)
    })
  }

  const normalizeActiveIndex = (preferNearest = false): number | null => {
    const posts = getPosts()
    if (!posts.length) {
      activeIndex = null
      return null
    }

    if (preferNearest || activeIndex === null) {
      activeIndex = nearestVisiblePostIndex() ?? 0
      applyActiveClass()
      return activeIndex
    }

    const current = posts[activeIndex]
    if (!current) {
      activeIndex = Math.min(Math.max(0, activeIndex), posts.length - 1)
      applyActiveClass()
      return activeIndex
    }

    if (!isVisibleInViewport(current)) {
      activeIndex = nearestVisiblePostIndex() ?? activeIndex
      applyActiveClass()
    }

    return activeIndex
  }

  const scrollToPost = (index: number) => {
    const posts = getPosts()
    const target = posts[index]
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const moveSelection = (delta: number) => {
    const posts = getPosts()
    if (!posts.length) return
    const baseIndex = normalizeActiveIndex(false) ?? 0
    const nextIndex = Math.max(0, Math.min(posts.length - 1, baseIndex + delta))
    activeIndex = nextIndex
    applyActiveClass()
    scrollToPost(nextIndex)
  }

  const clickActivePostAction = (selector: string) => {
    const index = normalizeActiveIndex(true)
    if (index === null) return
    const posts = getPosts()
    const post = posts[index]
    if (!post) return
    post.querySelector<HTMLElement>(selector)?.click()
  }

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.defaultPrevented) return
    if (event.metaKey || event.ctrlKey || event.altKey) return
    if (event.repeat) return
    if (isEditableTarget(event.target)) return

    switch (event.code) {
      case 'KeyW':
        event.preventDefault()
        clickActivePostAction('[data-post-action-vote-up]')
        break
      case 'KeyS':
        event.preventDefault()
        clickActivePostAction('[data-post-action-vote-down]')
        break
      case 'KeyA':
        event.preventDefault()
        moveSelection(-1)
        break
      case 'KeyD':
        event.preventDefault()
        moveSelection(1)
        break
      case 'KeyF':
        event.preventDefault()
        clickActivePostAction('[data-post-action-toggle-expand]')
        break
      default:
        break
    }
  }

  const syncToViewport = () => {
    if (syncRaf !== null) return
    syncRaf = window.requestAnimationFrame(() => {
      syncRaf = null
      normalizeActiveIndex(true)
    })
  }

  const mutationObserver = new MutationObserver(() => {
    normalizeActiveIndex(true)
  })
  mutationObserver.observe(node, { childList: true, subtree: true })

  window.addEventListener('keydown', handleKeydown)
  window.addEventListener('scroll', syncToViewport, { passive: true })
  window.addEventListener('resize', syncToViewport)
  normalizeActiveIndex(true)

  return {
    update(nextParams: Params = {}) {
      params = nextParams
      normalizeActiveIndex(true)
    },
    destroy() {
      window.removeEventListener('keydown', handleKeydown)
      window.removeEventListener('scroll', syncToViewport)
      window.removeEventListener('resize', syncToViewport)
      mutationObserver.disconnect()
      if (syncRaf !== null) {
        window.cancelAnimationFrame(syncRaf)
        syncRaf = null
      }
      activeIndex = null
      applyActiveClass()
    },
  }
}

