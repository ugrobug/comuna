import type { Column, Content, TDocumentDefinitions } from 'pdfmake/interfaces'
import pdfMake from 'pdfmake/build/pdfmake'
import fonts from 'pdfmake/build/vfs_fonts'
import type { ExploreData, ExploreNode } from './types'
import type { HobbySteps } from './HobbySteps'
import { getBackendBaseUrl } from '$lib/api/backend'

/** Loaded only on export. Resolve both edge directions once for the whole selection. */
export class HobbyPdf {
  private readonly communities = new Map<number, ExploreNode[]>()

  constructor(data: ExploreData, private readonly steps: HobbySteps) {
    const nodes = new Map(data.nodes.map(node => [node.id, node]))
    for (const edge of data.edges) {
      const a = nodes.get(edge.source), b = nodes.get(edge.target)
      if (!a?.is_active || !b?.is_active || a.kind === b.kind) continue
      const [hobby, club] = a.kind === 'element' ? [a, b] : [b, a]
      if (!club.community_url) continue
      const clubs = this.communities.get(hobby.id) ?? []
      clubs.push(club)
      this.communities.set(hobby.id, clubs)
    }
  }

  private async cover(node: ExploreNode): Promise<Content> {
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
      return { image: canvas.toDataURL('image/jpeg', 0.82), fit: [475, 210], margin: [0, 0, 0, 14] }
    } catch { return { text: 'Обложка временно недоступна.', color: '#616777', margin: [0, 0, 0, 8] } }
    finally { if (url) URL.revokeObjectURL(url) }
  }

  private async card(node: ExploreNode, index: number): Promise<Content[]> {
    const content: Content[] = [
      { text: 'Тамбур  /  Мои хобби', color: '#65549b', pageBreak: index ? 'before' : undefined },
      { text: node.title, fontSize: 23, bold: true, margin: [0, 7, 0, 14] },
    ]
    if (node.image_url) content.push(await this.cover(node))
    if (node.description) content.push({ text: node.description })
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
    const clubs = (this.communities.get(node.id) ?? []).sort((a,b) =>
      (b.subscribers_count ?? 0) - (a.subscribers_count ?? 0) || a.title.localeCompare(b.title, 'ru') || a.id - b.id)
    if (clubs.length) content.push({ text: 'Сообщества', style: 'section' })
    for (const club of clubs.slice(0, 3)) content.push({
      text: club.title, link: new URL(club.community_url!, window.location.origin).href,
      decoration: 'underline', color: '#554291', margin: [0, 2, 0, 3],
    })
    return content
  }

  async download(picks: ExploreNode[]) {
    const content: Content[] = []
    for (let i = 0; i < picks.length; i += 3) {
      const group = await Promise.all(picks.slice(i, i + 3).map((node, j) => this.card(node, i + j)))
      content.push(...group.flat())
    }
    const doc: TDocumentDefinitions = {
      info: {title: 'Мои хобби — Тамбур'}, pageSize: 'A4', pageMargins: [46, 38, 46, 46],
      defaultStyle: {fontSize: 11, lineHeight: 1.25, color: '#242536'},
      styles: {section: {fontSize: 15, bold: true, margin: [0, 16, 0, 6]}},
      footer: (page, pages) => ({ text: page + ' / ' + pages, alignment: 'right', margin: [0, 6, 46, 0], fontSize: 9 }),
      content,
    }
    await new Promise<void>(resolve => pdfMake.createPdf(doc, undefined, undefined, fonts).download('Мои хобби.pdf', resolve))
  }
}
