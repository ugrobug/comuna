<script lang="ts">
  import { onMount, onDestroy } from 'svelte'
  import { profile } from '$lib/auth'
  import { uploadSiteImage, siteToken } from '$lib/siteAuth'
  import {
    getTemplateEditorBlockTypes,
    normalizeTemplateEditorBlockTypes,
    type PostTemplateType,
  } from '$lib/postTemplates'
  import {
    uploadImage,
    serializeEditorModel,
    deserializeEditorModel,
    parseGpsCoordinates,
    normalizeOpenStreetMapZoom,
    buildOpenStreetMapEmbedUrl,
  } from '$lib/util'
  import { get } from 'svelte/store'
  import { Button, toast } from 'mono-svelte'
  import CustomInputTune from './CustomInputTune'
  import './CustomInputTune.css'
  import { saveDraft, getDraft, formatLastSaved, getDraftLastSaved } from '$lib/session'

  export let showPostSettings: boolean = true

  const uploadEditorImage = async (file: File) => {
    if (get(siteToken)) {
      return { url: await uploadSiteImage(file), useWebp: false }
    }
    if ($profile?.jwt) {
      return {
        url: await uploadImage(file, $profile.instance, $profile.jwt),
        useWebp: true,
      }
    }
    throw new Error('Нужна авторизация для загрузки изображений')
  }

  const humanizeUploadError = (error: unknown): string => {
    const rawMessage = error instanceof Error ? error.message : String(error ?? '')
    const message = rawMessage.trim()
    if (!message) {
      return 'Не удалось загрузить изображение'
    }
    const lowered = message.toLowerCase()
    if (
      lowered.includes('слишком большой') ||
      lowered.includes('too large') ||
      lowered.includes('413')
    ) {
      return 'Файл слишком большой. Максимальный размер — 10 МБ.'
    }
    return message
  }

  // Импортируем иконки
  const iconPath = '/img/editorjs'
  const icons = {
    delete: `${iconPath}/x-lg.svg`,
    moveDown: `${iconPath}/chevron-down.svg`,
    convert: `${iconPath}/arrow-repeat.svg`,
    moveUp: `${iconPath}/chevron-up.svg`,
    gallery: `${iconPath}/images.svg`,
    code: `${iconPath}/code-slash.svg`,
    header: `${iconPath}/type-h2.svg`,
    unorderedList: `${iconPath}/list-ul.svg`,
    orderedList: `${iconPath}/list-ol.svg`,
    checklist: `${iconPath}/list-check.svg`,
    clock: `${iconPath}/clock.svg`,
    music: `${iconPath}/music-note.svg`,
    map: `${iconPath}/geo-alt.svg`,
    imageCompare: `${iconPath}/images.svg`,
    movieCard: `${iconPath}/card-image.svg`,
    quote: `${iconPath}/quote.svg`,
    image: `${iconPath}/card-image.svg`,
    link: `${iconPath}/link-45deg.svg`,
    italic: `${iconPath}/type-italic.svg`,
    bold: `${iconPath}/type-bold.svg`,
    text: `${iconPath}/type.svg`
  }

  // Кастомный плагин для ссылок
  class CustomLinkTool {
    private api: any;
    private data: { url: string; title: string; text: string; style?: string };
    private config: any;
    private wrapper: HTMLElement | null = null;
    private suggestionList: HTMLElement | null = null;

    static get toolbox() {
      return {
        title: 'Ссылка',
        icon: `<img src="${icons.link}" width="16" height="16" />`
      }
    }

    constructor({ data, config, api }: { data?: { url: string; title: string; text: string; style?: string }, config?: any, api?: any }) {
      this.api = api;
      this.data = {
        url: data?.url || '',
        title: data?.title || '',
        text: data?.text || '',
        style: data?.style || 'link'
      };
      this.config = config || {};
    }

    private async getAnchors(): Promise<string[]> {
      const anchors: string[] = [];
      const count = this.api.blocks.getBlocksCount();
      
      console.log('Blocks count:', count);
      
      for (let i = 0; i < count; i++) {
        const block = this.api.blocks.getBlockByIndex(i);
        const data = await block.save();
        //console.log('Block data:', data);
        
        // Проверяем разные возможные пути к якорю
        const anchorText = data?.tunes?.anchorInput?.text || 
                         data?.tunes?.customInput?.text || 
                         block?.tunes?.anchorInput?.text ||
                         block?.tunes?.customInput?.text;
                         
        if (anchorText) {
          //console.log('Found anchor:', anchorText);
          anchors.push(anchorText);
        }
      }
      
      //console.log('All anchors:', anchors);
      return anchors;
    }

    private async createSuggestionList() {
      if (this.suggestionList) {
        this.suggestionList.remove();
      }

      const suggestionList = document.createElement('div');
      suggestionList.classList.add('link-suggestions');
      this.suggestionList = suggestionList;
      
      const anchors = await this.getAnchors();
      if (anchors.length > 0) {
        const title = document.createElement('div');
        title.classList.add('link-suggestions__title');
        title.textContent = 'Якоря в материале:';
        suggestionList.appendChild(title);
        
        anchors.forEach(anchor => {
          if (!anchor) return;
          
          const item = document.createElement('div');
          item.classList.add('link-suggestions__item');
          item.textContent = `#${anchor}`;
          item.onclick = () => {
            if (this.wrapper) {
              const urlInput = this.wrapper.querySelector('input:nth-child(2)') as HTMLInputElement;
              if (urlInput) {
                urlInput.value = `#${anchor}`;
                this.data.url = `#${anchor}`;
                this.data.title = `Якорь: ${anchor}`;
              }
            }
            suggestionList.remove();
          };
          suggestionList.appendChild(item);
        });
      }

      return suggestionList;
    }

    render() {
      this.wrapper = document.createElement('div');
      this.wrapper.classList.add('link-tool');
      
      const textInput = document.createElement('input');
      textInput.classList.add('link-tool__input');
      textInput.placeholder = 'Введите текст ссылки...';
      textInput.value = this.data.text;
      
      textInput.addEventListener('input', () => {
        this.data.text = textInput.value;
      });
      
      const urlWrapper = document.createElement('div');
      urlWrapper.classList.add('link-tool__row');
      
      const urlInput = document.createElement('input');
      urlInput.classList.add('link-tool__input', 'link-tool__input--url');
      urlInput.placeholder = 'Вставьте URL или выберите якорь...';
      urlInput.value = this.data.url;
      
      urlInput.addEventListener('input', () => {
        this.data.url = urlInput.value;
      });
      
      urlInput.addEventListener('focus', async () => {
        const suggestions = await this.createSuggestionList();
        this.wrapper?.appendChild(suggestions);
      });
      
      urlInput.addEventListener('blur', () => {
        // Небольшая задержка, чтобы успеть обработать клик по подсказке
        setTimeout(() => {
          this.suggestionList?.remove();
        }, 200);
      });

      const styleSelect = document.createElement('select');
      styleSelect.classList.add('link-tool__input', 'link-tool__input--select');
      styleSelect.innerHTML = `
        <option value="link">Обычная ссылка</option>
        <option value="btn-primary">Кнопка Primary</option>
      `;
      styleSelect.value = this.data.style || 'link';
      
      styleSelect.addEventListener('change', () => {
        console.log('Style changed to:', styleSelect.value);
        this.data.style = styleSelect.value;
        console.log('Updated data:', this.data);
        // Принудительно вызываем сохранение всего редактора
        editor.save().then((savedData: any) => {
          console.log('Editor saved data:', savedData);
          updateMarkdown(savedData);
        });
      });
      
      urlWrapper.appendChild(urlInput);
      urlWrapper.appendChild(styleSelect);
      
      this.wrapper.appendChild(textInput);
      this.wrapper.appendChild(urlWrapper);
      
      return this.wrapper;
    }

    save() {
      console.log('Save method called, current data:', this.data);
      const savedData = {
        text: this.data.text,
        url: this.data.url,
        style: this.data.style || 'link'
      };
      console.log('Returning saved data:', savedData);
      return savedData;
    }
  }

  // Кастомный плагин для галереи
  class GalleryTool {
    private api: any;
    private data: { images: Array<{ url: string; alt: string; title: string }> };
    private config: any;
    private isUploading: boolean = false;

    static get toolbox() {
      return {
        title: 'Галерея',
        icon: `<img src="${icons.gallery}" width="16" height="16" />`
      }
    }

    constructor({ data, config, api }: { data?: { images: Array<{ url: string; alt: string; title: string }> }, config?: any, api?: any }) {
      this.api = api
      this.data = {
        images: Array.isArray(data?.images) ? data.images : []
      }
      this.config = config || {}
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('gallery-wrapper')
      
      const input = document.createElement('input')
      input.type = 'file'
      input.multiple = true
      input.accept = 'image/*'
      input.style.display = 'none'
      
      const button = document.createElement('button')
      button.classList.add('gallery-button')
      button.textContent = 'Добавить изображения'
      button.onclick = (e) => {
        e.preventDefault()
        e.stopPropagation()
        input.click()
      }
      
      const gallery = document.createElement('div')
      gallery.classList.add('gallery-grid')
      
      const loader = document.createElement('div')
      loader.classList.add('gallery-loader')
      loader.innerHTML = `
        <div class="gallery-loader-spinner"></div>
        <div class="gallery-loader-text">Загрузка изображений...</div>
      `
      
      input.onchange = async (e: Event) => {
        const target = e.target as HTMLInputElement
        if (!target.files) return
        
        const files = Array.from(target.files)
        if (files.length > 0) {
          try {
            this.isUploading = true
            wrapper.appendChild(loader)
            button.disabled = true
            button.textContent = 'Загрузка...'
            
            for (const file of files) {
              try {
                const uploaded = await uploadEditorImage(file)
                if (uploaded?.url) {
                  const finalUrl = uploaded.useWebp ? `${uploaded.url}?format=webp` : uploaded.url
                  this.data.images.push({
                    url: finalUrl,
                    alt: '',
                    title: ''
                  })
                  this.renderGallery(gallery)
                }
              } catch (error) {
                console.error('Ошибка при загрузке изображения:', error)
                const fileLabel = file?.name ? `«${file.name}»` : 'Файл'
                toast({
                  content: `${fileLabel}: ${humanizeUploadError(error)}`,
                  type: 'error'
                })
              }
            }
          } catch (error) {
            console.error('Ошибка при загрузке изображений в галерею:', error)
            toast({
              content: humanizeUploadError(error),
              type: 'error'
            })
          } finally {
            this.isUploading = false
            wrapper.removeChild(loader)
            button.disabled = false
            button.textContent = 'Добавить изображения'
          }
        }
      }
      
      wrapper.appendChild(button)
      wrapper.appendChild(input)
      wrapper.appendChild(gallery)
      
      this.renderGallery(gallery)
      
      return wrapper
    }

    renderGallery(container: HTMLElement) {
      if (!container || !this.data?.images) return
      
      container.innerHTML = ''
      
      if (!Array.isArray(this.data.images)) {
        this.data.images = []
      }
      
      // Добавляем обработчик клика вне панели
      const closePanels = (e: MouseEvent) => {
        const target = e.target as HTMLElement
        if (!target.closest('.gallery-settings-panel') && !target.closest('.gallery-settings')) {
          const openPanels = container.querySelectorAll('.gallery-settings-panel')
          openPanels.forEach(panel => panel.remove())
          document.removeEventListener('click', closePanels)
        }
      }
      
      this.data.images.forEach((image: { url: string; alt: string; title: string }, index: number) => {
        const imgWrapper = document.createElement('div')
        imgWrapper.classList.add('gallery-item')
        imgWrapper.draggable = true
        imgWrapper.dataset.index = index.toString()
        
        // Добавляем обработчики drag and drop
        imgWrapper.ondragstart = (e) => {
          if (e.dataTransfer) {
            e.dataTransfer.setData('application/x-gallery-item', index.toString())
            e.dataTransfer.effectAllowed = 'move'
            
            // Создаем миниатюру для перетаскивания
            const dragImage = document.createElement('div')
            dragImage.style.position = 'absolute'
            dragImage.style.top = '-1000px'
            dragImage.style.width = '100px'
            dragImage.style.height = '100px'
            dragImage.style.background = `url(${image.url}) center/cover`
            dragImage.style.borderRadius = '4px'
            dragImage.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.2)'
            document.body.appendChild(dragImage)
            
            // Устанавливаем смещение курсора относительно миниатюры
            e.dataTransfer.setDragImage(dragImage, 50, 50)
            
            setTimeout(() => {
              document.body.removeChild(dragImage)
            }, 0)
          }
          imgWrapper.classList.add('dragging')
        }
        
        imgWrapper.ondragend = () => {
          imgWrapper.classList.remove('dragging')
        }
        
        imgWrapper.ondragover = (e) => {
          e.preventDefault()
          if (e.dataTransfer) {
            e.dataTransfer.dropEffect = 'move'
          }
          const draggingItem = container.querySelector('.dragging')
          if (draggingItem !== imgWrapper) {
            imgWrapper.classList.add('drag-over')
          }
        }
        
        imgWrapper.ondragleave = () => {
          imgWrapper.classList.remove('drag-over')
        }
        
        imgWrapper.ondrop = (e) => {
          e.preventDefault()
          imgWrapper.classList.remove('drag-over')
          
          const fromIndex = e.dataTransfer ? parseInt(e.dataTransfer.getData('application/x-gallery-item') || '0') : 0
          const toIndex = parseInt(imgWrapper.dataset.index || '0')
          
          if (fromIndex !== toIndex) {
            const images = [...this.data.images]
            const [movedImage] = images.splice(fromIndex, 1)
            images.splice(toIndex, 0, movedImage)
            this.data.images = images
            this.renderGallery(container)
          }
        }
        
        const img = document.createElement('img')
        img.src = image.url
        img.alt = image.alt
        img.title = image.title
        
        // Добавляем обработчик загрузки изображения
        img.onload = () => {
          imgWrapper.classList.add('loaded')
        }
        
        // Добавляем обработчик ошибки загрузки
        img.onerror = () => {
          console.error('Ошибка загрузки изображения:', image.url)
          imgWrapper.classList.add('error')
        }
        
        const removeBtn = document.createElement('button')
        removeBtn.classList.add('gallery-remove')
        removeBtn.textContent = '×'
        removeBtn.onclick = (e) => {
          e.preventDefault()
          e.stopPropagation()
          if (Array.isArray(this.data.images)) {
            this.data.images.splice(index, 1)
            this.renderGallery(container)
          }
        }
        
        const settingsBtn = document.createElement('button')
        settingsBtn.classList.add('gallery-settings')
        settingsBtn.textContent = '⚙️'
        settingsBtn.onclick = (e) => {
          e.preventDefault()
          e.stopPropagation()
          
          // Проверяем, есть ли уже открытая панель для этого изображения
          const existingPanel = imgWrapper.querySelector('.gallery-settings-panel')
          if (existingPanel) {
            existingPanel.remove()
            return
          }
          
          // Закрываем все открытые панели
          const openPanels = container.querySelectorAll('.gallery-settings-panel')
          openPanels.forEach(panel => panel.remove())
          
          const altInput = document.createElement('input')
          altInput.type = 'text'
          altInput.classList.add('gallery-input')
          altInput.placeholder = 'Alt текст'
          altInput.value = image.alt
          altInput.onchange = (e) => {
            e.preventDefault()
            e.stopPropagation()
            image.alt = altInput.value
            img.alt = altInput.value
          }
          
          const titleInput = document.createElement('input')
          titleInput.type = 'text'
          titleInput.classList.add('gallery-input')
          titleInput.placeholder = 'Title текст'
          titleInput.value = image.title
          titleInput.onchange = (e) => {
            e.preventDefault()
            e.stopPropagation()
            image.title = titleInput.value
            img.title = titleInput.value
          }
          
          const settingsPanel = document.createElement('div')
          settingsPanel.classList.add('gallery-settings-panel')
          settingsPanel.onclick = (e) => {
            e.preventDefault()
            e.stopPropagation()
          }
          settingsPanel.appendChild(altInput)
          settingsPanel.appendChild(titleInput)
          
          imgWrapper.appendChild(settingsPanel)
          
          // Добавляем обработчик клика вне панели
          document.addEventListener('click', closePanels)
        }
        
        imgWrapper.appendChild(img)
        imgWrapper.appendChild(removeBtn)
        imgWrapper.appendChild(settingsBtn)
        container.appendChild(imgWrapper)
      })
    }

    save() {
      return {
        images: Array.isArray(this.data?.images) ? this.data.images : []
      }
    }
  }

  // Кастомный плагин для изображений
  class CustomImageTool {
    private api: any;
    private data: { file: { url: string; alt: string; title: string }; caption: string };
    private config: any;
    private isUploading: boolean = false;
    private shouldAutoOpenPicker: boolean = false;

    static get toolbox() {
      return {
        title: 'Изображение',
        icon: `<img src="${icons.image}" width="16" height="16" />`
      }
    }

    constructor({ data, config, api }: { data?: { file: { url: string; alt: string; title: string }; caption: string }, config?: any, api?: any }) {
      this.api = api
      this.data = {
        file: {
          url: data?.file?.url || '',
          alt: data?.file?.alt || '',
          title: data?.file?.title || ''
        },
        caption: data?.caption || ''
      }
      this.config = config || {}
      this.shouldAutoOpenPicker = !Boolean(data?.file?.url)
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('image-tool__wrapper')
      
      const imageWrapper = document.createElement('div')
      imageWrapper.classList.add('image-tool__image-wrapper')
      
      const image = document.createElement('img')
      image.src = this.data.file.url
      image.alt = this.data.file.alt
      image.title = this.data.file.title
      
      let previewControl: HTMLDivElement | null = null
      if (showPostSettings) {
        previewControl = document.createElement('div')
        previewControl.classList.add('image-tool__preview-control')

        // Показываем контрол только если изображение уже загружено
        if (!this.data.file.url) {
          previewControl.style.display = 'none'
        }

        const isPreview = Boolean(this.data.file.url && this.data.file.url === previewImage)
        previewControl.classList.toggle('active', isPreview)
        previewControl.innerHTML = `
          <span class="preview-star">${isPreview ? '★' : '☆'}</span>
          <span class="preview-text">Вывести в ленте</span>
        `
        previewControl.onclick = (e) => {
          e.preventDefault()
          e.stopPropagation()
          if (this.data.file.url) {
            // Если выбираем новое изображение, сначала очищаем все остальные
            if (this.data.file.url !== previewImage) {
              // Находим все контролы в редакторе
              const allControls = document.querySelectorAll('.image-tool__preview-control')
              allControls.forEach(control => {
                control.classList.remove('active')
                const star = control.querySelector('.preview-star')
                if (star) {
                  star.textContent = '☆'
                }
              })
            }

            // Устанавливаем новое значение previewImage
            previewImage = this.data.file.url === previewImage ? '' : this.data.file.url

            // Обновляем текущий контрол
            previewControl?.classList.toggle('active', Boolean(this.data.file.url === previewImage))
            const star = previewControl?.querySelector('.preview-star')
            if (star) {
              star.textContent = this.data.file.url === previewImage ? '★' : '☆'
            }

            editor.save().then(updateMarkdown)
          }
        }
      }
      
      const caption = document.createElement('textarea')
      caption.classList.add('image-tool__caption')
      caption.placeholder = 'Введите подпись к изображению...'
      caption.value = this.data.caption
      caption.onchange = () => {
        this.data.caption = caption.value
      }
      
      const altInput = document.createElement('input')
      altInput.type = 'text'
      altInput.classList.add('image-tool__alt')
      altInput.placeholder = 'Описание изображения для поисковиков (ALT)'
      altInput.value = this.data.file.alt
      altInput.onchange = () => {
        this.data.file.alt = altInput.value
        image.alt = altInput.value
      }
      
      const titleInput = document.createElement('input')
      titleInput.type = 'text'
      titleInput.classList.add('image-tool__title')
      titleInput.placeholder = 'Подпись к изображению'
      titleInput.value = this.data.file.title
      titleInput.onchange = () => {
        this.data.file.title = titleInput.value
        image.title = titleInput.value
      }
      
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = 'image/*'
      input.style.display = 'none'
      
      const button = document.createElement('button')
      button.classList.add('image-tool__button')
      button.textContent = 'Загрузить изображение'
      button.onclick = (e) => {
        e.preventDefault()
        e.stopPropagation()
        input.click()
      }
      
      const loader = document.createElement('div')
      loader.classList.add('image-tool__loader')
      loader.innerHTML = `
        <div class="image-tool__loader-spinner"></div>
        <div class="image-tool__loader-text">Загрузка изображения...</div>
      `
      
      input.onchange = async (e: Event) => {
        const target = e.target as HTMLInputElement
        if (!target.files) return
        
        const file = target.files[0]
        if (file) {
          try {
            this.isUploading = true
            wrapper.appendChild(loader)
            button.disabled = true
            button.textContent = 'Загрузка...'
            
            const uploaded = await uploadEditorImage(file)
            if (uploaded?.url) {
              this.data.file.url = uploaded.useWebp
                ? `${uploaded.url}?format=webp`
                : uploaded.url
              image.src = this.data.file.url
              
              // Показываем контрол "Вывести в ленте" после успешной загрузки
              if (previewControl) {
                previewControl.style.display = 'flex'

                // Обновляем состояние контрола
                const isNowPreview = Boolean(this.data.file.url === previewImage)
                previewControl.classList.toggle('active', isNowPreview)
                const star = previewControl.querySelector('.preview-star')
                if (star) {
                  star.textContent = isNowPreview ? '★' : '☆'
                }
              }
            }
          } catch (error) {
            console.error('Ошибка при загрузке изображения:', error)
            toast({
              content: humanizeUploadError(error),
              type: 'error'
            })
          } finally {
            this.isUploading = false
            wrapper.removeChild(loader)
            button.disabled = false
            button.textContent = 'Загрузить изображение'
          }
        }
      }
      
      imageWrapper.appendChild(image)
      if (previewControl) {
        imageWrapper.appendChild(previewControl)
      }
      wrapper.appendChild(imageWrapper)
      
      wrapper.appendChild(button)
      wrapper.appendChild(input)
      
      wrapper.appendChild(caption)
      wrapper.appendChild(altInput)
      wrapper.appendChild(titleInput)

      // When a new image block is added from the toolbox, immediately open
      // the file picker to avoid an extra click on the upload button.
      if (this.shouldAutoOpenPicker && !this.data.file.url) {
        this.shouldAutoOpenPicker = false
        button.textContent = 'Выберите изображение'
        try {
          input.click()
        } catch (error) {
          console.warn('Не удалось автоматически открыть выбор файла:', error)
        }
      }
      
      return wrapper
    }

    save() {
      return this.data
    }
  }

  class MapTool {
    private data: { lat: number | null; lng: number | null; zoom: number; raw: string }

    static get toolbox() {
      return {
        title: 'Карта',
        icon: `<img src="${icons.map}" width="16" height="16" />`,
      }
    }

    constructor({ data }: { data?: { lat?: unknown; lng?: unknown; zoom?: unknown; raw?: unknown } }) {
      const lat = typeof data?.lat === 'number' && Number.isFinite(data.lat) ? data.lat : null
      const lng = typeof data?.lng === 'number' && Number.isFinite(data.lng) ? data.lng : null
      const parsedFromRaw =
        typeof data?.raw === 'string' && data.raw.trim() ? parseGpsCoordinates(data.raw) : null

      this.data = {
        lat: parsedFromRaw?.lat ?? lat,
        lng: parsedFromRaw?.lng ?? lng,
        zoom: normalizeOpenStreetMapZoom(data?.zoom, 14),
        raw:
          typeof data?.raw === 'string' && data.raw.trim()
            ? data.raw.trim()
            : lat !== null && lng !== null
              ? `${lat}, ${lng}`
              : '',
      }
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('map-tool')

      const controls = document.createElement('div')
      controls.classList.add('map-tool__controls')

      const gpsLabel = document.createElement('label')
      gpsLabel.classList.add('map-tool__label')
      gpsLabel.textContent = 'GPS координаты (широта, долгота)'

      const gpsInput = document.createElement('input')
      gpsInput.type = 'text'
      gpsInput.classList.add('map-tool__input')
      gpsInput.placeholder = 'Например: 55.7558, 37.6176'
      gpsInput.value = this.data.raw

      const zoomRow = document.createElement('div')
      zoomRow.classList.add('map-tool__zoom-row')

      const zoomLabel = document.createElement('label')
      zoomLabel.classList.add('map-tool__label')
      zoomLabel.textContent = 'Масштаб'

      const zoomInput = document.createElement('input')
      zoomInput.type = 'number'
      zoomInput.min = '1'
      zoomInput.max = '19'
      zoomInput.step = '1'
      zoomInput.classList.add('map-tool__zoom')
      zoomInput.value = String(this.data.zoom)

      zoomRow.appendChild(zoomLabel)
      zoomRow.appendChild(zoomInput)

      const hint = document.createElement('p')
      hint.classList.add('map-tool__hint')

      const preview = document.createElement('div')
      preview.classList.add('map-tool__preview')

      const previewFrame = document.createElement('iframe')
      previewFrame.classList.add('map-tool__frame')
      previewFrame.loading = 'lazy'
      previewFrame.referrerPolicy = 'no-referrer-when-downgrade'
      previewFrame.setAttribute('title', 'Предпросмотр карты')
      previewFrame.setAttribute('frameborder', '0')
      previewFrame.setAttribute('allowfullscreen', '')

      preview.appendChild(previewFrame)

      const updatePreview = () => {
        const parsed = parseGpsCoordinates(gpsInput.value)
        const zoom = normalizeOpenStreetMapZoom(zoomInput.value, 14)
        zoomInput.value = String(zoom)
        this.data.zoom = zoom
        this.data.raw = gpsInput.value.trim()

        if (!parsed) {
          this.data.lat = null
          this.data.lng = null
          preview.classList.remove('is-ready')
          previewFrame.removeAttribute('src')
          hint.textContent = 'Укажите координаты в формате "широта, долгота".'
          return
        }

        this.data.lat = parsed.lat
        this.data.lng = parsed.lng
        if (!this.data.raw) {
          this.data.raw = `${parsed.lat}, ${parsed.lng}`
        }
        previewFrame.src = buildOpenStreetMapEmbedUrl(parsed.lat, parsed.lng, zoom)
        preview.classList.add('is-ready')
        hint.textContent = 'Карта будет показана в посте. Нажатие по карте откроет увеличенный вид.'
      }

      gpsInput.addEventListener('input', updatePreview)
      zoomInput.addEventListener('input', updatePreview)
      zoomInput.addEventListener('blur', updatePreview)

      controls.appendChild(gpsLabel)
      controls.appendChild(gpsInput)
      controls.appendChild(zoomRow)
      controls.appendChild(hint)

      wrapper.appendChild(controls)
      wrapper.appendChild(preview)

      updatePreview()
      return wrapper
    }

    save() {
      return {
        lat: this.data.lat,
        lng: this.data.lng,
        zoom: normalizeOpenStreetMapZoom(this.data.zoom, 14),
        raw: this.data.raw,
      }
    }
  }

  class MovieTimeTool {
    private data: {
      time: string
      title: string
      note: string
    }

    static get toolbox() {
      return {
        title: 'Время в фильме',
        icon: `<img src="${icons.clock}" width="16" height="16" />`,
      }
    }

    constructor({ data }: { data?: { time?: unknown; title?: unknown; note?: unknown } }) {
      this.data = {
        time: typeof data?.time === 'string' ? data.time.trim() : '',
        title: typeof data?.title === 'string' ? data.title.trim() : '',
        note: typeof data?.note === 'string' ? data.note.trim() : '',
      }
    }

    private parseTimeToSeconds(value: string): number | null {
      const raw = value.trim()
      if (!raw) return null

      if (/^\d+$/.test(raw)) {
        const totalSeconds = Number(raw)
        if (!Number.isFinite(totalSeconds) || totalSeconds < 0) return null
        return Math.floor(totalSeconds)
      }

      const parts = raw.split(':').map((part) => part.trim())
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

    private formatTimeFromSeconds(totalSeconds: number, hasHours: boolean): string {
      const safeSeconds = Math.max(0, Math.floor(totalSeconds))
      const hours = Math.floor(safeSeconds / 3600)
      const minutes = Math.floor((safeSeconds % 3600) / 60)
      const seconds = safeSeconds % 60
      if (hasHours || hours > 0) {
        return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
      }
      return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
    }

    private normalizeTimeValue(value: string): string {
      const raw = value.trim()
      if (!raw) return ''
      const totalSeconds = this.parseTimeToSeconds(raw)
      if (totalSeconds === null) return raw
      const hasHoursInInput = raw.split(':').length === 3
      return this.formatTimeFromSeconds(totalSeconds, hasHoursInInput || totalSeconds >= 3600)
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('movie-time-tool')

      const title = document.createElement('div')
      title.classList.add('movie-time-tool__title')
      title.textContent = 'Время в фильме'

      const subtitle = document.createElement('div')
      subtitle.classList.add('movie-time-tool__subtitle')
      subtitle.textContent = 'Укажите таймкод и короткий комментарий автора.'

      const grid = document.createElement('div')
      grid.classList.add('movie-time-tool__grid')

      const timeInput = document.createElement('input')
      timeInput.type = 'text'
      timeInput.classList.add('movie-time-tool__input')
      timeInput.placeholder = 'Таймкод: 01:23:45 или 12:40'
      timeInput.value = this.data.time

      const titleInput = document.createElement('input')
      titleInput.type = 'text'
      titleInput.classList.add('movie-time-tool__input')
      titleInput.placeholder = 'Название сцены (необязательно)'
      titleInput.value = this.data.title

      const noteInput = document.createElement('textarea')
      noteInput.classList.add('movie-time-tool__textarea')
      noteInput.rows = 3
      noteInput.placeholder = 'Что важно в этом моменте?'
      noteInput.value = this.data.note

      const preview = document.createElement('div')
      preview.classList.add('movie-time-tool__preview')

      const updatePreview = () => {
        this.data.time = timeInput.value.trim()
        this.data.title = titleInput.value.trim()
        this.data.note = noteInput.value.trim()
        const normalizedTime = this.normalizeTimeValue(this.data.time)
        const previewTitle = this.data.title || 'Ключевой момент'
        if (!normalizedTime) {
          preview.textContent = 'Этот блок появится в тексте после заполнения таймкода.'
          return
        }
        preview.textContent = `${normalizedTime} • ${previewTitle}`
      }

      timeInput.addEventListener('input', updatePreview)
      titleInput.addEventListener('input', updatePreview)
      noteInput.addEventListener('input', updatePreview)
      timeInput.addEventListener('blur', () => {
        const normalizedTime = this.normalizeTimeValue(timeInput.value)
        timeInput.value = normalizedTime
        this.data.time = normalizedTime
        updatePreview()
      })

      grid.appendChild(timeInput)
      grid.appendChild(titleInput)

      wrapper.appendChild(title)
      wrapper.appendChild(subtitle)
      wrapper.appendChild(grid)
      wrapper.appendChild(noteInput)
      wrapper.appendChild(preview)

      updatePreview()
      return wrapper
    }

    save() {
      const time = this.normalizeTimeValue(this.data.time)
      return {
        time,
        title: this.data.title.trim(),
        note: this.data.note.trim(),
      }
    }
  }

  class MovieCardTool {
    private data: {
      use_template: boolean
    }

    static get toolbox() {
      return {
        title: 'Карточка фильма',
        icon: `<img src="${icons.movieCard}" width="16" height="16" />`,
      }
    }

    constructor({ data }: { data?: { use_template?: unknown } }) {
      this.data = {
        use_template:
          typeof data?.use_template === 'boolean' ? data.use_template : true,
      }
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('movie-card-tool')

      const title = document.createElement('div')
      title.classList.add('movie-card-tool__title')
      title.textContent = 'Карточка фильма'

      const subtitle = document.createElement('p')
      subtitle.classList.add('movie-card-tool__subtitle')
      subtitle.textContent =
        postTemplateType === 'movie_review'
          ? 'Блок покажет карточку по данным шаблона «Кинообзор» в тексте и в превью ленты.'
          : 'Для корректной карточки выберите шаблон «Кинообзор».'

      const preview = document.createElement('div')
      preview.classList.add('movie-card-tool__preview')
      preview.textContent =
        postTemplateType === 'movie_review'
          ? 'Будут использованы поля: постер, название, жанр, тип, премьера, где смотреть, IMDb.'
          : 'Карточка сейчас недоступна для выбранного шаблона.'

      wrapper.appendChild(title)
      wrapper.appendChild(subtitle)
      wrapper.appendChild(preview)

      return wrapper
    }

    save() {
      return {
        use_template: this.data.use_template,
      }
    }
  }

  class SpoilerTool {
    private api: any
    private block: any
    private data: {
      marker: 'start' | 'end'
      title: string
    }
    private legacyContent: string
    private shouldAutoInsertEndMarker: boolean

    static get toolbox() {
      return {
        title: 'Спойлер',
        icon: `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M2 8C2 8 4.2 4.5 8 4.5C11.8 4.5 14 8 14 8C14 8 11.8 11.5 8 11.5C4.2 11.5 2 8 2 8Z" stroke="currentColor" stroke-width="1.3"/><circle cx="8" cy="8" r="1.8" stroke="currentColor" stroke-width="1.3"/><path d="M3 13L13 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg>`,
      }
    }

    constructor({
      data,
      api,
      block,
    }: {
      data?: { marker?: unknown; mode?: unknown; title?: unknown; content?: unknown }
      api?: any
      block?: any
    }) {
      this.api = api
      this.block = block
      const markerCandidate =
        typeof data?.marker === 'string'
          ? data.marker.trim().toLowerCase()
          : typeof data?.mode === 'string'
            ? data.mode.trim().toLowerCase()
            : ''
      const marker: 'start' | 'end' =
        markerCandidate === 'end' || markerCandidate === 'close' ? 'end' : 'start'
      this.data = {
        marker,
        title: typeof data?.title === 'string' && data.title.trim() ? data.title.trim() : 'Спойлер',
      }
      this.legacyContent = typeof data?.content === 'string' ? data.content.trim() : ''
      const hasPersistedData = Boolean(data && Object.keys(data).length > 0)
      this.shouldAutoInsertEndMarker =
        !hasPersistedData && this.legacyContent.length === 0 && marker === 'start'
    }

    private findCurrentBlockIndex(): number {
      if (!this.api?.blocks) return -1
      if (typeof this.api.blocks.getCurrentBlockIndex === 'function') {
        const currentIndex = Number(this.api.blocks.getCurrentBlockIndex())
        if (Number.isFinite(currentIndex) && currentIndex >= 0) {
          return currentIndex
        }
      }
      const currentId = this.block?.id
      const count = Number(this.api.blocks.getBlocksCount?.() || 0)
      for (let index = 0; index < count; index += 1) {
        const candidate = this.api.blocks.getBlockByIndex(index)
        if (candidate?.id && currentId && candidate.id === currentId) {
          return index
        }
      }
      return -1
    }

    private ensurePairedEndMarkerInserted() {
      if (!this.shouldAutoInsertEndMarker) return
      if (!this.api?.blocks || typeof this.api.blocks.insert !== 'function') return
      this.shouldAutoInsertEndMarker = false

      setTimeout(() => {
        try {
          const currentIndex = this.findCurrentBlockIndex()
          if (currentIndex < 0) return
          const nextBlock = this.api.blocks.getBlockByIndex(currentIndex + 1)
          const nextData =
            nextBlock && typeof nextBlock.data === 'object' && nextBlock.data ? nextBlock.data : {}
          const nextMarker =
            typeof nextData.marker === 'string' ? nextData.marker.trim().toLowerCase() : ''
          if (nextBlock?.name === 'spoiler' && (nextMarker === 'end' || nextMarker === 'close')) {
            return
          }
          this.api.blocks.insert(
            'spoiler',
            {
              marker: 'end',
              title: this.data.title,
            },
            undefined,
            currentIndex + 1,
            false
          )
        } catch (error) {
          console.error('Failed to insert closing spoiler marker', error)
        }
      }, 0)
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('spoiler-marker-tool')
      wrapper.classList.add(
        this.data.marker === 'end' ? 'spoiler-marker-tool--end' : 'spoiler-marker-tool--start'
      )

      const title = document.createElement('div')
      title.classList.add('spoiler-marker-tool__title')
      title.textContent = this.data.marker === 'end' ? 'Конец спойлера' : 'Начало спойлера'

      const subtitle = document.createElement('p')
      subtitle.classList.add('spoiler-marker-tool__subtitle')
      subtitle.textContent =
        this.data.marker === 'end'
          ? 'Закрывает спойлер. Все блоки выше до «Начало спойлера» будут скрыты до клика.'
          : 'Открывает спойлер. Все следующие блоки до «Конец спойлера» будут скрыты до клика.'

      const preview = document.createElement('div')
      preview.classList.add('spoiler-marker-tool__preview')

      if (this.legacyContent) {
        wrapper.classList.add('spoiler-marker-tool--legacy')
        title.textContent = 'Спойлер (старый формат)'
        subtitle.textContent =
          'Этот блок создан в старом формате с текстом внутри. При сохранении он останется без изменений.'
        preview.textContent = 'Скрытый текст сохранится как есть.'
      } else {
        preview.textContent =
          this.data.marker === 'end'
            ? 'Закрывающий маркер.'
            : 'После вставки блока автоматически добавляется закрывающий маркер.'
        if (this.data.marker === 'start') {
          this.ensurePairedEndMarkerInserted()
        }
      }

      wrapper.appendChild(title)
      wrapper.appendChild(subtitle)
      wrapper.appendChild(preview)
      return wrapper
    }

    save() {
      if (this.legacyContent) {
        return {
          title: this.data.title.trim() || 'Спойлер',
          content: this.legacyContent,
        }
      }
      return {
        marker: this.data.marker,
        title: this.data.title.trim() || 'Спойлер',
      }
    }
  }

  class MusicTool {
    private data: {
      url: string
      provider: string
      caption: string
    }

    static get toolbox() {
      return {
        title: 'Музыка',
        icon: `<img src="${icons.music}" width="16" height="16" />`,
      }
    }

    constructor({
      data,
    }: {
      data?: { url?: unknown; provider?: unknown; caption?: unknown }
    }) {
      this.data = {
        url: typeof data?.url === 'string' ? data.url.trim() : '',
        provider:
          typeof data?.provider === 'string' ? this.normalizeProvider(data.provider) : 'auto',
        caption: typeof data?.caption === 'string' ? data.caption.trim() : '',
      }
    }

    private normalizeProvider(value: string): string {
      const normalized = String(value || '').trim().toLowerCase()
      if (normalized === 'spotify') return 'spotify'
      if (normalized === 'yandex_music') return 'yandex_music'
      if (normalized === 'soundcloud') return 'soundcloud'
      return 'auto'
    }

    private inferProviderFromUrl(value: string): string {
      const raw = value.trim().toLowerCase()
      if (!raw) return 'unknown'
      if (raw.includes('open.spotify.com/track/')) return 'spotify'
      if (raw.includes('music.yandex.ru/') || raw.includes('music.yandex.com/')) {
        return 'yandex_music'
      }
      if (raw.includes('soundcloud.com/') || raw.includes('snd.sc/')) return 'soundcloud'
      return 'unknown'
    }

    private providerLabel(value: string): string {
      if (value === 'spotify') return 'Spotify'
      if (value === 'yandex_music') return 'Яндекс Музыка'
      if (value === 'soundcloud') return 'SoundCloud'
      return 'не определена'
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('music-tool')

      const title = document.createElement('div')
      title.classList.add('music-tool__title')
      title.textContent = 'Музыка'

      const subtitle = document.createElement('p')
      subtitle.classList.add('music-tool__subtitle')
      subtitle.textContent =
        'Вставьте ссылку на трек. Поддержка: Spotify, Яндекс Музыка, SoundCloud.'

      const providerLabel = document.createElement('label')
      providerLabel.classList.add('music-tool__label')
      providerLabel.textContent = 'Площадка'

      const providerSelect = document.createElement('select')
      providerSelect.classList.add('music-tool__select')
      const providerOptions = [
        { value: 'auto', label: 'Определить автоматически' },
        { value: 'spotify', label: 'Spotify' },
        { value: 'yandex_music', label: 'Яндекс Музыка' },
        { value: 'soundcloud', label: 'SoundCloud' },
      ]
      providerOptions.forEach((option) => {
        const optionElement = document.createElement('option')
        optionElement.value = option.value
        optionElement.textContent = option.label
        providerSelect.appendChild(optionElement)
      })
      providerSelect.value = this.normalizeProvider(this.data.provider)

      const urlInput = document.createElement('input')
      urlInput.type = 'url'
      urlInput.classList.add('music-tool__input')
      urlInput.placeholder = 'https://open.spotify.com/track/...'
      urlInput.value = this.data.url

      const captionInput = document.createElement('textarea')
      captionInput.classList.add('music-tool__textarea')
      captionInput.rows = 2
      captionInput.placeholder = 'Подпись к треку (необязательно)'
      captionInput.value = this.data.caption

      const preview = document.createElement('div')
      preview.classList.add('music-tool__preview')

      const updatePreview = () => {
        this.data.url = urlInput.value.trim()
        this.data.provider = this.normalizeProvider(providerSelect.value)
        this.data.caption = captionInput.value.trim()

        if (!this.data.url) {
          preview.textContent = 'После вставки ссылки в посте появится встроенный плеер.'
          return
        }

        const detectedProvider = this.inferProviderFromUrl(this.data.url)
        const effectiveProvider =
          this.data.provider === 'auto' ? detectedProvider : this.data.provider
        const label = this.providerLabel(effectiveProvider)

        if (effectiveProvider === 'unknown') {
          preview.textContent =
            'Ссылка сохранена. Если плеер не отобразится, используйте ссылку Spotify, Яндекс Музыки или SoundCloud.'
          return
        }

        preview.textContent = `Плеер будет показан через ${label}.`
      }

      providerSelect.addEventListener('change', updatePreview)
      urlInput.addEventListener('input', updatePreview)
      captionInput.addEventListener('input', updatePreview)

      wrapper.appendChild(title)
      wrapper.appendChild(subtitle)
      wrapper.appendChild(providerLabel)
      wrapper.appendChild(providerSelect)
      wrapper.appendChild(urlInput)
      wrapper.appendChild(captionInput)
      wrapper.appendChild(preview)

      updatePreview()
      return wrapper
    }

    save() {
      return {
        url: this.data.url.trim(),
        provider: this.normalizeProvider(this.data.provider),
        caption: this.data.caption.trim(),
      }
    }
  }

  class ImageCompareTool {
    private data: {
      before: { url: string; alt: string; title: string }
      after: { url: string; alt: string; title: string }
      caption: string
      position: number
    }

    static get toolbox() {
      return {
        title: 'Сравнение',
        icon: `<img src="${icons.imageCompare}" width="16" height="16" />`,
      }
    }

    constructor({
      data,
    }: {
      data?: {
        before?: { url?: unknown; alt?: unknown; title?: unknown }
        after?: { url?: unknown; alt?: unknown; title?: unknown }
        caption?: unknown
        position?: unknown
      }
    }) {
      const normalizeImage = (value: { url?: unknown; alt?: unknown; title?: unknown } | undefined) => ({
        url: typeof value?.url === 'string' ? value.url : '',
        alt: typeof value?.alt === 'string' ? value.alt : '',
        title: typeof value?.title === 'string' ? value.title : '',
      })

      this.data = {
        before: normalizeImage(data?.before),
        after: normalizeImage(data?.after),
        caption: typeof data?.caption === 'string' ? data.caption : '',
        position: this.normalizePosition(data?.position),
      }
    }

    private normalizePosition(value: unknown): number {
      const parsed = Number(value)
      if (!Number.isFinite(parsed)) return 50
      return Math.min(95, Math.max(5, Math.round(parsed)))
    }

    render() {
      const wrapper = document.createElement('div')
      wrapper.classList.add('image-compare-tool')

      const hint = document.createElement('p')
      hint.classList.add('image-compare-tool__hint')
      hint.textContent = 'Загрузите левое и правое изображение, затем перетащите разделитель.'

      const controls = document.createElement('div')
      controls.classList.add('image-compare-tool__controls')

      const preview = document.createElement('div')
      preview.classList.add('image-compare-tool__preview')

      const beforeImage = document.createElement('img')
      beforeImage.classList.add('image-compare-tool__image', 'image-compare-tool__image--before')

      const overlay = document.createElement('div')
      overlay.classList.add('image-compare-tool__overlay')

      const afterImage = document.createElement('img')
      afterImage.classList.add('image-compare-tool__image', 'image-compare-tool__image--after')
      overlay.appendChild(afterImage)

      const divider = document.createElement('div')
      divider.classList.add('image-compare-tool__divider')
      const knob = document.createElement('span')
      knob.classList.add('image-compare-tool__knob')
      divider.appendChild(knob)

      const placeholder = document.createElement('div')
      placeholder.classList.add('image-compare-tool__placeholder')

      preview.appendChild(beforeImage)
      preview.appendChild(overlay)
      preview.appendChild(divider)
      preview.appendChild(placeholder)

      const caption = document.createElement('textarea')
      caption.classList.add('image-compare-tool__caption')
      caption.placeholder = 'Подпись к сравнению (необязательно)'
      caption.value = this.data.caption
      caption.addEventListener('input', () => {
        this.data.caption = caption.value
      })

      const applyPosition = (value: unknown) => {
        const position = this.normalizePosition(value)
        this.data.position = position
        const rightInset = 100 - position
        const clipRule = `inset(0 ${rightInset}% 0 0)`
        overlay.style.clipPath = clipRule
        ;(overlay.style as CSSStyleDeclaration & { webkitClipPath?: string }).webkitClipPath = clipRule
        divider.style.left = `${position}%`
      }

      const updateFromClientX = (clientX: number) => {
        const rect = preview.getBoundingClientRect()
        if (!rect.width) return
        const next = ((clientX - rect.left) / rect.width) * 100
        applyPosition(next)
      }

      let isDragging = false

      const onPointerMove = (event: PointerEvent) => {
        if (!isDragging) return
        event.preventDefault()
        updateFromClientX(event.clientX)
      }

      const stopDrag = () => {
        if (!isDragging) return
        isDragging = false
        preview.classList.remove('is-dragging')
        window.removeEventListener('pointermove', onPointerMove)
        window.removeEventListener('pointerup', stopDrag)
        window.removeEventListener('pointercancel', stopDrag)
      }

      const startDrag = (event: PointerEvent) => {
        if (event.button !== 0 && event.pointerType !== 'touch') return
        event.preventDefault()
        isDragging = true
        preview.classList.add('is-dragging')
        updateFromClientX(event.clientX)
        window.addEventListener('pointermove', onPointerMove)
        window.addEventListener('pointerup', stopDrag)
        window.addEventListener('pointercancel', stopDrag)
      }

      preview.addEventListener('pointerdown', startDrag)

      const updatePreview = () => {
        const beforeUrl = this.data.before.url
        const afterUrl = this.data.after.url

        if (beforeUrl) {
          beforeImage.src = beforeUrl
          beforeImage.style.display = 'block'
        } else {
          beforeImage.removeAttribute('src')
          beforeImage.style.display = 'none'
        }

        if (afterUrl) {
          afterImage.src = afterUrl
          afterImage.style.display = 'block'
        } else {
          afterImage.removeAttribute('src')
          afterImage.style.display = 'none'
        }

        applyPosition(this.data.position)

        const ready = Boolean(beforeUrl && afterUrl)
        preview.classList.toggle('is-ready', ready)
        if (ready) {
          placeholder.style.display = 'none'
        } else {
          placeholder.style.display = 'flex'
          if (!beforeUrl && !afterUrl) {
            placeholder.textContent = 'Загрузите два изображения для сравнения'
          } else if (!beforeUrl) {
            placeholder.textContent = 'Загрузите левое изображение'
          } else {
            placeholder.textContent = 'Загрузите правое изображение'
          }
        }
      }

      const createSideControls = (side: 'before' | 'after', label: string) => {
        const section = document.createElement('div')
        section.classList.add('image-compare-tool__side')

        const title = document.createElement('p')
        title.classList.add('image-compare-tool__side-title')
        title.textContent = label

        const button = document.createElement('button')
        button.type = 'button'
        button.classList.add('image-compare-tool__upload')

        const setButtonLabel = () => {
          button.textContent = this.data[side].url ? 'Заменить изображение' : 'Загрузить изображение'
        }

        const input = document.createElement('input')
        input.type = 'file'
        input.accept = 'image/*'
        input.style.display = 'none'

        button.onclick = (e) => {
          e.preventDefault()
          e.stopPropagation()
          input.click()
        }

        input.onchange = async (event: Event) => {
          const target = event.target as HTMLInputElement
          const file = target.files?.[0]
          if (!file) return

          button.disabled = true
          button.textContent = 'Загрузка...'

          try {
            const uploaded = await uploadEditorImage(file)
            if (uploaded?.url) {
              this.data[side].url = uploaded.useWebp ? `${uploaded.url}?format=webp` : uploaded.url
              updatePreview()
            }
          } catch (error) {
            console.error('Ошибка при загрузке изображения для сравнения:', error)
          } finally {
            button.disabled = false
            target.value = ''
            setButtonLabel()
          }
        }

        const altInput = document.createElement('input')
        altInput.type = 'text'
        altInput.classList.add('image-compare-tool__input')
        altInput.placeholder = 'ALT текст'
        altInput.value = this.data[side].alt
        altInput.addEventListener('input', () => {
          this.data[side].alt = altInput.value
        })

        const titleInput = document.createElement('input')
        titleInput.type = 'text'
        titleInput.classList.add('image-compare-tool__input')
        titleInput.placeholder = 'Title'
        titleInput.value = this.data[side].title
        titleInput.addEventListener('input', () => {
          this.data[side].title = titleInput.value
        })

        setButtonLabel()
        section.appendChild(title)
        section.appendChild(button)
        section.appendChild(input)
        section.appendChild(altInput)
        section.appendChild(titleInput)

        return section
      }

      controls.appendChild(createSideControls('before', 'Левое изображение (до)'))
      controls.appendChild(createSideControls('after', 'Правое изображение (после)'))

      updatePreview()

      wrapper.appendChild(hint)
      wrapper.appendChild(controls)
      wrapper.appendChild(preview)
      wrapper.appendChild(caption)

      return wrapper
    }

    save() {
      return {
        before: { ...this.data.before },
        after: { ...this.data.after },
        caption: this.data.caption,
        position: this.normalizePosition(this.data.position),
      }
    }
  }

  // Кастомный inline link tool с одинарными кавычками
  class CustomInlineLinkTool {
    private api: any;
    private button: HTMLButtonElement | null = null;
    private tag = 'A';
    private iconSVG = `<img src="${icons.link}" width="13" height="14" />`;

    static get isInline() {
      return true;
    }

    static get title() {
      return 'Ссылка';
    }

    get shortcut() {
      return 'CMD+K';
    }

    constructor({ api }: { api: any }) {
      this.api = api;
    }

    private async getAnchors(): Promise<string[]> {
      const anchors: string[] = [];
      const count = this.api.blocks.getBlocksCount();
      
      console.log('Blocks count:', count);
      
      for (let i = 0; i < count; i++) {
        const block = this.api.blocks.getBlockByIndex(i);
        const data = await block.save();
        
        // Проверяем разные возможные пути к якорю
        const anchorText = data?.tunes?.anchorInput?.text || 
                         data?.tunes?.customInput?.text || 
                         block?.tunes?.anchorInput?.text ||
                         block?.tunes?.customInput?.text;
                         
        if (anchorText) {
          anchors.push(anchorText);
        }
      }
      
      return anchors;
    }

    // Функция для проверки и добавления протокола
    private normalizeUrl(url: string): string {
      // Если это якорь, оставляем как есть
      if (url.startsWith('#')) {
        return url;
      }
      
      // Если уже есть протокол, оставляем как есть
      if (url.match(/^https?:\/\//)) {
        return url;
      }
      
      // Если это localhost или IP адрес, добавляем http
      if (url.match(/^(localhost|127\.0\.0\.1|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.|0\.0\.0\.0)/)) {
        return `http://${url}`;
      }
      
      // Во всех остальных случаях добавляем https
      return `https://${url}`;
    }

    render() {
      this.button = document.createElement('button');
      this.button.type = 'button';
      this.button.classList.add('ce-inline-tool');
      this.button.innerHTML = this.iconSVG;
      this.button.title = 'Ссылка';
      
      return this.button;
    }

    surround(range: Range) {
      console.log('🎯 CustomInlineLinkTool: surround вызван');
      console.log('📍 Range:', range);
      
      if (!range) return;

      const selectedText = range.extractContents();
      console.log('📝 Выделенный текст:', selectedText.textContent);
      
      const link = document.createElement(this.tag) as HTMLAnchorElement;
      
      if (selectedText.textContent?.trim()) {
        link.appendChild(selectedText);
        range.insertNode(link);
        console.log('✅ Ссылка создана:', link);
        
        // Показываем инлайн попап для редактирования
        this.showInlinePopup(link);
      } else {
        console.log('⚠️ Текст не выделен, вставляем как есть');
        // Если текст не выделен, вставляем текст ссылки
        range.insertNode(selectedText);
      }
    }

    // Функция для принудительного сохранения модели
    private triggerSave() {
      console.log('🔄 CustomInlineLinkTool: Попытка сохранения модели...');
      console.log('🔍 API объект:', this.api);
      console.log('🔍 API.saver:', this.api?.saver);
      
      if (this.api && this.api.saver) {
        // Используем встроенный механизм сохранения EditorJS
        console.log('✅ Вызываем api.saver.save()...');
        this.api.saver.save().then((data: any) => {
          console.log('💾 Данные сохранены через API:', data);
          updateMarkdown(data);
          console.log('📝 updateMarkdown вызван');
        }).catch((error: any) => {
          console.error('❌ Ошибка сохранения через API:', error);
        });
      } else {
        console.warn('⚠️ API.saver недоступен, пробуем альтернативный метод...');
        // Альтернативный способ через прямой вызов editor.save()
        if (typeof editor !== 'undefined' && editor && editor.save) {
          console.log('🔄 Используем прямой вызов editor.save()...');
          editor.save().then((data: any) => {
            console.log('💾 Данные сохранены через editor:', data);
            updateMarkdown(data);
            console.log('📝 updateMarkdown вызван (альтернативный путь)');
          }).catch((error: any) => {
            console.error('❌ Ошибка сохранения через editor:', error);
          });
        } else {
          console.error('❌ Ни API.saver, ни editor.save() не доступны');
        }
      }
    }

    // Функция для извлечения якоря из полного URL
    private extractAnchorFromUrl(url: string): string {
      if (!url) return '';
      
      // Если это уже якорь, возвращаем как есть
      if (url.startsWith('#')) {
        return url;
      }
      
      // Если это полный URL с якорем, извлекаем только якорь
      const hashIndex = url.indexOf('#');
      if (hashIndex !== -1) {
        return url.substring(hashIndex);
      }
      
      // Если это обычный URL без якоря, возвращаем как есть
      return url;
    }

    async showInlinePopup(linkElement: HTMLAnchorElement) {
      // Удаляем существующие попапы
      const existingPopups = document.querySelectorAll('.ce-link-popup');
      existingPopups.forEach(popup => popup.remove());

      // Создаем попап
      const popup = document.createElement('div');
      popup.className = 'ce-link-popup';
      
      // Извлекаем якорь из URL если это якорь
      const currentUrl = linkElement.href || '';
      const displayUrl = this.extractAnchorFromUrl(currentUrl);
      
      // Создаем input для URL
      const urlInput = document.createElement('input');
      urlInput.type = 'url';
      urlInput.className = 'ce-link-popup__input';
      urlInput.placeholder = 'Вставьте ссылку или выберите якорь...';
      urlInput.value = displayUrl;
      
      // Кнопка показать якоря
      const anchorsButton = document.createElement('button');
      anchorsButton.className = 'ce-link-popup__anchors';
      anchorsButton.innerHTML = '⚓';
      anchorsButton.title = 'Выбрать якорь';
      
      // Кнопка сохранить
      const saveButton = document.createElement('button');
      saveButton.className = 'ce-link-popup__save';
      saveButton.innerHTML = '✓';
      saveButton.title = 'Сохранить';
      
      // Кнопка удалить
      const removeButton = document.createElement('button');
      removeButton.className = 'ce-link-popup__remove';
      removeButton.innerHTML = '✕';
      removeButton.title = 'Удалить ссылку';
      
      // Добавляем элементы в попап
      popup.appendChild(urlInput);
      popup.appendChild(anchorsButton);
      popup.appendChild(saveButton);
      popup.appendChild(removeButton);
      
      // Сначала добавляем попап в DOM с невидимым состоянием для правильного расчета размеров
      popup.style.visibility = 'hidden';
      popup.style.position = 'absolute';
      document.body.appendChild(popup);
      
      // Теперь позиционируем попап правильно
      this.positionPopup(popup, linkElement);
      
      // Делаем попап видимым с анимацией
      popup.style.visibility = 'visible';
      setTimeout(() => {
        popup.classList.add('visible');
      }, 10);
      
      // Фокусируемся на input
      urlInput.focus();
      urlInput.select();
      
      // Обработчики событий
      const handleSave = () => {
        const url = urlInput.value.trim();
        console.log('💾 CustomInlineLinkTool: Сохранение ссылки...');
        console.log('🔗 URL:', url);
        console.log('🎯 Элемент ссылки:', linkElement);
        console.log('📝 Текущий href:', linkElement.href);
        
        if (url) {
          // Нормализуем URL (добавляем протокол если нужно)
          const normalizedUrl = this.normalizeUrl(url);
          linkElement.href = normalizedUrl;
          console.log('✅ Новый href установлен:', linkElement.href);
        } else {
          console.log('🗑️ URL пустой, удаляем ссылку...');
          this.removeLink(linkElement);
        }
        popup.remove();
        
        // Принудительно сохраняем модель после изменения
        console.log('⏰ Запланировано сохранение через 100мс...');
        setTimeout(() => {
          this.triggerSave();
        }, 100);
      };
      
      const handleRemove = () => {
        console.log('🗑️ CustomInlineLinkTool: Удаление ссылки...');
        console.log('🎯 Элемент ссылки:', linkElement);
        this.removeLink(linkElement);
        popup.remove();
        
        // Принудительно сохраняем модель после удаления
        console.log('⏰ Запланировано сохранение после удаления через 100мс...');
        setTimeout(() => {
          this.triggerSave();
        }, 100);
      };

      const handleAnchors = async () => {
        // Удаляем существующий список якорей если есть
        const existingSuggestions = popup.querySelector('.ce-link-suggestions');
        if (existingSuggestions) {
          existingSuggestions.remove();
          return;
        }

        const anchors = await this.getAnchors();
        if (anchors.length === 0) {
          // Показываем уведомление об отсутствии якорей
          const noAnchorsDiv = document.createElement('div');
          noAnchorsDiv.className = 'ce-link-suggestions';
          noAnchorsDiv.innerHTML = '<div class="ce-link-suggestions__title">Якорей в материале не найдено</div>';
          popup.appendChild(noAnchorsDiv);
          
          setTimeout(() => {
            noAnchorsDiv.remove();
          }, 2000);
          return;
        }

        const suggestionList = document.createElement('div');
        suggestionList.className = 'ce-link-suggestions';
        
        const title = document.createElement('div');
        title.className = 'ce-link-suggestions__title';
        title.textContent = 'Якоря в материале:';
        suggestionList.appendChild(title);
        
        anchors.forEach(anchor => {
          if (!anchor) return;
          
          const item = document.createElement('div');
          item.className = 'ce-link-suggestions__item';
          item.textContent = `#${anchor}`;
          item.onclick = (e) => {
            e.stopPropagation();
            urlInput.value = `#${anchor}`;
            suggestionList.remove();
            urlInput.focus();
          };
          suggestionList.appendChild(item);
        });

        popup.appendChild(suggestionList);
      };
      
      const handleClickOutside = (e: MouseEvent) => {
        if (!popup.contains(e.target as Node) && !linkElement.contains(e.target as Node)) {
          handleSave();
          document.removeEventListener('click', handleClickOutside);
        }
      };
      
      // События
      anchorsButton.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        handleAnchors();
      });
      
      saveButton.addEventListener('click', handleSave);
      removeButton.addEventListener('click', handleRemove);
      
      urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          handleSave();
        } else if (e.key === 'Escape') {
          e.preventDefault();
          popup.remove();
        }
      });
      
      // Клик вне попапа через небольшую задержку
      setTimeout(() => {
        document.addEventListener('click', handleClickOutside);
      }, 100);
    }

    positionPopup(popup: HTMLElement, linkElement: HTMLAnchorElement) {
      const linkRect = linkElement.getBoundingClientRect();
      const popupRect = popup.getBoundingClientRect();
      
      // Находим контейнер редактора для дополнительной проверки
      const editorContainer = linkElement.closest('.codex-editor') as HTMLElement;
      const editorRect = editorContainer ? editorContainer.getBoundingClientRect() : null;
      
      console.log('Позиционирование попапа:', {
        linkRect: {
          top: linkRect.top,
          bottom: linkRect.bottom,
          left: linkRect.left,
          right: linkRect.right,
          width: linkRect.width,
          height: linkRect.height
        },
        editorRect: editorRect ? {
          top: editorRect.top,
          bottom: editorRect.bottom,
          left: editorRect.left,
          right: editorRect.right
        } : null,
        popupRect: {
          width: popupRect.width,
          height: popupRect.height
        },
        window: {
          scrollX: window.scrollX,
          scrollY: window.scrollY,
          innerWidth: window.innerWidth,
          innerHeight: window.innerHeight
        }
      });
      
      // Позиционируем под ссылкой
      let top = linkRect.bottom + window.scrollY + 8;
      let left = linkRect.left + window.scrollX;
      
      console.log('Первичные координаты:', { top, left });
      
      // Проверяем, не выходит ли попап за правую границу экрана
      if (left + popupRect.width > window.innerWidth) {
        left = window.innerWidth - popupRect.width - 20;
        console.log('Скорректировано по правой границе:', { left });
      }
      
      // Проверяем, не выходит ли попап за левую границу экрана
      if (left < 10) {
        left = 10;
        console.log('Скорректировано по левой границе:', { left });
      }
      
      // Проверяем, не выходит ли попап за нижнюю границу экрана
      if (top + popupRect.height > window.innerHeight + window.scrollY) {
        top = linkRect.top + window.scrollY - popupRect.height - 8;
        console.log('Скорректировано по нижней границе:', { top });
      }
      
      // Проверяем, не выходит ли попап за верхнюю границу экрана
      if (top < window.scrollY + 10) {
        top = linkRect.bottom + window.scrollY + 8;
        console.log('Скорректировано по верхней границе:', { top });
      }
      
      console.log('Финальные координаты:', { top, left });
      
      popup.style.top = `${top}px`;
      popup.style.left = `${left}px`;
      popup.style.zIndex = '1000';
    }

    removeLink(linkElement: HTMLAnchorElement) {
      console.log('🗑️ removeLink вызван для элемента:', linkElement);
      const textContent = linkElement.textContent || '';
      console.log('📝 Текст ссылки:', textContent);
      const textNode = document.createTextNode(textContent);
      linkElement.parentNode?.replaceChild(textNode, linkElement);
      console.log('✅ Ссылка удалена, текст сохранен');
    }

    checkState() {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return false;
      
      const range = selection.getRangeAt(0);
      const parentNode = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
        ? range.commonAncestorContainer.parentNode
        : range.commonAncestorContainer;
      
      return !!(parentNode as Element)?.closest(this.tag);
    }

    clear() {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0) return;
      
      const range = selection.getRangeAt(0);
      const parentNode = range.commonAncestorContainer.nodeType === Node.TEXT_NODE
        ? range.commonAncestorContainer.parentNode
        : range.commonAncestorContainer;
      
      const linkElement = (parentNode as Element)?.closest(this.tag) as HTMLAnchorElement;
      if (linkElement) {
        this.removeLink(linkElement);
      }
    }

    // Метод для санитизации HTML
    static get sanitize() {
      return {
        a: {
          href: true,
          target: '_blank',
          rel: 'noopener'
        }
      };
    }

    // Метод для удаления обертки
    unwrap(termWrapper: HTMLElement) {
      this.api.selection.expandToTag(termWrapper);
    }
  }

  interface AdditionalData {
    previewImage: string
    previewDescription: string
    metaTitle: string
    metaDescription: string
  }

  interface ContentData {
    blocks: any[]
    additional?: AdditionalData
    [key: string]: any
  }

  export let value = ''
  export let placeholder = ''
  export let label = ''
  export let postTemplateType: '' | PostTemplateType = ''
  export let enabledTemplateEditorBlockTypes: string[] | undefined = undefined
  export let postId: string | number | null = null // ID поста для автосохранения
  export let enableAutosave: boolean = true // Разрешение автосохранения
  export let onContentChange: (() => void) | null = null // Callback для уведомления PostForm об изменениях

  let previewImage = ''
  let previewDescription = ''
  let metaDescription = ''
  let metaTitle = ''
  let draftLastSaved: Date | null = null
  let autosaveTimeout: NodeJS.Timeout | null = null
  let isUpdatingFromInternal = false // Флаг для предотвращения циклов обновления
  let isInitialized = false // Флаг готовности редактора для автосохранения
  
  let element: HTMLElement
  let editor: any
  let markdownOutput = ''
  let destroyBlockDragAndDrop: (() => void) | null = null

  const setupEditorBlockDragAndDrop = (editorInstance: any, rootElement: HTMLElement) => {
    const redactor = rootElement.querySelector('.codex-editor__redactor') as HTMLElement | null
    if (!redactor) {
      return () => {}
    }

    let fromIndex: number | null = null
    let dragSourceBlock: HTMLElement | null = null
    let currentDropBlock: HTMLElement | null = null
    let currentDropPosition: 'before' | 'after' | null = null

    const clearDropDecorations = () => {
      redactor.querySelectorAll('.ce-block.comuna-drop-before, .ce-block.comuna-drop-after').forEach((block) => {
        block.classList.remove('comuna-drop-before', 'comuna-drop-after')
      })
      currentDropBlock = null
      currentDropPosition = null
    }

    const clearDragState = () => {
      clearDropDecorations()
      if (dragSourceBlock) {
        dragSourceBlock.classList.remove('comuna-block-dragging')
      }
      rootElement
        .querySelectorAll('.ce-toolbar__settings-btn.editorjs-dnd-dragging')
        .forEach((button) => button.classList.remove('editorjs-dnd-dragging'))
      dragSourceBlock = null
      fromIndex = null
    }

    const getEditorBlocks = () => Array.from(redactor.querySelectorAll('.ce-block')) as HTMLElement[]

    const getBlockIndex = (block: HTMLElement | null) => {
      if (!block) return -1
      return getEditorBlocks().indexOf(block)
    }

    const ensureSettingsButtonsDraggable = () => {
      rootElement.querySelectorAll('.ce-toolbar__settings-btn').forEach((button) => {
        const el = button as HTMLElement
        if (!el.hasAttribute('draggable')) {
          el.setAttribute('draggable', 'true')
        }
        if (!el.title) {
          el.title = 'Перетащите, чтобы переместить блок'
        }
      })
    }

    const mutationObserver = new MutationObserver(() => {
      ensureSettingsButtonsDraggable()
    })

    const onPointerDown = (event: Event) => {
      const target = event.target as HTMLElement | null
      const settingsButton = target?.closest('.ce-toolbar__settings-btn') as HTMLElement | null
      if (settingsButton) {
        settingsButton.setAttribute('draggable', 'true')
      }
    }

    const onDragStart = (event: DragEvent) => {
      const target = event.target as HTMLElement | null
      const settingsButton = target?.closest('.ce-toolbar__settings-btn') as HTMLElement | null
      if (!settingsButton) return

      const currentIndex = typeof editorInstance?.blocks?.getCurrentBlockIndex === 'function'
        ? editorInstance.blocks.getCurrentBlockIndex()
        : -1

      const blocks = getEditorBlocks()
      const sourceBlock = blocks[currentIndex]
      if (currentIndex < 0 || !sourceBlock) return

      fromIndex = currentIndex
      dragSourceBlock = sourceBlock

      dragSourceBlock.classList.add('comuna-block-dragging')
      settingsButton.classList.add('editorjs-dnd-dragging')

      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = 'move'
        event.dataTransfer.setData('text/plain', String(currentIndex))
      }
    }

    const resolveDropPosition = (event: DragEvent, block: HTMLElement): 'before' | 'after' => {
      const rect = block.getBoundingClientRect()
      return event.clientY >= rect.top + rect.height / 2 ? 'after' : 'before'
    }

    const paintDropTarget = (block: HTMLElement, position: 'before' | 'after') => {
      if (currentDropBlock && currentDropBlock !== block) {
        currentDropBlock.classList.remove('comuna-drop-before', 'comuna-drop-after')
      }
      if (currentDropBlock === block && currentDropPosition === position) {
        return
      }
      block.classList.remove('comuna-drop-before', 'comuna-drop-after')
      block.classList.add(position === 'before' ? 'comuna-drop-before' : 'comuna-drop-after')
      currentDropBlock = block
      currentDropPosition = position
    }

    const onDragOver = (event: DragEvent) => {
      if (fromIndex == null) return
      const target = event.target as HTMLElement | null
      const targetBlock = target?.closest('.ce-block') as HTMLElement | null
      if (!targetBlock || !redactor.contains(targetBlock)) {
        return
      }

      event.preventDefault()
      if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move'
      }

      const position = resolveDropPosition(event, targetBlock)
      paintDropTarget(targetBlock, position)
    }

    const onDrop = async (event: DragEvent) => {
      if (fromIndex == null) return

      const target = event.target as HTMLElement | null
      const targetBlock = target?.closest('.ce-block') as HTMLElement | null
      if (!targetBlock || !redactor.contains(targetBlock)) {
        clearDragState()
        return
      }

      event.preventDefault()

      const targetIndex = getBlockIndex(targetBlock)
      if (targetIndex < 0) {
        clearDragState()
        return
      }

      const position = resolveDropPosition(event, targetBlock)
      const blocksCount = getEditorBlocks().length
      let toIndex = fromIndex

      if (position === 'before') {
        toIndex = fromIndex < targetIndex ? targetIndex - 1 : targetIndex
      } else {
        toIndex = fromIndex < targetIndex ? targetIndex : targetIndex + 1
      }

      toIndex = Math.max(0, Math.min(blocksCount - 1, toIndex))

      if (toIndex === fromIndex) {
        clearDragState()
        return
      }

      const sourceIndex = fromIndex
      clearDragState()

      try {
        editorInstance.blocks.move(toIndex, sourceIndex)
        const data = await editorInstance.save()
        updateMarkdown(data)
      } catch (error) {
        console.error('Ошибка при перетаскивании блока EditorJS:', error)
      } finally {
        ensureSettingsButtonsDraggable()
      }
    }

    const onDragEnd = () => {
      clearDragState()
    }

    ensureSettingsButtonsDraggable()
    mutationObserver.observe(rootElement, { childList: true, subtree: true })
    rootElement.addEventListener('pointerdown', onPointerDown, true)
    rootElement.addEventListener('dragstart', onDragStart, true)
    rootElement.addEventListener('dragend', onDragEnd, true)
    redactor.addEventListener('dragover', onDragOver)
    redactor.addEventListener('drop', onDrop)

    return () => {
      mutationObserver.disconnect()
      clearDragState()
      rootElement.removeEventListener('pointerdown', onPointerDown, true)
      rootElement.removeEventListener('dragstart', onDragStart, true)
      rootElement.removeEventListener('dragend', onDragEnd, true)
      redactor.removeEventListener('dragover', onDragOver)
      redactor.removeEventListener('drop', onDrop)
    }
  }

  // Функция для автосохранения черновика
  const autosaveDraft = () => {
    console.log('🔄 EditorJS autosaveDraft: начало функции', {
      postId,
      enableAutosave,
      isInitialized,
      valueLength: value?.length || 0,
      hasTimeout: !!autosaveTimeout
    })
    
    // Блокируем автосохранение если оно отключено
    if (!enableAutosave) {
      console.log('🚫 EditorJS autosaveDraft: блокировано - автосохранение отключено')
      return
    }
    
    // Блокируем автосохранение если редактор ещё не инициализирован
    if (!isInitialized) {
      console.log('🚫 EditorJS autosaveDraft: блокировано - редактор ещё не готов')
      return
    }
    
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout)
      console.log('⏰ EditorJS autosaveDraft: очистили предыдущий таймер')
    }
    
          autosaveTimeout = setTimeout(() => {
        console.log('🚀 EditorJS autosaveDraft: выполняем отложенное сохранение', {
          postId,
          valueLength: value?.length || 0,
          previewImageLength: previewImage?.length || 0,
          previewDescriptionLength: previewDescription?.length || 0
        })
        
        // Не сохраняем отдельные черновики от EditorJS
        // Автосохранение должно происходить только на уровне PostForm
        console.log('⏭️ EditorJS: пропускаем автосохранение - оставляем это PostForm')
        draftLastSaved = new Date()
      }, 2000) // Автосохранение через 2 секунды после изменения
  }

  // Функция для обновления markdown
  const updateMarkdown = (data: any) => {
    console.log('📄 updateMarkdown вызван с данными:', data);
    
    // Устанавливаем флаг что обновление идёт изнутри (только если не обновляем извне)
    if (!isUpdatingFromInternal) {
      isUpdatingFromInternal = true
      
      // Добавляем дополнительные данные в JSON
      const additionalData = {
        previewImage,
        previewDescription,
        metaTitle,
        metaDescription
      }
      data.additional = additionalData
      
      // Сериализуем данные в base64
      const serializedData = serializeEditorModel(data)
      markdownOutput = serializedData
      value = serializedData
      lastExternalValue = serializedData // Обновляем также последнее внешнее значение
      
      console.log('💾 Данные сериализованы в base64, длина:', serializedData.length);
      console.log('📊 Количество блоков:', data.blocks?.length || 0);
      
      // Сбрасываем флаг через небольшую задержку
      setTimeout(() => {
        isUpdatingFromInternal = false
      }, 100)
    } else {
      console.log('⏭️ updateMarkdown пропущен - идёт внешнее обновление')
    }
    
    // Проверяем наличие ссылок в блоках
    if (data.blocks) {
      data.blocks.forEach((block: any, index: number) => {
        if (block.data?.text && block.data.text.includes('<a ')) {
          console.log(`🔗 Блок ${index} содержит ссылки:`, block.data.text);
        }
      });
    }
    
    // Запускаем автосохранение
    autosaveDraft()
    
    // Уведомляем PostForm об изменении контента
    if (onContentChange) {
      onContentChange()
    }
  }

  onMount(async () => {
    console.log('🚀 EditorJS onMount: начало монтирования', { postId })
    
    // Загружаем информацию о последнем сохранении черновика
    draftLastSaved = getDraftLastSaved(postId)
    console.log('📅 EditorJS onMount: дата последнего черновика', {
      draftLastSaved: draftLastSaved?.toLocaleString('ru-RU') || 'нет'
    })
    
    // Извлекаем существующие данные из value при монтировании
    let contentData: ContentData = { blocks: [] }
    
    try {
      // Пробуем десериализовать данные
      contentData = value ? deserializeEditorModel(value) : { blocks: [] }
    } catch (e) {
      console.error('Failed to deserialize content data:', e)
      contentData = { blocks: [] }
    }
    
    if (contentData.additional) {
      previewImage = contentData.additional.previewImage || ''
      previewDescription = contentData.additional.previewDescription || ''
      metaTitle = contentData.additional.metaTitle || ''
      metaDescription = contentData.additional.metaDescription || ''
    }

    // Динамический импорт Editor.js и его плагинов
    const [
      { default: EditorJS },
      { default: Header },
      { default: List },
      { default: Image },
      { default: Quote },
      { default: Code },
      { default: AlignmentBlockTune },
      { default: LinkTool },
      { default: Embed }
    ] = await Promise.all([
      import('@editorjs/editorjs'),
      import('@editorjs/header'),
      import('@editorjs/list'),
      import('@editorjs/image'),
      import('@editorjs/quote'),
      import('@editorjs/code'),
      import('editorjs-text-alignment-blocktune'),
      import('@editorjs/link'),
      import('@editorjs/embed')
    ])

    const enabledTemplateBlockTypes = new Set(
      enabledTemplateEditorBlockTypes === undefined
        ? getTemplateEditorBlockTypes(postTemplateType)
        : normalizeTemplateEditorBlockTypes(enabledTemplateEditorBlockTypes)
    )

    // Инициализация Editor.js
    editor = new EditorJS({
      holder: element,
      placeholder: placeholder,
      tools: {
        ...(enabledTemplateBlockTypes.has('header')
          ? {
              header: {
                class: Header,
                config: {
                  levels: [2, 3],
                  defaultLevel: 2
                },
                toolbox: {
                  title: 'Заголовок',
                  icon: `<img src="${icons.header}" width="16" height="16" />`
                }
              },
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('list')
          ? {
              list: {
                class: List,
                inlineToolbar: ['bold', 'italic', 'customInlineLink'],
                toolbox: {
                  title: 'Список',
                  icon: `<img src="${icons.unorderedList}" width="16" height="16" />`
                },
                config: {
                  defaultStyle: 'unordered'
                }
              },
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('image')
          ? {
              image: CustomImageTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('quote')
          ? {
              quote: {
                class: Quote,
                inlineToolbar: ['bold', 'italic', 'customInlineLink'],
                toolbox: {
                  title: 'Цитата',
                  icon: `<img src="${icons.quote}" width="16" height="16" />`
                }
              },
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('code')
          ? {
              code: {
                class: Code,
                inlineToolbar: ['bold', 'italic'],
                toolbox: {
                  title: 'Код',
                  icon: `<img src="${icons.code}" width="16" height="16" />`
                }
              },
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('spoiler')
          ? {
              spoiler: SpoilerTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('gallery')
          ? {
              gallery: GalleryTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('map')
          ? {
              map: MapTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('compare')
          ? {
              compare: {
                class: ImageCompareTool,
                toolbox: {
                  title: 'Сравнение изображений',
                  icon: `<img src="${icons.imageCompare}" width="16" height="16" />`,
                },
              },
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('movie_time')
          ? {
              movie_time: MovieTimeTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('music')
          ? {
              music: MusicTool,
            }
          : {}),
        ...(enabledTemplateBlockTypes.has('movie_card')
          ? {
              movie_card: MovieCardTool,
            }
          : {}),
        anchorInput: {
          class: CustomInputTune
        },
        ...(enabledTemplateBlockTypes.has('link')
          ? {
              customLink: CustomLinkTool,
            }
          : {}),
        customInlineLink: CustomInlineLinkTool,
        ...(enabledTemplateBlockTypes.has('embed')
          ? {
              embed: {
                class: Embed,
                config: {
            services: {
              // Стандартные сервисы
              youtube: true,
              vimeo: true,
              coub: true,
              facebook: true,
              instagram: true,
              twitter: true,
              'twitch-video': true,
              'twitch-channel': true,
              miro: true,
              gfycat: true,
              imgur: true,
              vine: true,
              aparat: true,
              'yandex-music-track': true,
              'yandex-music-album': true,
              'yandex-music-playlist': true,
              codepen: true,
              pinterest: true,
              github: true,
              // Кастомные сервисы
              rutube: {
                regex: /https?:\/\/rutube\.ru\/video\/([a-f0-9]+)(?:\/.*)?/,
                embedUrl: '<%= remote_id %>',
                html: "<iframe width='720' height='405' frameBorder='0' allow='clipboard-write; autoplay' webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe>",
                height: 405,
                width: 720,
                id: (groups: RegExpMatchArray) => {
                  console.log('Rutube video parsing - Input:', {
                    input: groups.input,
                    groups: Array.from(groups)
                  });
                  
                  try {

                    const videoId = groups[0];
                    
                    if (!videoId) {
                      throw new Error('Could not extract video ID from Rutube URL');
                    }

                    const embedUrl = `https://rutube.ru/play/embed/${videoId}/`;
                    console.log('Rutube video parsing - Success!', { videoId, embedUrl });
                    return embedUrl;
                  } catch (error) {
                    console.error('Rutube video parsing - Error:', error);
                    return null;
                  }
                }
              },
              vk: {
                regex: /https?:\/\/vk\.com\/vkvideo\?z=video([-\d]+)_(\d+)(?:%.+)?/,
                embedUrl:  '<%= remote_id %>',
                html: "<iframe width='426' height='240' allow='autoplay; encrypted-media; fullscreen; picture-in-picture; screen-wake-lock;' frameborder='0' allowfullscreen></iframe>",
                height: 300,
                width: 426,
                id: (groups: RegExpMatchArray) => {
                  console.log('VK video parsing (vkvideo format) - Input:', {
                    input: groups.input,
                    groups: Array.from(groups)
                  });
                  
                  try {
                    // В массиве groups:
                    // groups[0] содержит ID владельца (например "-220754053")
                    // groups[1] содержит ID видео (например "456243385")
                    const oid = groups[0];
                    const vid = groups[1];
                    
                    if (!oid || !vid) {
                      throw new Error('Could not extract video ID from vkvideo URL');
                    }

                    const result = {
                      remote_id: `https://vk.com/video_ext.php?oid=${oid}&id=${vid}`,
                      remote_id_oid: oid,
                      remote_id_vid: vid
                    };
                    console.log('VK video parsing (vkvideo format) - Success!', result);
                    return result.remote_id;
                  } catch (error) {
                    console.error('VK video parsing (vkvideo format) - Error:', error);
                    return null;
                  }
                }
              },
              vkvideo: {
                regex: /https?:\/\/vk\.com\/video([-\d]+)_(\d+)/,
                embedUrl: '<%= remote_id %>',
                html: "<iframe width='426' height='240' allow='autoplay; encrypted-media; fullscreen; picture-in-picture; screen-wake-lock;' frameborder='0' allowfullscreen></iframe>",
                height: 300,
                width: 426,
                id: (groups: RegExpMatchArray) => {
                  console.log('VK video parsing (direct format) - Input:', {
                    input: groups.input,
                    groups: Array.from(groups)
                  });
                  
                  try {
                  
                    const oid = groups[0];
                    const vid = groups[1];
                    
                    if (!oid || !vid) {
                      throw new Error('Could not extract video ID from direct video URL');
                    }

                    const result = {
                      remote_id: `https://vk.com/video_ext.php?oid=${oid}&id=${vid}`,
                      remote_id_oid: oid,
                      remote_id_vid: vid
                    };
                    console.log('VK video parsing (direct format) - Success!', result);
                    return result.remote_id;

                  } catch (error) {
                    console.error('VK video parsing (direct format) - Error:', error);
                    return null;
                  }
                }
              },
              vkvideoRu: {
                // Пример URL: https://vkvideo.ru/video-1623507_456247959
                regex: /https?:\/\/vkvideo\.ru\/video-([-\d]+)_(\d+)/,
                embedUrl: '<%= remote_id %>',
                html: "<iframe width='426' height='240' allow='autoplay; encrypted-media; fullscreen; picture-in-picture; screen-wake-lock;' frameborder='0' allowfullscreen></iframe>",
                height: 300,
                width: 426,
                id: (groups: RegExpMatchArray) => {
                  console.log('VK video parsing (vkvideo.ru format) - Input:', {
                    input: groups.input,
                    groups: Array.from(groups),
                    match: {
                      full: groups[0],
                      oid: groups[1],
                      vid: groups[2]
                    }
                  });
                  
                  try {
                    // В массиве groups:
                    // groups[0] содержит ID владельца (например "-220754053")
                    // groups[1] содержит ID видео (например "456243385")
                    const oid = groups[0];
                    const vid = groups[1];
                    
                    if (!oid || !vid) {
                      console.error('Missing oid or vid:', { oid, vid, groups: Array.from(groups) });
                      throw new Error('Could not extract video ID from vkvideo.ru URL');
                    }

                    const result = {
                      remote_id: `https://vkvideo.ru/video_ext.php?oid=-${oid}&id=${vid}`,
                      remote_id_oid: oid,
                      remote_id_vid: vid
                    };
                    console.log('VK video parsing (vkvideo.ru format) - Success!', result);
                    return result.remote_id;
                  } catch (error) {
                    console.error('VK video parsing (vkvideo.ru format) - Error:', error);
                    return null;
                  }
                }
              }
            }
          },
        },
      }
      : {}),
      },
      tunes: ["anchorInput"],
      inlineToolbar: ['bold', 'italic', 'customInlineLink'],
      i18n: {
        messages: {
          ui: {
            "blockTunes": {
              "toggler": {
                "Click to tune": "Нажмите, чтобы настроить",
                "or drag to move": "или перетащите"
              },
            },
            "toolbar": {
              "toolbox": {
                "Add": "Добавить",
                "Filter": "Фильтр",
                "Nothing found": "Ничего не найдено"
              }
            },
            "inlineToolbar": {
              "converter": {
                "Convert to": "Преобразовать в"
              }
            },
            "popover": {
              "Convert to": "Преобразовать в"
            }
          },
          toolNames: {
            "Text": "Текст",
            "Heading": "Заголовок",
            "List": "Список",
            "Quote": "Цитата",
            "Code": "Код",
            "Image": "Изображение",
            "Gallery": "Галерея",
            "Map": "Карта",
            "Image Compare": "Сравнение изображений",
            "Сравнение изображений": "Сравнение изображений",
            "Compare": "Сравнение изображений",
            "Movie Time": "Время в фильме",
            "Время в фильме": "Время в фильме",
            "Movie Card": "Карточка фильма",
            "Карточка фильма": "Карточка фильма",
            "Link": "Ссылка",
            "Unordered List": "Маркированный список",
            "Ordered List": "Нумерованный список",
            "Checklist": "Чек-лист",
            "Numbered List": "Нумерованный список",
            "Heading 2": "Заголовок 2",
            "Heading 3": "Заголовок 3"
          },
          tools: {
            "warning": {
              "Title": "Заголовок",
              "Message": "Сообщение",
            },
            "link": {
              "Add a link": "Добавить ссылку",
              "Link": "Ссылка",
              "Paste the link and press Enter": "Вставьте ссылку и нажмите Enter"
            },
            "customInlineLink": {
              "Add a link": "Добавить ссылку",
              "Link": "Ссылка"
            },
            "stub": {
              "The block can not be displayed correctly.": "Блок не может быть корректно отображен."
            },
            "list": {
              "Unordered": "Маркированный",
              "Ordered": "Нумерованный",
              "Convert to": "Преобразовать в"
            },
            "header": {
              "Heading 2": "Заголовок 2",
              "Heading 3": "Заголовок 3",
              "Convert to": "Преобразовать в"
            },
            "embed": {
              "Enter a caption": "Введите подпись"
            }
          },
          blockTunes: {
            "delete": {
              "Delete": "Удалить",
              "Click to delete": "Нажмите, чтобы удалить"
            },
            "moveUp": {
              "Move up": "Переместить вверх"
            },
            "moveDown": {
              "Move down": "Переместить вниз"
            },
            "convertTo": {
              "Convert to": "Преобразовать в"
            }
          }
        }
      },
      data: contentData,
      onChange: async () => {
        const data = await editor.save()
        updateMarkdown(data)
      },
      onReady: () => {
        console.log('🚀 EditorJS готов к работе');

        destroyBlockDragAndDrop?.()
        destroyBlockDragAndDrop = setupEditorBlockDragAndDrop(editor, element)
        
        // Добавляем обработчик кликов по ссылкам для их редактирования
        const editorElement = element.querySelector('.codex-editor__redactor');
        if (editorElement) {
          console.log('✅ Обработчик кликов по ссылкам добавлен');
          editorElement.addEventListener('click', (e: Event) => {
            const target = e.target as HTMLElement;
            const linkElement = target.closest('a') as HTMLAnchorElement;
            
            console.log('👆 Клик в редакторе:', { target, linkElement });
            
            if (linkElement && !(e as MouseEvent).ctrlKey && !(e as MouseEvent).metaKey) {
              console.log('🔗 Клик по ссылке обнаружен:', linkElement.href);
              e.preventDefault();
              e.stopPropagation();
              
              // Создаем временный экземпляр tool для показа попапа с правильным API
              const tempTool = new CustomInlineLinkTool({ api: editor });
              tempTool.showInlinePopup(linkElement);
            }
          });
        } else {
          console.warn('⚠️ Элемент редактора не найден');
        }
        
        // Включаем автосохранение через 2 секунды после готовности редактора
        setTimeout(() => {
          isInitialized = true;
          console.log('✅ EditorJS: автосохранение включено');
        }, 2000);
      }
    })
  })

  let lastExternalValue = '' // Отслеживаем последнее внешнее значение

  // Реактивное обновление содержимого редактора при изменении value извне
  $: if (editor && value && !isUpdatingFromInternal && value !== lastExternalValue) {
    updateEditorContent(value)
  }

  async function updateEditorContent(newValue: string) {
    if (!editor || !newValue || isUpdatingFromInternal) return
    
    try {
      console.log('🔄 EditorJS: обновляем содержимое редактора извне', {
        newValueLength: newValue.length,
        newValuePreview: newValue.substring(0, 100),
        lastExternalValue: lastExternalValue.substring(0, 50)
      })
      
      // Устанавливаем флаг блокировки
      isUpdatingFromInternal = true
      lastExternalValue = newValue
      
      const contentData = deserializeEditorModel(newValue)
      
      // Очищаем редактор и загружаем новые данные
      await editor.clear()
      await editor.render(contentData)
      
      // Временно отключаем автосохранение при внешнем обновлении
      isInitialized = false
      
      console.log('✅ EditorJS: содержимое редактора обновлено', {
        blocksCount: contentData.blocks?.length || 0
      })
      
      // Обновляем дополнительные данные
      if (contentData.additional) {
        previewImage = contentData.additional.previewImage || ''
        previewDescription = contentData.additional.previewDescription || ''
        metaTitle = contentData.additional.metaTitle || ''
        metaDescription = contentData.additional.metaDescription || ''
      }
      
      // Сбрасываем флаг через задержку и включаем автосохранение обратно
      setTimeout(() => {
        isUpdatingFromInternal = false
        isInitialized = true
        console.log('✅ EditorJS: автосохранение включено после внешнего обновления')
      }, 1000) // Увеличиваем задержку
      
    } catch (e) {
      console.error('❌ EditorJS: ошибка при обновлении содержимого:', e)
      isUpdatingFromInternal = false
    }
  }

  onDestroy(() => {
    destroyBlockDragAndDrop?.()
    destroyBlockDragAndDrop = null
    if (editor) {
      editor.destroy()
    }
    if (autosaveTimeout) {
      clearTimeout(autosaveTimeout)
    }
  })
</script>

<div class="flex flex-col gap-1 relative editor-container">
  {#if label}
    <span class="font-medium text-sm text-slate-600 dark:text-slate-300">{label}</span>
  {/if}

  <div
    class="min-h-[400px] p-3 rounded-lg focus-within:ring-2 focus-within:ring-blue-500 transition-all duration-200 editor-content bg-white dark:bg-slate-800 border dark:border-slate-700"
    bind:this={element}
  />

  {#if showPostSettings}
    <!-- Информационный блок об обложке поста -->
    <div class="mt-4 text-xs sm:text-sm text-slate-600 dark:text-slate-400 bg-white dark:bg-zinc-900/60 border border-dashed border-slate-200 dark:border-zinc-800 rounded-lg px-3 py-2 sm:px-4 sm:py-3">
      <div class="flex flex-col sm:flex-row gap-3 sm:gap-4 items-start">
        <div class="flex-1 flex flex-col gap-1.5">
          <span class="font-medium text-slate-800 dark:text-slate-100">
            Обложка поста
          </span>
          <p class="leading-snug">
            Хороший пост должен быть с обложкой. Выберите любое изображение в статье и кликните - <strong>вывести в ленте</strong>. Тогда выбранное изображение появится в ленте постов, и ваш пост станет гораздо более кликабельным.
          </p>
        </div>
        <div class="flex-shrink-0 w-full sm:w-auto sm:max-w-[300px]">
          <img
            src="/img/oblozhka.webp"
            alt="Демонстрация создания обложки поста"
            class="w-full sm:w-[300px] rounded-lg border border-slate-200 dark:border-zinc-700"
            loading="lazy"
          />
        </div>
      </div>
    </div>

    <div class="mt-4 space-y-4">
      <div class="flex flex-col gap-1">
        <div class="flex items-center justify-between">
          <p class="font-medium text-lg text-slate-600 dark:text-slate-300">
            Настройки поста
          </p>
          {#if draftLastSaved}
            <span class="text-xs text-slate-500 dark:text-slate-400">
              Черновик: {formatLastSaved(draftLastSaved)}
            </span>
          {/if}
        </div>
      </div>
    </div>

    <div class="mt-4 space-y-4">
      <div class="flex flex-col gap-1">
        <label for="previewDescription" class="font-medium text-sm text-slate-600 dark:text-slate-300">
          Вывести в ленте
        </label>
        <textarea
          id="previewDescription"
          bind:value={previewDescription}
          on:input={(e) => {
            e.preventDefault();
            e.stopPropagation();
            editor.save().then(updateMarkdown);
          }}
          placeholder="Этот текст будет показан в ленте постов и в превью статьи. Коротко и ясно опишите, о чём материал — это помогает привлечь внимание и повысить кликабельность. Если оставить поле пустым, в ленту автоматически попадут первые 300 символов из статьи."
          rows="4"
          class="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 resize-none"
        ></textarea>
      </div>

      <div class="flex flex-col gap-1">
        <label for="metaTitle" class="font-medium text-sm text-slate-600 dark:text-slate-300">
          SEO meta title
        </label>
        <input
          id="metaTitle"
          type="text"
          bind:value={metaTitle}
          on:input={(e) => {
            e.preventDefault();
            e.stopPropagation();
            editor.save().then(updateMarkdown);
          }}
          placeholder="Введите заголовок для поисковых систем (до 60 символов)"
          class="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200"
        />
      </div>

      <div class="flex flex-col gap-1">
        <label for="metaDescription" class="font-medium text-sm text-slate-600 dark:text-slate-300">
          SEO meta description
        </label>
        <textarea
          id="metaDescription"
          bind:value={metaDescription}
          on:input={(e) => {
            e.preventDefault();
            e.stopPropagation();
            editor.save().then(updateMarkdown);
          }}
          placeholder="Описание, которое увидят пользователи в результатах поиска (до 160 символов)"
          rows="3"
          class="w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-slate-800 dark:border-slate-700 dark:text-slate-200 resize-none"
        ></textarea>
      </div>
    </div>
  {/if}
</div>

<style>
  .editor-container {
    position: relative;
  }

  .editor-content {
    padding-left: 2.5rem;
  }

  :global(.gallery-wrapper) {
    padding: 1rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    margin: 1rem 0;
  }

  :global(.dark .gallery-wrapper) {
    background: #1f2937;
    border-color: #4b5563;
  }

  :global(.gallery-button) {
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    padding: 0.5rem 1rem;
    cursor: pointer;
    margin-bottom: 1rem;
    color: #374151;
    font-size: 0.875rem;
    font-weight: 500;
    transition: all 0.2s;
  }

  :global(.gallery-button:hover) {
    background: #e5e7eb;
  }

  :global(.dark .gallery-button) {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.dark .gallery-button:hover) {
    background: #4b5563;
  }

  :global(.gallery-grid) {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 1rem;
    margin-top: 1rem;
  }

  :global(.gallery-item) {
    position: relative;
    aspect-ratio: 1;
    overflow: hidden;
    border-radius: 0.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    opacity: 0;
    transition: all 0.3s ease;
    cursor: move;
  }

  :global(.gallery-item.dragging) {
    opacity: 0.5;
    transform: scale(0.95);
    box-shadow: 0 0 0 2px #2563eb;
  }

  :global(.dark .gallery-item.dragging) {
    box-shadow: 0 0 0 2px #60a5fa;
  }

  :global(.gallery-item.drag-over) {
    border: 2px dashed #2563eb;
    background: rgba(37, 99, 235, 0.1);
  }

  :global(.dark .gallery-item.drag-over) {
    border-color: #60a5fa;
    background: rgba(96, 165, 250, 0.1);
  }

  :global(.gallery-item.loaded) {
    opacity: 1;
  }

  :global(.gallery-item.error) {
    background: #fee2e2;
    border-color: #ef4444;
  }

  :global(.dark .gallery-item.error) {
    background: #7f1d1d;
    border-color: #dc2626;
  }

  :global(.gallery-item img) {
    width: 100%;
    height: 100%;
    object-fit: cover;
    opacity: 0;
    transition: opacity 0.3s ease;
    pointer-events: none;
  }

  :global(.gallery-item.loaded img) {
    opacity: 1;
  }

  :global(.gallery-remove) {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border: none;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1.2rem;
  }

  :global(.gallery-settings) {
    position: absolute;
    top: 0.5rem;
    left: 0.5rem;
    background: rgba(0, 0, 0, 0.5);
    color: white;
    border: none;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    font-size: 1rem;
    transition: all 0.2s;
  }

  :global(.gallery-settings:hover) {
    background: rgba(0, 0, 0, 0.7);
  }

  :global(.gallery-settings-panel) {
    position: absolute;
    top: 2.5rem;
    left: 0.5rem;
    right: 0.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    z-index: 10;
  }

  :global(.dark .gallery-settings-panel) {
    background: #1f2937;
    border-color: #4b5563;
  }

  :global(.gallery-input) {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    background: white;
    color: #1f2937;
    font-size: 0.875rem;
    line-height: 1.25rem;
  }

  :global(.dark .gallery-input) {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.gallery-input:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  :global(.dark .gallery-input:focus) {
    border-color: #60a5fa;
    box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.1);
  }

  :global(.image-tool__wrapper) {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    padding: 1rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
  }

  :global(.dark .image-tool__wrapper) {
    background: #1f2937;
    border-color: #4b5563;
  }

  :global(.image-tool__image-wrapper) {
    position: relative;
    margin: 1rem 0;
  }

  :global(.image-tool__image-wrapper img) {
    width: 100%;
    height: auto;
    display: block;
    border-radius: 0.375rem;
  }

  :global(.image-tool__preview-control) {
    position: absolute;
    top: 0.5rem;
    right: 0.5rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 0.75rem;
    background: rgba(229, 231, 235, 0.9);
    border-radius: 0.375rem;
    color: #374151;
    cursor: pointer;
    transition: all 0.2s;
    z-index: 2;
    font-size: 0.875rem;
  }

  :global(.dark .image-tool__preview-control) {
    background: rgba(55, 65, 81, 0.9);
    color: #e5e7eb;
  }

  :global(.image-tool__preview-control:hover) {
    background: rgba(209, 213, 219, 0.9);
  }

  :global(.dark .image-tool__preview-control:hover) {
    background: rgba(75, 85, 99, 0.9);
  }

  :global(.image-tool__preview-control.active) {
    color: #2563eb;
  }

  :global(.dark .image-tool__preview-control.active) {
    color: #60a5fa;
  }

  :global(.preview-star) {
    font-size: 1.2rem;
    line-height: 1;
    transition: all 0.2s;
  }

  :global(.image-tool__preview-control:hover .preview-star) {
    transform: scale(1.1);
  }

  :global(.preview-text) {
    font-weight: 500;
  }

  :global(.image-tool__caption) {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    background: white;
    color: #1f2937;
    font-size: 0.875rem;
    line-height: 1.25rem;
    min-height: 2.5rem;
  }

  :global(.dark .image-tool__caption) {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.image-tool__caption:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  :global(.dark .image-tool__caption:focus) {
    border-color: #60a5fa;
    box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.1);
  }

  :global(.image-tool__alt),
  :global(.image-tool__title) {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    background: white;
    color: #1f2937;
    font-size: 0.875rem;
    line-height: 1.25rem;
  }

  :global(.dark .image-tool__alt),
  :global(.dark .image-tool__title) {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.image-tool__alt:focus),
  :global(.image-tool__title:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  :global(.dark .image-tool__alt:focus),
  :global(.dark .image-tool__title:focus) {
    border-color: #60a5fa;
    box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.1);
  }

  :global(.image-tool__button) {
    display: block;
    width: 100%;
    padding: 0.75rem;
    margin-bottom: 1rem;
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    color: #374151;
    font-size: 0.875rem;
    font-weight: 500;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
  }

  :global(.image-tool__button:hover) {
    background: #e5e7eb;
  }

  :global(.dark .image-tool__button) {
    background: #374151;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.dark .image-tool__button:hover) {
    background: #4b5563;
  }

  :global(.image-tool__loader) {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 0.5rem;
  }

  :global(.image-tool__loader-spinner) {
    width: 40px;
    height: 40px;
    border: 4px solid #2563eb;
    border-radius: 50%;
    border-top-color: transparent;
    animation: spin 1s linear infinite;
  }

  :global(.image-tool__loader-text) {
    margin-top: 1rem;
    font-size: 1rem;
    font-weight: 500;
    color: #1f2937;
  }

  @keyframes spin {
    0% {
      transform: rotate(0deg);
    }
    100% {
      transform: rotate(360deg);
    }
  }

  :global(.dark .image-tool__loader) {
    background: rgba(31, 41, 55, 0.8);
  }

  :global(.dark .image-tool__loader-spinner) {
    border-color: #60a5fa;
    border-top-color: transparent;
  }

  :global(.dark .image-tool__loader-text) {
    color: #e5e7eb;
  }

  :global(.movie-time-tool) {
    border-radius: 0.9rem;
    border: 1px solid #e2e8f0;
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.22), rgba(251, 191, 36, 0) 58%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.93), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  :global(.dark .movie-time-tool) {
    border-color: #3f3f46;
  }

  :global(.movie-time-tool__title) {
    font-weight: 700;
    color: #fff;
    font-size: 0.95rem;
    line-height: 1.2;
  }

  :global(.movie-time-tool__subtitle) {
    font-size: 0.78rem;
    color: #cbd5e1;
    margin-top: -0.2rem;
  }

  :global(.movie-time-tool__grid) {
    display: grid;
    gap: 0.55rem;
    grid-template-columns: 1fr 1fr;
  }

  :global(.movie-time-tool__input),
  :global(.movie-time-tool__textarea) {
    width: 100%;
    border-radius: 0.7rem;
    border: 1px solid rgba(251, 191, 36, 0.35);
    background: rgba(15, 23, 42, 0.45);
    color: #f8fafc;
    font-size: 0.87rem;
    line-height: 1.3;
    padding: 0.55rem 0.7rem;
  }

  :global(.movie-time-tool__input::placeholder),
  :global(.movie-time-tool__textarea::placeholder) {
    color: #94a3b8;
  }

  :global(.movie-time-tool__input:focus),
  :global(.movie-time-tool__textarea:focus) {
    outline: none;
    border-color: rgba(251, 191, 36, 0.85);
    box-shadow: 0 0 0 2px rgba(251, 191, 36, 0.18);
  }

  :global(.movie-time-tool__textarea) {
    resize: vertical;
    min-height: 5rem;
  }

  :global(.movie-time-tool__preview) {
    border-radius: 0.7rem;
    border: 1px solid rgba(251, 191, 36, 0.28);
    background: rgba(15, 23, 42, 0.42);
    color: #fde68a;
    font-size: 0.8rem;
    padding: 0.5rem 0.65rem;
    min-height: 2rem;
    display: flex;
    align-items: center;
  }

  @media (max-width: 760px) {
    :global(.movie-time-tool__grid) {
      grid-template-columns: 1fr;
    }
  }

  :global(.movie-card-tool) {
    border-radius: 0.9rem;
    border: 1px solid rgba(251, 191, 36, 0.38);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.22), rgba(251, 191, 36, 0) 58%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  :global(.dark .movie-card-tool) {
    border-color: rgba(251, 191, 36, 0.34);
  }

  :global(.movie-card-tool__title) {
    font-weight: 700;
    color: #fff;
    font-size: 0.95rem;
    line-height: 1.2;
  }

  :global(.movie-card-tool__subtitle) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.79rem;
    line-height: 1.4;
  }

  :global(.movie-card-tool__preview) {
    border-radius: 0.65rem;
    border: 1px solid rgba(251, 191, 36, 0.28);
    background: rgba(15, 23, 42, 0.4);
    color: #fde68a;
    font-size: 0.78rem;
    line-height: 1.35;
    padding: 0.5rem 0.65rem;
  }

  :global(.spoiler-marker-tool) {
    border-radius: 0.9rem;
    border: 1px solid rgba(148, 163, 184, 0.4);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(148, 163, 184, 0.24), rgba(148, 163, 184, 0) 58%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  :global(.spoiler-marker-tool--start) {
    border-color: rgba(148, 163, 184, 0.48);
  }

  :global(.spoiler-marker-tool--end) {
    border-color: rgba(94, 234, 212, 0.44);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(45, 212, 191, 0.2), rgba(45, 212, 191, 0) 58%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
  }

  :global(.spoiler-marker-tool--legacy) {
    border-color: rgba(251, 191, 36, 0.52);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(251, 191, 36, 0.2), rgba(251, 191, 36, 0) 58%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
  }

  :global(.dark .spoiler-marker-tool) {
    border-color: rgba(148, 163, 184, 0.45);
  }

  :global(.spoiler-marker-tool__title) {
    font-weight: 700;
    color: #fff;
    font-size: 0.95rem;
    line-height: 1.2;
  }

  :global(.spoiler-marker-tool__subtitle) {
    margin: 0;
    color: #cbd5e1;
    font-size: 0.78rem;
    line-height: 1.35;
  }

  :global(.spoiler-marker-tool__preview) {
    border-radius: 0.7rem;
    border: 1px solid rgba(148, 163, 184, 0.34);
    background: rgba(15, 23, 42, 0.42);
    color: #e2e8f0;
    font-size: 0.78rem;
    line-height: 1.35;
    padding: 0.52rem 0.66rem;
  }

  :global(.music-tool) {
    border-radius: 0.9rem;
    border: 1px solid rgba(14, 165, 233, 0.38);
    background:
      radial-gradient(120% 120% at 0% 0%, rgba(56, 189, 248, 0.2), rgba(56, 189, 248, 0) 60%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.9));
    color: #e2e8f0;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.55rem;
  }

  :global(.dark .music-tool) {
    border-color: rgba(56, 189, 248, 0.42);
  }

  :global(.music-tool__title) {
    font-weight: 700;
    color: #fff;
    font-size: 0.95rem;
    line-height: 1.2;
  }

  :global(.music-tool__subtitle) {
    margin: 0;
    color: #bae6fd;
    font-size: 0.78rem;
    line-height: 1.35;
  }

  :global(.music-tool__label) {
    color: #e0f2fe;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.01em;
  }

  :global(.music-tool__select),
  :global(.music-tool__input),
  :global(.music-tool__textarea) {
    width: 100%;
    border-radius: 0.7rem;
    border: 1px solid rgba(56, 189, 248, 0.34);
    background: rgba(15, 23, 42, 0.48);
    color: #f8fafc;
    font-size: 0.86rem;
    line-height: 1.3;
    padding: 0.55rem 0.68rem;
  }

  :global(.music-tool__select:focus),
  :global(.music-tool__input:focus),
  :global(.music-tool__textarea:focus) {
    outline: none;
    border-color: rgba(56, 189, 248, 0.85);
    box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
  }

  :global(.music-tool__input::placeholder),
  :global(.music-tool__textarea::placeholder) {
    color: #7dd3fc;
  }

  :global(.music-tool__textarea) {
    resize: vertical;
    min-height: 4rem;
  }

  :global(.music-tool__preview) {
    border-radius: 0.7rem;
    border: 1px solid rgba(56, 189, 248, 0.32);
    background: rgba(15, 23, 42, 0.44);
    color: #e0f2fe;
    font-size: 0.78rem;
    line-height: 1.35;
    padding: 0.52rem 0.66rem;
  }

  :global(.map-tool) {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    background: #ffffff;
  }

  :global(.dark .map-tool) {
    border-color: #4b5563;
    background: #1f2937;
  }

  :global(.map-tool__controls) {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  :global(.map-tool__label) {
    font-size: 0.8rem;
    font-weight: 600;
    color: #334155;
  }

  :global(.dark .map-tool__label) {
    color: #cbd5e1;
  }

  :global(.map-tool__input),
  :global(.map-tool__zoom) {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 0.5rem;
    background: #f8fafc;
    color: #0f172a;
    padding: 0.55rem 0.65rem;
    font-size: 0.875rem;
  }

  :global(.dark .map-tool__input),
  :global(.dark .map-tool__zoom) {
    border-color: #52525b;
    background: #111827;
    color: #e5e7eb;
  }

  :global(.map-tool__input:focus),
  :global(.map-tool__zoom:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
  }

  :global(.map-tool__zoom-row) {
    display: grid;
    grid-template-columns: 1fr minmax(90px, 120px);
    gap: 0.5rem;
    align-items: end;
  }

  :global(.map-tool__hint) {
    margin: 0;
    font-size: 0.78rem;
    color: #64748b;
  }

  :global(.dark .map-tool__hint) {
    color: #a1a1aa;
  }

  :global(.map-tool__preview) {
    border-radius: 0.75rem;
    overflow: hidden;
    border: 1px dashed #cbd5e1;
    background:
      linear-gradient(135deg, rgba(226, 232, 240, 0.7), rgba(248, 250, 252, 0.9));
    min-height: 220px;
  }

  :global(.dark .map-tool__preview) {
    border-color: #3f3f46;
    background:
      linear-gradient(135deg, rgba(39, 39, 42, 0.9), rgba(24, 24, 27, 0.92));
  }

  :global(.map-tool__preview.is-ready) {
    border-style: solid;
  }

  :global(.map-tool__frame) {
    width: 100%;
    height: 220px;
    border: 0;
    display: block;
  }

  :global(.image-compare-tool) {
    display: flex;
    flex-direction: column;
    gap: 0.85rem;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    background: #ffffff;
  }

  :global(.dark .image-compare-tool) {
    border-color: #4b5563;
    background: #1f2937;
  }

  :global(.image-compare-tool__hint) {
    margin: 0;
    font-size: 0.8rem;
    color: #64748b;
  }

  :global(.dark .image-compare-tool__hint) {
    color: #a1a1aa;
  }

  :global(.image-compare-tool__controls) {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.75rem;
  }

  :global(.image-compare-tool__side) {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.75rem;
    border: 1px solid #e2e8f0;
    border-radius: 0.6rem;
    background: #f8fafc;
  }

  :global(.dark .image-compare-tool__side) {
    border-color: #52525b;
    background: #111827;
  }

  :global(.image-compare-tool__side-title) {
    margin: 0;
    font-size: 0.8rem;
    font-weight: 600;
    color: #334155;
  }

  :global(.dark .image-compare-tool__side-title) {
    color: #cbd5e1;
  }

  :global(.image-compare-tool__upload) {
    border: 1px solid #d1d5db;
    border-radius: 0.5rem;
    background: #ffffff;
    color: #1f2937;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 0.55rem 0.75rem;
    cursor: pointer;
    transition: all 0.2s;
  }

  :global(.image-compare-tool__upload:hover) {
    background: #f8fafc;
    border-color: #94a3b8;
  }

  :global(.dark .image-compare-tool__upload) {
    border-color: #4b5563;
    background: #1f2937;
    color: #e5e7eb;
  }

  :global(.dark .image-compare-tool__upload:hover) {
    background: #374151;
    border-color: #64748b;
  }

  :global(.image-compare-tool__input),
  :global(.image-compare-tool__caption) {
    width: 100%;
    border: 1px solid #cbd5e1;
    border-radius: 0.5rem;
    background: #ffffff;
    color: #0f172a;
    padding: 0.55rem 0.65rem;
    font-size: 0.85rem;
  }

  :global(.dark .image-compare-tool__input),
  :global(.dark .image-compare-tool__caption) {
    border-color: #52525b;
    background: #111827;
    color: #e5e7eb;
  }

  :global(.image-compare-tool__input:focus),
  :global(.image-compare-tool__caption:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
  }

  :global(.image-compare-tool__preview) {
    position: relative;
    border-radius: 0.75rem;
    overflow: hidden;
    border: 1px solid #cbd5e1;
    background: #f8fafc;
    aspect-ratio: 16 / 9;
  }

  :global(.dark .image-compare-tool__preview) {
    border-color: #3f3f46;
    background: #18181b;
  }

  :global(.image-compare-tool__image) {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  :global(.image-compare-tool__overlay) {
    position: absolute;
    inset: 0;
    width: 100%;
    overflow: hidden;
    clip-path: inset(0 50% 0 0);
    -webkit-clip-path: inset(0 50% 0 0);
    pointer-events: none;
  }

  :global(.image-compare-tool__divider) {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 50%;
    width: 2px;
    background: rgba(255, 255, 255, 0.88);
    transform: translateX(-50%);
    box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.16);
    pointer-events: auto;
    cursor: ew-resize;
    touch-action: none;
    z-index: 2;
  }

  :global(.image-compare-tool__knob) {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 2rem;
    height: 2rem;
    border-radius: 999px;
    border: 1px solid rgba(148, 163, 184, 0.75);
    background: rgba(255, 255, 255, 0.95);
    transform: translate(-50%, -50%);
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.25);
  }

  :global(.dark .image-compare-tool__knob) {
    border-color: rgba(113, 113, 122, 0.9);
    background: rgba(24, 24, 27, 0.95);
  }

  :global(.image-compare-tool__placeholder) {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 0.75rem;
    font-size: 0.85rem;
    color: #475569;
    background: linear-gradient(135deg, rgba(241, 245, 249, 0.95), rgba(226, 232, 240, 0.9));
  }

  :global(.dark .image-compare-tool__placeholder) {
    color: #d4d4d8;
    background: linear-gradient(135deg, rgba(39, 39, 42, 0.95), rgba(24, 24, 27, 0.92));
  }

  :global(.image-compare-tool__preview.is-ready) {
    cursor: ew-resize;
    touch-action: none;
  }

  :global(.image-compare-tool__preview.is-dragging) {
    user-select: none;
  }

  :global(.image-compare-tool__caption) {
    min-height: 2.6rem;
    resize: vertical;
  }

  @media (max-width: 640px) {
    :global(.image-compare-tool__controls) {
      grid-template-columns: 1fr;
    }
  }

  :global(.gallery-loader) {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 0.5rem;
    z-index: 10;
  }

  :global(.dark .gallery-loader) {
    background: rgba(31, 41, 55, 0.8);
  }

  :global(.gallery-loader-spinner) {
    width: 40px;
    height: 40px;
    border: 4px solid #2563eb;
    border-radius: 50%;
    border-top-color: transparent;
    animation: spin 1s linear infinite;
  }

  :global(.dark .gallery-loader-spinner) {
    border-color: #60a5fa;
    border-top-color: transparent;
  }

  :global(.gallery-loader-text) {
    margin-top: 1rem;
    font-size: 1rem;
    font-weight: 500;
    color: #1f2937;
  }

  :global(.dark .gallery-loader-text) {
    color: #e5e7eb;
  }

  :global(.ce-header[contenteditable="true"][data-placeholder]) {
    margin-bottom: 0.7em;
  }

  :global(.ce-header[contenteditable="true"]) {
    outline: none;
  }

  :global(.ce-header) {
    padding: 0.4em 0;
    margin: 0;
    line-height: 1.25em;
    outline: none;
  }

  :global(h2.ce-header) {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
    line-height: 1.2;
  }

  :global(h3.ce-header) {
    font-size: 1.2rem;
    font-weight: 600;
    margin: 0;
    line-height: 1.2;
  }

  :global(.dark .ce-header) {
    color: #e5e7eb;
  }

  :global(.link-tool) {
    position: relative;
    width: 100%;
    padding: 0.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  :global(.link-tool__input) {
    width: 100%;
    padding: 0.5rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    background: white;
    color: #1f2937;
    font-size: 0.875rem;
    line-height: 1.25rem;
    margin-bottom: 0.5rem;
  }

  :global(.dark .link-tool__input) {
    background: #1f2937;
    border-color: #4b5563;
    color: #e5e7eb;
  }

  :global(.link-tool__input:focus) {
    outline: none;
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
  }

  :global(.dark .link-tool__input:focus) {
    border-color: #60a5fa;
    box-shadow: 0 0 0 2px rgba(96, 165, 250, 0.1);
  }

  :global(.link-suggestions) {
    position: absolute;
    top: calc(100% + 0.25rem);
    left: 0;
    right: 0;
    margin-top: 0.25rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    z-index: 10;
    max-height: 200px;
    overflow-y: auto;
  }

  :global(.dark .link-suggestions) {
    background: #1f2937;
    border-color: #4b5563;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
  }

  :global(.link-suggestions__title) {
    padding: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #6b7280;
    border-bottom: 1px solid #e5e7eb;
  }

  :global(.dark .link-suggestions__title) {
    color: #9ca3af;
    border-color: #4b5563;
  }

  :global(.link-suggestions__item) {
    padding: 0.5rem;
    font-size: 0.875rem;
    color: #1f2937;
    cursor: pointer;
    transition: all 0.2s;
  }

  :global(.dark .link-suggestions__item) {
    color: #e5e7eb;
  }

  :global(.link-suggestions__item:hover) {
    background: #f3f4f6;
  }

  :global(.dark .link-suggestions__item:hover) {
    background: #374151;
  }

  /* Стили для кастомного попапа ссылок */
  :global(.ce-link-popup) {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.5rem;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    font-family: inherit;
    font-size: 0.875rem;
    min-width: 250px;
    opacity: 0;
    transform: translateY(-4px);
    transition: opacity 0.2s ease-out, transform 0.2s ease-out;
    flex-wrap: wrap;
  }

  :global(.ce-link-popup.visible) {
    opacity: 1;
    transform: translateY(0);
  }

  :global(.dark .ce-link-popup) {
    background: #1f2937;
    border-color: #4b5563;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2);
  }

  :global(.ce-link-popup__input) {
    flex: 1;
    padding: 0.375rem 0.5rem;
    border: 1px solid #d1d5db;
    border-radius: 0.25rem;
    background: white;
    color: #1f2937;
    font-size: 0.875rem;
    line-height: 1.25rem;
    outline: none;
    transition: border-color 0.15s ease-in-out;
    min-width: 150px;
  }

  :global(.dark .ce-link-popup__input) {
    background: #374151;
    border-color: #6b7280;
    color: #e5e7eb;
  }

  :global(.ce-link-popup__input:focus) {
    border-color: #2563eb;
    box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.1);
  }

  :global(.dark .ce-link-popup__input:focus) {
    border-color: #60a5fa;
    box-shadow: 0 0 0 1px rgba(96, 165, 250, 0.1);
  }

  :global(.ce-link-popup__anchors),
  :global(.ce-link-popup__save),
  :global(.ce-link-popup__remove) {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid #d1d5db;
    border-radius: 0.25rem;
    background: white;
    color: #4b5563;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease-in-out;
    outline: none;
  }

  :global(.dark .ce-link-popup__anchors),
  :global(.dark .ce-link-popup__save),
  :global(.dark .ce-link-popup__remove) {
    background: #374151;
    border-color: #6b7280;
    color: #e5e7eb;
  }

  :global(.ce-link-popup__anchors:hover) {
    background: #f3f4f6;
    border-color: #8b5cf6;
    color: #8b5cf6;
  }

  :global(.dark .ce-link-popup__anchors:hover) {
    background: #4b5563;
    border-color: #a78bfa;
    color: #a78bfa;
  }

  :global(.ce-link-popup__save:hover) {
    background: #f3f4f6;
    border-color: #2563eb;
    color: #2563eb;
  }

  :global(.dark .ce-link-popup__save:hover) {
    background: #4b5563;
    border-color: #60a5fa;
    color: #60a5fa;
  }

  :global(.ce-link-popup__remove:hover) {
    background: #fef2f2;
    border-color: #ef4444;
    color: #ef4444;
  }

  :global(.dark .ce-link-popup__remove:hover) {
    background: #7f1d1d;
    border-color: #dc2626;
    color: #dc2626;
  }

  :global(.ce-link-popup__anchors:active),
  :global(.ce-link-popup__save:active),
  :global(.ce-link-popup__remove:active) {
    transform: scale(0.95);
  }

  /* Стили для списка якорей в inline popup */
  :global(.ce-link-popup .ce-link-suggestions) {
    position: absolute;
    top: calc(100% + 0.25rem);
    left: 0;
    right: 0;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 0.375rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    z-index: 20;
    max-height: 200px;
    overflow-y: auto;
  }

  :global(.dark .ce-link-popup .ce-link-suggestions) {
    background: #1f2937;
    border-color: #4b5563;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
  }

  :global(.ce-link-popup .ce-link-suggestions__title) {
    padding: 0.5rem;
    font-size: 0.875rem;
    font-weight: 500;
    color: #6b7280;
    border-bottom: 1px solid #e5e7eb;
  }

  :global(.dark .ce-link-popup .ce-link-suggestions__title) {
    color: #9ca3af;
    border-color: #4b5563;
  }

  :global(.ce-link-popup .ce-link-suggestions__item) {
    padding: 0.5rem;
    font-size: 0.875rem;
    color: #1f2937;
    cursor: pointer;
    transition: all 0.2s;
  }

  :global(.dark .ce-link-popup .ce-link-suggestions__item) {
    color: #e5e7eb;
  }

  :global(.ce-link-popup .ce-link-suggestions__item:hover) {
    background: #f3f4f6;
  }

  :global(.dark .ce-link-popup .ce-link-suggestions__item:hover) {
    background: #374151;
  }
  
  /* Стили для иконок в тулбаре */
  :global(.ce-toolbar__plus img),
  :global(.ce-toolbar__settings-btn img),
  :global(.ce-conversion-tool img),
  :global(.ce-inline-toolbar__dropdown img),
  :global(.ce-inline-toolbar__buttons img) {
    width: 16px;
    height: 16px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  :global(.ce-toolbar__plus:hover img),
  :global(.ce-toolbar__settings-btn:hover img),
  :global(.ce-conversion-tool:hover img),
  :global(.ce-inline-toolbar__dropdown:hover img),
  :global(.ce-inline-toolbar__buttons button:hover img) {
    opacity: 1;
  }

  :global(.ce-toolbar__actions img) {
    width: 14px;
    height: 14px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  :global(.ce-toolbar__actions button:hover img) {
    opacity: 1;
  }

  :global(.ce-toolbar__settings-btn[draggable='true']) {
    cursor: grab;
  }

  :global(.ce-toolbar__settings-btn.editorjs-dnd-dragging) {
    cursor: grabbing;
  }

  :global(.ce-block.comuna-block-dragging) {
    opacity: 0.65;
  }

  :global(.ce-block.comuna-drop-before),
  :global(.ce-block.comuna-drop-after) {
    border-radius: 0.5rem;
  }

  :global(.ce-block.comuna-drop-before) {
    box-shadow: inset 0 3px 0 #3b82f6;
  }

  :global(.ce-block.comuna-drop-after) {
    box-shadow: inset 0 -3px 0 #3b82f6;
  }

  :global(.dark .ce-block.comuna-drop-before) {
    box-shadow: inset 0 3px 0 #60a5fa;
  }

  :global(.dark .ce-block.comuna-drop-after) {
    box-shadow: inset 0 -3px 0 #60a5fa;
  }

  :global(.ce-block__content img) {
    max-width: 100%;
    height: auto;
  }

  :global(.ce-block--selected .ce-block__content img) {
    opacity: 0.7;
  }

  /* Стили для иконок в тунах блока */
  :global(.ce-tune-move-up img),
  :global(.ce-tune-move-down img) {
    width: 14px;
    height: 14px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  :global(.ce-tune-move-up:hover img),
  :global(.ce-tune-move-down:hover img) {
    opacity: 1;
  }

  /* Стили для иконок в инлайн тулбаре */
  :global(.ce-inline-tool img) {
    width: 14px;
    height: 14px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  :global(.ce-inline-tool:hover img) {
    opacity: 1;
  }

  :global(.ce-inline-tool--active img) {
    opacity: 1;
  }

  /* Стили для иконок в конвертере */
  :global(.ce-conversion-tool img) {
    margin-right: 8px;
  }

  :global(.ce-conversion-tool--focused img) {
    opacity: 1;
  }

  /* Стили для иконок в тулбоксе */
  :global(.ce-toolbox__button img) {
    width: 16px;
    height: 16px;
    opacity: 0.7;
    transition: opacity 0.2s ease;
  }

  :global(.ce-toolbox__button:hover img) {
    opacity: 1;
  }

  :global(.ce-toolbox__button--active img) {
    opacity: 1;
  }

  /* Темная тема для иконок */
  :global(.dark .ce-toolbar__plus img),
  :global(.dark .ce-toolbar__settings-btn img),
  :global(.dark .ce-conversion-tool img),
  :global(.dark .ce-inline-toolbar__dropdown img),
  :global(.dark .ce-inline-toolbar__buttons img),
  :global(.dark .ce-toolbar__actions img),
  :global(.dark .ce-tune-move-up img),
  :global(.dark .ce-tune-move-down img),
  :global(.dark .ce-inline-tool img),
  :global(.dark .ce-toolbox__button img) {
    filter: invert(1);
  }

  /* Стили для иконок в тулбаре */
  :global(.ce-block__content a),
  :global(.ce-block a),
  :global(.codex-editor a) {
    color: #0000EE !important;
    text-decoration: underline !important;
    cursor: pointer;
  }

  :global(.ce-block__content a:hover),
  :global(.ce-block a:hover),
  :global(.codex-editor a:hover) {
    color: #0000EE !important;
    text-decoration: underline !important;
  }

  :global(.dark .ce-toolbar__plus svg) {
    filter: none !important;
    color: #e4e4e7 !important;
    fill: #e4e4e7 !important;
    stroke: #e4e4e7 !important;
  }

  :global(.dark .ce-toolbar__plus:hover svg) {
    color: #000 !important;
    fill: #000 !important;
    stroke: #000 !important;
  }

  :global(.link-tool__row) {
    display: flex;
    gap: 0.5rem;
    width: 100%;
  }

  :global(.link-tool__input--url) {
    flex: 1;
    margin-bottom: 0;
  }

  :global(.link-tool__input--select) {
    width: 200px;
    margin-bottom: 0;
  }
</style> 
