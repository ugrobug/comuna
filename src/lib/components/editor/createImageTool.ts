type ImageData = { file: { url: string; alt: string; title: string }; caption: string }
type ToolOptions = {
  icon: string
  upload: (file: File) => Promise<{ url: string; useWebp: boolean }>
  onError: (error: unknown) => string
  onPendingChange: (delta: number) => void
  showPostSettings: () => boolean
  getPreview: () => string
  setPreview: (url: string) => void
}

export const createImageTool = (options: ToolOptions) => class {
  private data: ImageData
  private initialFile?: File
  private block: { dispatchChange: () => void } | undefined
  private wrapper?: HTMLDivElement
  private image?: HTMLImageElement
  private input?: HTMLInputElement
  private button?: HTMLButtonElement
  private loader?: HTMLDivElement
  private error?: HTMLParagraphElement
  private previewControl?: HTMLDivElement
  private pending: Promise<void> | null = null
  private previewUrl: string | null = null
  private destroyed = false

  static get toolbox() {
    return { title: 'Изображение', icon: `<img src="${options.icon}" width="16" height="16" />` }
  }

  static get pasteConfig() {
    return { tags: [{ img: { src: true, alt: true } }], files: { mimeTypes: ['image/*'] } }
  }

  constructor({ data, block }: { data?: Partial<ImageData> & { uploadFile?: File }; block?: { dispatchChange: () => void } }) {
    const caption = data?.caption || data?.file?.alt || data?.file?.title || ''
    this.data = { file: { url: data?.file?.url || '', alt: caption, title: data?.file?.title || '' }, caption }
    this.initialFile = data?.uploadFile
    this.block = block
  }

  private refreshPreviewControl() {
    if (!this.previewControl) return
    this.previewControl.hidden = !this.data.file.url
    const selected = this.data.file.url === options.getPreview()
    this.previewControl.classList.toggle('active', selected)
    this.previewControl.textContent = `${selected ? '★' : '☆'} Вывести в ленте`
  }

  render() {
    this.wrapper = document.createElement('div')
    this.wrapper.className = 'image-tool__wrapper'
    const imageWrapper = document.createElement('div')
    imageWrapper.className = 'image-tool__image-wrapper'
    this.image = document.createElement('img')
    this.image.alt = this.data.file.alt
    this.image.title = this.data.file.title
    if (this.data.file.url) this.image.src = this.data.file.url
    else this.image.hidden = true
    imageWrapper.append(this.image)

    if (options.showPostSettings()) {
      this.previewControl = document.createElement('div')
      this.previewControl.className = 'image-tool__preview-control'
      this.refreshPreviewControl()
      this.previewControl.onclick = (event) => {
        event.preventDefault()
        if (!this.data.file.url || this.pending) return
        options.setPreview(this.data.file.url === options.getPreview() ? '' : this.data.file.url)
        this.refreshPreviewControl()
        this.block?.dispatchChange()
      }
      imageWrapper.append(this.previewControl)
    }

    this.input = document.createElement('input')
    this.input.type = 'file'
    this.input.accept = 'image/*'
    this.input.hidden = true
    this.input.onchange = () => {
      const file = this.input?.files?.[0]
      if (file) void this.uploadFile(file)
    }
    this.button = document.createElement('button')
    this.button.type = 'button'
    this.button.className = 'image-tool__button'
    this.button.textContent = 'Загрузить изображение'
    this.button.onclick = () => this.input?.click()
    this.loader = document.createElement('div')
    this.loader.className = 'image-tool__loader'
    this.loader.setAttribute('role', 'status')
    this.loader.textContent = 'Загрузка изображения…'
    this.loader.hidden = true
    this.error = document.createElement('p')
    this.error.className = 'image-tool__error'
    this.error.setAttribute('role', 'alert')
    this.error.hidden = true

    const caption = document.createElement('textarea')
    caption.className = 'image-tool__caption'
    caption.setAttribute('aria-label', 'Подпись изображения')
    caption.placeholder = 'Подпись изображения'
    caption.value = this.data.caption
    caption.oninput = () => {
      this.data.caption = caption.value
      this.data.file.alt = caption.value
      if (this.image) this.image.alt = caption.value
      this.block?.dispatchChange()
    }
    this.wrapper.append(imageWrapper, this.loader, this.error, this.button, this.input, caption)
    if (this.initialFile) {
      const file = this.initialFile
      this.initialFile = undefined
      void this.uploadFile(file)
    }
    return this.wrapper
  }

  // Only a toolbox insertion should open the picker, never a paste or saved block.
  appendCallback() {
    if (!this.data.file.url && !this.pending) this.input?.click()
  }

  uploadFile(file: File): Promise<void> {
    if (this.pending || this.destroyed) return this.pending ?? Promise.resolve()
    const previousUrl = this.data.file.url
    this.previewUrl = URL.createObjectURL(file)
    this.image!.src = this.previewUrl
    this.image!.hidden = false
    this.loader!.hidden = false
    this.error!.hidden = true
    this.button!.disabled = true
    this.wrapper!.setAttribute('aria-busy', 'true')
    options.onPendingChange(1)

    this.pending = (async () => {
      try {
        const uploaded = await options.upload(file)
        if (!uploaded?.url) throw new Error('Не удалось загрузить изображение')
        if (this.destroyed) return
        this.data.file.url = uploaded.useWebp ? `${uploaded.url}?format=webp` : uploaded.url
        this.image!.src = this.data.file.url
        this.refreshPreviewControl()
        this.block?.dispatchChange()
      } catch (error) {
        if (this.destroyed) return
        this.image!.hidden = !previousUrl
        if (previousUrl) this.image!.src = previousUrl
        else this.image!.removeAttribute('src')
        this.error!.textContent = options.onError(error)
        this.error!.hidden = false
      } finally {
        this.releasePreview()
        this.pending = null
        this.loader!.hidden = true
        this.button!.disabled = false
        this.wrapper!.removeAttribute('aria-busy')
        if (this.input) this.input.value = ''
        options.onPendingChange(-1)
      }
    })()
    return this.pending
  }

  async onPaste(event: { type: string; detail: { file?: File; data?: HTMLElement } }) {
    if (event.type === 'file' && event.detail.file) return this.uploadFile(event.detail.file)
    if (event.type !== 'tag') return
    const source = event.detail.data?.getAttribute('src') || ''
    if (/^https?:\/\//i.test(source)) {
      this.data.file.url = source
      this.image!.src = source
      this.image!.hidden = false
      this.refreshPreviewControl()
      this.block?.dispatchChange()
    } else if (/^data:image\/(png|jpeg|webp|gif);base64,/i.test(source)) {
      try {
        const blob = await (await fetch(source)).blob()
        await this.uploadFile(new File([blob], 'clipboard-image', { type: blob.type }))
      } catch (error) {
        this.error!.textContent = options.onError(error)
        this.error!.hidden = false
      }
    }
  }

  async save() {
    await this.pending
    // Local previews and File objects must never be serialized into a post.
    return this.data
  }

  private releasePreview() {
    if (this.previewUrl) URL.revokeObjectURL(this.previewUrl)
    this.previewUrl = null
  }

  destroy() {
    this.destroyed = true
    this.releasePreview()
  }
}
