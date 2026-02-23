import { browser } from '$app/environment'

type Params = {
  text?: string
  offset?: number
}

const BASE_Z_INDEX = 10000

const createTooltipEl = () => {
  const el = document.createElement('div')
  Object.assign(el.style, {
    position: 'fixed',
    left: '0px',
    top: '0px',
    zIndex: String(BASE_Z_INDEX),
    pointerEvents: 'none',
    opacity: '0',
    transform: 'translate3d(0,0,0)',
    transition: 'opacity 120ms ease',
    background: 'rgba(15, 23, 42, 0.95)',
    color: '#fff',
    borderRadius: '6px',
    padding: '6px 8px',
    fontSize: '12px',
    lineHeight: '1.2',
    whiteSpace: 'nowrap',
    boxShadow: '0 6px 16px rgba(0, 0, 0, 0.22)',
  } satisfies Partial<CSSStyleDeclaration>)
  return el
}

export const portalTooltip = (node: HTMLElement, initialParams: Params = {}) => {
  if (!browser) {
    return {
      update() {},
      destroy() {},
    }
  }

  let params = initialParams
  let tooltipEl: HTMLDivElement | null = null
  let visible = false

  const getText = () =>
    (params.text ?? node.getAttribute('data-tooltip') ?? node.getAttribute('title') ?? '').trim()

  const getOffset = () => params.offset ?? 10

  const ensureTooltip = () => {
    if (tooltipEl) return tooltipEl
    tooltipEl = createTooltipEl()
    document.body.appendChild(tooltipEl)
    return tooltipEl
  }

  const positionTooltip = () => {
    if (!tooltipEl || !visible) return
    const text = getText()
    if (!text) return

    const rect = node.getBoundingClientRect()
    const margin = 8
    const offset = getOffset()

    tooltipEl.textContent = text
    tooltipEl.style.opacity = '0'

    // Measure after text update.
    const { offsetWidth: width, offsetHeight: height } = tooltipEl
    const viewportW = window.innerWidth
    const viewportH = window.innerHeight

    let left = rect.left + rect.width / 2 - width / 2
    left = Math.max(margin, Math.min(left, viewportW - width - margin))

    let top = rect.top - height - offset
    if (top < margin) {
      top = rect.bottom + offset
    }
    top = Math.max(margin, Math.min(top, viewportH - height - margin))

    tooltipEl.style.left = `${Math.round(left)}px`
    tooltipEl.style.top = `${Math.round(top)}px`
    tooltipEl.style.opacity = '1'
  }

  const show = () => {
    const text = getText()
    if (!text) return
    visible = true
    const el = ensureTooltip()
    el.textContent = text
    positionTooltip()
    window.addEventListener('scroll', positionTooltip, true)
    window.addEventListener('resize', positionTooltip)
  }

  const hide = () => {
    visible = false
    if (tooltipEl) {
      tooltipEl.style.opacity = '0'
    }
    window.removeEventListener('scroll', positionTooltip, true)
    window.removeEventListener('resize', positionTooltip)
  }

  const onMouseEnter = () => show()
  const onMouseLeave = () => hide()
  const onFocus = () => show()
  const onBlur = () => hide()

  node.addEventListener('mouseenter', onMouseEnter)
  node.addEventListener('mouseleave', onMouseLeave)
  node.addEventListener('focus', onFocus)
  node.addEventListener('blur', onBlur)

  return {
    update(nextParams: Params = {}) {
      params = nextParams
      if (visible) positionTooltip()
    },
    destroy() {
      hide()
      node.removeEventListener('mouseenter', onMouseEnter)
      node.removeEventListener('mouseleave', onMouseLeave)
      node.removeEventListener('focus', onFocus)
      node.removeEventListener('blur', onBlur)
      if (tooltipEl?.parentNode) {
        tooltipEl.parentNode.removeChild(tooltipEl)
      }
      tooltipEl = null
    },
  }
}

