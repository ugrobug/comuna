/** Enhances each body gallery once and preserves its full-resolution image group. */
export class PostGallery {
  constructor(private readonly element: Element) {}

  enhance(): void {
    if (this.element.hasAttribute('data-gallery-ready')) return
    const images = Array.from(this.element.querySelectorAll('img'))
    if (!images.length) return
    const mainWrapper = document.createElement('div')
    mainWrapper.className = 'featured-gallery-main'
    const main = document.createElement('img')
    main.setAttribute('data-expandable-image', '1')
    main.loading = 'lazy'
    mainWrapper.append(main)
    const thumbs = document.createElement('div')
    thumbs.className = 'featured-gallery-thumbs'
    const select = (image: HTMLImageElement, button: HTMLButtonElement) => {
      for (const name of ['src', 'srcset', 'sizes', 'alt', 'data-expandable-src']) {
        const value = image.getAttribute(name)
        if (value) main.setAttribute(name, value)
        else main.removeAttribute(name)
      }
      thumbs.querySelectorAll('button').forEach((item) => {
        item.classList.toggle('active', item === button)
        item.setAttribute('aria-pressed', String(item === button))
      })
    }
    images.forEach((image, index) => {
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'featured-gallery-thumb'
      button.setAttribute('aria-pressed', 'false')
      button.setAttribute('aria-label', `Изображение ${index + 1} из ${images.length}`)
      const thumb = image.cloneNode(false) as HTMLImageElement
      thumb.removeAttribute('style')
      thumb.removeAttribute('data-preview-hidden')
      thumb.loading = 'lazy'
      thumb.sizes = '96px'
      button.append(thumb)
      button.addEventListener('click', (event) => {
        event.stopPropagation()
        select(image, button)
      })
      thumbs.append(button)
      if (index === 0) select(image, button)
    })
    this.element.replaceChildren(mainWrapper, thumbs)
    this.element.classList.add('featured-gallery')
    this.element.setAttribute('data-gallery-ready', '1')
  }
}
