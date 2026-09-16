import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createImageTool } from './createImageTool'
import { getClipboardImages } from './imageClipboard'

const file = new File(['image'], 'picture.png', { type: 'image/png' })
const deferred = () => {
  let resolve!: (value: { url: string; useWebp: boolean }) => void
  let reject!: (error: Error) => void
  const promise = new Promise<{ url: string; useWebp: boolean }>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const setup = (upload = vi.fn(async (_file: File) => ({ url: '/media/image.webp', useWebp: false }))) => {
  const pending = vi.fn()
  const changed = vi.fn()
  const Tool = createImageTool({
    icon: '', upload, onError: (error) => (error as Error).message, onPendingChange: pending,
    showPostSettings: () => false, getPreview: () => '', setPreview: vi.fn(),
  })
  return { Tool, pending, changed }
}

beforeEach(() => {
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: vi.fn(() => 'blob:local-preview'), revokeObjectURL: vi.fn() }))
})
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

describe('editor image uploads', () => {
  it('shows a pasted image before the server responds and saves only the final URL', async () => {
    const request = deferred()
    const { Tool, pending, changed } = setup(vi.fn(() => request.promise))
    const picker = vi.spyOn(HTMLInputElement.prototype, 'click')
    const tool = new Tool({ data: { uploadFile: file }, block: { dispatchChange: changed } })
    const view = tool.render()
    tool.appendCallback()
    expect(picker).not.toHaveBeenCalled()
    expect(view.querySelector('img')?.getAttribute('src')).toBe('blob:local-preview')
    expect(view.getAttribute('aria-busy')).toBe('true')
    let saved = false
    const saving = tool.save().then(data => { saved = true; return data })
    await Promise.resolve()
    expect(saved).toBe(false)
    request.resolve({ url: '/media/uploaded.webp', useWebp: false })
    const data = await saving
    expect(data.file.url).toBe('/media/uploaded.webp')
    expect(JSON.stringify(data)).not.toContain('blob:')
    expect(data).not.toHaveProperty('uploadFile')
    expect(changed).toHaveBeenCalled()
    expect(pending.mock.calls).toEqual([[1], [-1]])
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:local-preview')
  })

  it('uploads another paste while the first one is still pending', async () => {
    const request = deferred()
    const upload = vi.fn(() => request.promise)
    const { Tool } = setup(upload)
    const first = new Tool({ data: { uploadFile: file } })
    const second = new Tool({ data: { uploadFile: file } })
    first.render(); second.render()
    expect(upload).toHaveBeenCalledTimes(2)
    request.resolve({ url: '/media/image.webp', useWebp: false })
    await Promise.all([first.save(), second.save()])
  })

  it('keeps the previous image when replacement fails and allows a retry', async () => {
    const upload = vi.fn().mockRejectedValueOnce(new Error('Нет соединения')).mockResolvedValue({ url: '/media/new.webp', useWebp: false })
    const { Tool, pending } = setup(upload)
    const tool = new Tool({ data: { file: { url: '/media/old.webp', alt: 'caption', title: '' } } })
    const view = tool.render()
    await tool.uploadFile(file)
    expect((await tool.save()).file.url).toBe('/media/old.webp')
    expect(view.querySelector('[role="alert"]')?.textContent).toBe('Нет соединения')
    expect(view.querySelector('button')?.disabled).toBe(false)
    await tool.uploadFile(file)
    expect((await tool.save()).file.url).toBe('/media/new.webp')
    expect(pending.mock.calls).toEqual([[1], [-1], [1], [-1]])
  })

  it('supports an HTML-only image paste without opening the file picker', async () => {
    const { Tool } = setup()
    const tool = new Tool({})
    const picker = vi.spyOn(HTMLInputElement.prototype, 'click')
    tool.render()
    const image = document.createElement('img')
    image.src = 'https://example.com/photo.jpg'
    await tool.onPaste({ type: 'tag', detail: { data: image } })
    expect((await tool.save()).file.url).toBe(image.src)
    expect(picker).not.toHaveBeenCalled()
  })

  it('does not accept unsafe HTML image URLs', async () => {
    const { Tool } = setup()
    const tool = new Tool({}); tool.render()
    const image = document.createElement('img')
    image.setAttribute('src', 'javascript:alert(1)')
    await tool.onPaste({ type: 'tag', detail: { data: image } })
    expect((await tool.save()).file.url).toBe('')
  })

  it('ignores a completed upload after its block was removed', async () => {
    const request = deferred()
    const { Tool, changed } = setup(vi.fn(() => request.promise))
    const tool = new Tool({ data: { uploadFile: file }, block: { dispatchChange: changed } })
    tool.render(); tool.destroy()
    request.resolve({ url: '/media/deleted.webp', useWebp: false })
    expect((await tool.save()).file.url).toBe('')
    expect(changed).not.toHaveBeenCalled()
  })
})

describe('clipboard extraction', () => {
  it('extracts all image files without duplicating the items/files views', () => {
    const second = new File(['image'], 'two.jpg', { type: 'image/jpeg' })
    const clipboard = { items: [file, second].map(f => ({ kind: 'file', getAsFile: () => f })), files: [file, second] } as unknown as DataTransfer
    expect(getClipboardImages(clipboard)).toEqual([file, second])
  })
  it('falls back to files and leaves text-only paste alone', () => {
    expect(getClipboardImages({ items: [], files: [file] } as unknown as DataTransfer)).toEqual([file])
    expect(getClipboardImages({ items: [], files: [] } as unknown as DataTransfer)).toEqual([])
    expect(getClipboardImages(null)).toEqual([])
  })
})
