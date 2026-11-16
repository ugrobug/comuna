import type { Column, Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import pdfMake from 'pdfmake/build/pdfmake'
import fonts from 'pdfmake/build/vfs_fonts'
import type { ExploreNode } from './types'
import { HobbySelection, type SelectedHobby } from './HobbySelection'
import type { HobbySteps } from './HobbySteps'
import { getBackendBaseUrl } from '$lib/api/backend'

/** Fonts, brand artwork and covers are loaded only when a selection is exported. */
export class HobbyPdf {
  constructor(private readonly steps: HobbySteps) {}

  private async masthead(): Promise<Content> {
    const response = await fetch('/logo_512.png', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error('Не удалось загрузить логотип Тамбура.')
    const blob = await response.blob()
    const logo = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as string)
      reader.onerror = () => reject(reader.error)
      reader.readAsDataURL(blob)
    })
    return { columns: [
      {image: logo, width: 38},
      {stack: [
        {text: 'Тамбур', fontSize: 19, bold: true, color: '#251943'},
        {text: 'Сайт с сообществами по хобби', fontSize: 10, color: '#575365'},
      ]},
    ], columnGap: 8 }
  }

  private async cover(node: ExploreNode): Promise<Column | null> {
    let url: string | undefined
    try {
      const response = await fetch(getBackendBaseUrl() + '/api/explore/nodes/' + node.id + '/cover/', {
        signal: AbortSignal.timeout(8000),
      })
      if (!response.ok) throw new Error()
      url = URL.createObjectURL(await response.blob())
      const image = new Image()
      image.src = url
      await image.decode()
      const canvas = document.createElement('canvas')
      canvas.width = image.naturalWidth
      canvas.height = image.naturalHeight
      const ctx = canvas.getContext('2d')!
      ctx.fillStyle = 'white'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(image, 0, 0)
      return { image: canvas.toDataURL('image/jpeg', 0.82), width: 104 }
    } catch { return null }
    finally { if (url) URL.revokeObjectURL(url) }
  }

  private async card({hobby: node, communities}: SelectedHobby): Promise<Content[]> {
    const cover = node.image_url ? await this.cover(node) : null
    const heading: Column = { width: '*', stack: [
      { text: node.title, fontSize: 19, bold: true, color: '#28203e' },
      { text: HobbySelection.description(node), margin: [0, 4, 0, 0] },
    ] }
    const content: Content[] = [{ unbreakable: true, margin: [0, 16, 0, 0], stack: [
      { canvas: [{ type: 'line', x1: 0, x2: 503, y1: 0, y2: 0, lineWidth: 1, lineColor: '#cec6e2' }] },
      { columns: cover ? [cover, heading] : [heading], columnGap: 16, margin: [0, 11, 0, 0] },
    ] }]
    if (node.try_description || node.try_step) {
      content.push({ text: 'Как попробовать', style: 'section' })
      if (node.try_description) content.push({ text: node.try_description })
      if (node.try_step) {
        const box: Column = { width: 14, canvas: [
          { type: 'rect', x: 1, y: 2, w: 10, h: 10, lineWidth: 1 },
          ...(this.steps.isDone(node) ? [{ type: 'polyline' as const, points: [{x:3,y:7},{x:5,y:10},{x:10,y:4}], lineWidth: 1.5 }] : []),
        ] }
        content.push({ columns: [box, {text: node.try_step}], columnGap: 5, margin: [0, 8, 0, 0] })
      }
    }
    communities.forEach((club, index) => {
      const stack: Content[] = []
      if (index === 0) stack.push({ text: 'Сообщества', style: 'section' })
      stack.push({ text: club.title, bold: true, link: new URL(club.community_url!, window.location.origin).href,
        decoration: 'underline', color: '#54309b' })
      const description = HobbySelection.description(club)
      if (description) stack.push({text: description, color: '#524e5e', fontSize: 10, margin: [0, 2, 0, 0]})
      content.push({stack, unbreakable: true, margin: [0, 4, 0, 4]})
    })
    if (!communities.length) {
      content.push({text: 'Создать сообщество по этому хобби', color: '#54309b', decoration: 'underline',
        link: new URL('/comuns?' + new URLSearchParams({create: '1', name: node.title}), window.location.origin).href,
        margin: [0, 8, 0, 0]})
    }
    return content
  }

  async download(picks: SelectedHobby[]) {
    const content: Content[] = [await this.masthead(),
      {text: 'Моя подборка хобби', fontSize: 27, bold: true, color: '#251943', margin: [0, 18, 0, 0]}]
    for (let i = 0; i < picks.length; i += 3) {
      const group = await Promise.all(picks.slice(i, i + 3).map(item => this.card(item)))
      content.push(...group.flat())
    }
    const doc: TDocumentDefinitions = {
      info: {title: 'Мои хобби — Тамбур'}, pageSize: 'A4', pageMargins: [46, 38, 46, 46],
      defaultStyle: {fontSize: 11, lineHeight: 1.25, color: '#242536'},
      styles: {section: {fontSize: 12, bold: true, color: '#392955', margin: [0, 9, 0, 4]}},
      footer: (page, pages) => ({ text: page + ' / ' + pages, alignment: 'right', margin: [0, 6, 46, 0], fontSize: 9 }),
      content,
    }
    await new Promise<void>(resolve => pdfMake.createPdf(doc, undefined, undefined, fonts).download('Мои хобби.pdf', resolve))
  }
}
