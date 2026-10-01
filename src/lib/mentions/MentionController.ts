export interface MentionCandidate {
  kind: 'user' | 'comun'
  id: number
  handle: string
  label: string
  url: string
}
export interface MentionOptions {
  enabled: boolean
  token: string | null | undefined
  mode: 'markdown' | 'html'
}
export interface MentionQuery { start: number; query: string }

export class MentionSyntax {
  static query(text: string): MentionQuery | null {
    const match = /(?:^|[\s(])@([\p{L}\p{N}_.\- ]{0,80})$/u.exec(text)
    if (!match || match[1].split(' ').length > 5) return null
    return { start: text.length - match[1].length - 1, query: match[1].trim() }
  }

  static markdown(item: MentionCandidate): string {
    const label = `@${item.kind === 'user' ? item.handle : item.label}`.replace(/[\\[\]]/g, '\\$&')
    return `[${label}](${item.url}) `
  }
}

interface SelectionContext {
  editable: HTMLElement | HTMLTextAreaElement
  query: MentionQuery
  range?: Range
  caret: number
}

/** One controller per editor; requests and DOM listeners never outlive that editor. */
export class MentionController {
  private popup: HTMLDivElement
  private items: MentionCandidate[] = []
  private selected = 0
  private context: SelectionContext | null = null
  private timer: ReturnType<typeof setTimeout> | undefined
  private request: AbortController | null = null
  private generation = 0
  private composing = false
  private cleanups: Array<() => void> = []
  private previousAria: Array<[HTMLElement, string, string | null]> = []
  private static sequence = 0

  constructor(private root: HTMLElement, private options: MentionOptions, private endpoint: string) {
    this.popup = document.createElement('div')
    this.popup.className = 'mention-suggestions'
    this.popup.id = `mention-list-${++MentionController.sequence}`
    this.popup.setAttribute('role', 'listbox')
    this.popup.setAttribute('aria-label', 'Упомянуть пользователя или сообщество')
    this.popup.hidden = true
    document.body.append(this.popup)
    this.listen(root, 'input', () => this.schedule())
    this.listen(root, 'keyup', (event) => {
      if (['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes((event as KeyboardEvent).key)) this.schedule()
    })
    this.listen(root, 'keydown', (event) => this.keydown(event as KeyboardEvent), true)
    this.listen(root, 'compositionstart', () => { this.composing = true; this.close() })
    this.listen(root, 'compositionend', () => { this.composing = false; this.schedule() })
    this.listen(document, 'pointerdown', (event) => {
      if (!this.popup.contains(event.target as Node)) this.close()
    })
    this.listen(root, 'focusout', () => this.close())
    this.listen(window, 'resize', () => this.close())
    this.listen(window, 'scroll', (event) => {
      if (!(event.target instanceof Node) || !this.popup.contains(event.target)) this.close()
    }, true)
  }

  update(options: MentionOptions) {
    if (this.options.token !== options.token || this.options.enabled !== options.enabled) this.close()
    this.options = options
  }

  private listen(target: EventTarget, type: string, callback: EventListener, capture = false) {
    target.addEventListener(type, callback, capture)
    this.cleanups.push(() => target.removeEventListener(type, callback, capture))
  }

  private selection(): SelectionContext | null {
    if (!this.options.enabled || !this.options.token || this.composing) return null
    const active = document.activeElement
    if (!active || !this.root.contains(active)) return null
    if (this.options.mode === 'markdown') {
      if (!(active instanceof HTMLTextAreaElement) || active.disabled || active.selectionStart !== active.selectionEnd) return null
      const caret = active.selectionStart
      const before = active.value.slice(0, caret)
      // Do not activate in an unfinished markdown link or inline/fenced code.
      if ((before.match(/`/g)?.length || 0) % 2 || /\[[^\]]*$/.test(before)) return null
      const query = MentionSyntax.query(before)
      return query ? {editable: active, query, caret} : null
    }
    const selection = window.getSelection()
    if (!selection?.isCollapsed || !selection.rangeCount) return null
    const node = selection.anchorNode
    const editable = (node instanceof Element ? node : node?.parentElement)?.closest<HTMLElement>('[contenteditable="true"]')
    if (!editable || !this.root.contains(editable) || (node instanceof Element ? node : node?.parentElement)?.closest('a, code, pre')) return null
    const range = selection.getRangeAt(0).cloneRange()
    const prefix = range.cloneRange()
    prefix.selectNodeContents(editable)
    prefix.setEnd(range.endContainer, range.endOffset)
    const before = prefix.toString()
    const query = MentionSyntax.query(before)
    return query ? {editable, range, query, caret: before.length} : null
  }

  private schedule() {
    this.close()
    const context = this.selection()
    if (!context) return
    this.context = context
    this.showMessage(context.query.query ? 'Ищем…' : 'Введите ник, имя или название сообщества')
    if (!context.query.query) return
    const generation = this.generation
    this.timer = setTimeout(() => void this.search(context.query.query, generation), 180)
  }

  private async search(query: string, generation: number) {
    const request = new AbortController()
    this.request = request
    try {
      const response = await fetch(`${this.endpoint}?q=${encodeURIComponent(query)}`, {
        headers: {Authorization: `Bearer ${this.options.token}`}, signal: request.signal,
      })
      if (!response.ok) throw new Error('search failed')
      const data = await response.json()
      if (request.signal.aborted || generation !== this.generation) return
      this.items = (Array.isArray(data.items) ? data.items : []).slice(0, 10)
      this.selected = 0
      if (!this.items.length) this.showMessage('Совпадений нет')
      else this.render()
    } catch {
      if (!request.signal.aborted && generation === this.generation) this.showMessage('Не удалось выполнить поиск. Попробуйте ещё раз.')
    }
  }

  private showMessage(text: string) {
    this.popup.replaceChildren()
    const message = document.createElement('div')
    message.className = 'mention-suggestions__message'
    message.setAttribute('role', 'status')
    message.textContent = text
    this.popup.append(message)
    this.show()
  }

  private render() {
    this.popup.replaceChildren()
    this.items.forEach((item, index) => {
      const option = document.createElement('div')
      option.id = `${this.popup.id}-${index}`
      option.className = 'mention-suggestions__option'
      option.setAttribute('role', 'option')
      option.setAttribute('aria-selected', String(index === this.selected))
      const name = document.createElement('strong')
      name.textContent = item.label
      const detail = document.createElement('span')
      detail.textContent = `${item.kind === 'user' ? 'Пользователь' : 'Сообщество'} · @${item.handle}`
      option.append(name, detail)
      option.addEventListener('pointerdown', (event) => event.preventDefault())
      option.addEventListener('click', () => this.insert(item))
      this.popup.append(option)
    })
    this.show()
    this.context?.editable.setAttribute('aria-activedescendant', `${this.popup.id}-${this.selected}`)
  }

  private show() {
    if (!this.context) return
    this.popup.hidden = false
    const editable = this.context.editable
    if (!this.previousAria.length) {
      for (const name of ['aria-controls', 'aria-expanded', 'aria-autocomplete', 'aria-activedescendant']) {
        this.previousAria.push([editable, name, editable.getAttribute(name)])
      }
    }
    editable.setAttribute('aria-controls', this.popup.id)
    editable.setAttribute('aria-expanded', 'true')
    editable.setAttribute('aria-autocomplete', 'list')
    const rect = this.context.range?.getBoundingClientRect() || editable.getBoundingClientRect()
    const viewport = window.visualViewport
    const left = viewport?.offsetLeft || 0, top = viewport?.offsetTop || 0
    const width = viewport?.width || window.innerWidth, height = viewport?.height || window.innerHeight
    const popupWidth = Math.min(350, width - 16)
    this.popup.style.width = `${popupWidth}px`
    this.popup.style.maxHeight = `${Math.max(80, Math.min(280, height - 32))}px`
    const popupHeight = this.popup.getBoundingClientRect().height
    this.popup.style.left = `${Math.max(left + 8, Math.min(rect.left, left + width - popupWidth - 8))}px`
    this.popup.style.top = `${Math.max(top + 8, Math.min(rect.bottom + 6, top + height - popupHeight - 8))}px`
  }

  private keydown(event: KeyboardEvent) {
    if (this.popup.hidden || event.isComposing) return
    if (event.key === 'Escape') { event.preventDefault(); event.stopImmediatePropagation(); this.close(); return }
    if (!this.items.length || !['ArrowDown', 'ArrowUp', 'Enter', 'Tab'].includes(event.key)) return
    event.preventDefault()
    event.stopImmediatePropagation()
    if (event.key === 'Enter' || event.key === 'Tab') this.insert(this.items[this.selected])
    else {
      this.selected = (this.selected + (event.key === 'ArrowDown' ? 1 : -1) + this.items.length) % this.items.length
      this.render()
      this.popup.children[this.selected]?.scrollIntoView({block: 'nearest'})
    }
  }

  private insert(item: MentionCandidate) {
    const context = this.context
    // Recheck the selection: a stale server response must not replace unrelated text.
    const live = this.selection()
    if (!context || !live || live.editable !== context.editable || live.caret !== context.caret || live.query.query !== context.query.query) {
      this.close(); return
    }
    const existing = context.editable instanceof HTMLTextAreaElement
      ? context.editable.value
      : Array.from(this.root.querySelectorAll('a[href]')).map(link => link.getAttribute('href')).join(' ')
    const targets = new Set(Array.from(existing.matchAll(/[?&]mention=(user|comun)\.(\d+)/g), match => `${match[1]}.${match[2]}`))
    if (targets.size >= 20 && !targets.has(`${item.kind}.${item.id}`)) {
      this.items = []
      this.showMessage('Можно упомянуть до 20 пользователей и сообществ в одном сообщении.')
      return
    }
    if (context.editable instanceof HTMLTextAreaElement) {
      context.editable.setRangeText(MentionSyntax.markdown(item), context.query.start, context.caret, 'end')
    } else if (context.range) {
      const range = context.range.cloneRange()
      const walker = document.createTreeWalker(context.editable, NodeFilter.SHOW_TEXT)
      let offset = context.query.start
      let node: Node | null = null
      while ((node = walker.nextNode())) {
        const length = node.textContent?.length || 0
        if (offset <= length) { range.setStart(node, offset); break }
        offset -= length
      }
      if (!node) { this.close(); return }
      range.deleteContents()
      const anchor = document.createElement('a')
      anchor.href = item.url
      anchor.textContent = `@${item.kind === 'user' ? item.handle : item.label}`
      range.insertNode(anchor)
      const space = document.createTextNode('\u00a0')
      anchor.after(space)
      range.setStartAfter(space)
      range.collapse(true)
      window.getSelection()?.removeAllRanges()
      window.getSelection()?.addRange(range)
    }
    const editable = context.editable
    this.close()
    editable.dispatchEvent(new Event('input', {bubbles: true}))
  }

  close() {
    clearTimeout(this.timer)
    this.request?.abort()
    this.request = null
    this.generation++
    this.popup.hidden = true
    this.items = []
    this.context = null
    for (const [element, name, value] of this.previousAria) {
      if (value === null) element.removeAttribute(name)
      else element.setAttribute(name, value)
    }
    this.previousAria = []
  }

  destroy() {
    this.close()
    this.cleanups.forEach(cleanup => cleanup())
    this.popup.remove()
  }
}
