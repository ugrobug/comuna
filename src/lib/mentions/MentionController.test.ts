import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MentionController, MentionSyntax } from './MentionController'

const user = {kind: 'user' as const, id: 7, handle: 'anna', label: 'Анна Петрова', url: '/id7?mention=user.7'}
const community = {kind: 'comun' as const, id: 9, handle: 'kino', label: 'Кино', url: '/comuns/kino?mention=comun.9'}
let controller: MentionController
let root: HTMLDivElement
let input: HTMLTextAreaElement
const flush = async () => { await vi.advanceTimersByTimeAsync(181) }
const type = (value: string) => {
  input.value = value
  input.setSelectionRange(value.length, value.length)
  input.dispatchEvent(new Event('input', {bubbles: true}))
}
beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: true, json: async () => ({items: [user, community]})}))
  Element.prototype.scrollIntoView = vi.fn()
  root = document.createElement('div')
  input = document.createElement('textarea')
  root.append(input)
  document.body.append(root)
  controller = new MentionController(root, {enabled:true, token:'test', mode:'markdown'}, '/api/mentions/suggest/')
  input.focus()
})
afterEach(() => {controller.destroy(); root.remove(); vi.useRealTimers(); vi.unstubAllGlobals()})

describe('mention syntax and interaction', () => {
  it('supports full names, nicknames, Cyrillic and does not trigger in emails', () => {
    expect(MentionSyntax.query('Привет @Анна Пет')).toEqual({start:7, query:'Анна Пет'})
    expect(MentionSyntax.query('@alina_art')).toEqual({start:0, query:'alina_art'})
    expect(MentionSyntax.query('a@b.ru')).toBeNull()
    expect(MentionSyntax.query('@'+'a'.repeat(81))).toBeNull()
  })
  it('debounces typing and inserts selected user with keyboard without deleting suffix', async () => {
    type('Привет @а'); type('Привет @ан')
    expect(fetch).not.toHaveBeenCalled()
    await flush()
    expect(fetch).toHaveBeenCalledTimes(1)
    input.dispatchEvent(new KeyboardEvent('keydown', {key:'Enter',bubbles:true,cancelable:true}))
    expect(input.value).toBe('Привет [@anna](/id7?mention=user.7) ')
    expect(document.querySelector('[role=listbox]')?.hasAttribute('hidden')).toBe(true)
  })
  it('allows mouse selection of a community and safely escapes markdown labels', async () => {
    type('@ки'); await flush()
    document.querySelectorAll('[role=option]')[1].dispatchEvent(new Event('click',{bubbles:true,cancelable:true}))
    expect(input.value).toBe('[@Кино](/comuns/kino?mention=comun.9) ')
    expect(MentionSyntax.markdown({...community,label:'[Кино]'})).toContain('\\[Кино\\]')
  })
  it('keeps text after caret and does not replace a changed selection', async () => {
    input.value='Привет @ан, завтра'
    input.setSelectionRange(10,10)
    input.dispatchEvent(new Event('input',{bubbles:true}))
    await flush()
    input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}))
    expect(input.value).toBe('Привет [@anna](/id7?mention=user.7) , завтра')
  })
  it('cancels requests on escape and never renders stale results', async () => {
    let resolve!: (value: Response | PromiseLike<Response>) => void
    vi.mocked(fetch).mockImplementationOnce(() => new Promise(r => { resolve=r }))
    type('@ан'); await flush()
    input.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))
    resolve({ok:true,json:async()=>({items:[user]})} as Response)
    await flush()
    expect(document.querySelector('[role=listbox]')?.hasAttribute('hidden')).toBe(true)
  })
  it('does not send queries during composition, in code, or without login', async () => {
    type('`@ан'); await flush()
    input.dispatchEvent(new Event('compositionstart',{bubbles:true})); type('@ан'); await flush()
    input.dispatchEvent(new Event('compositionend',{bubbles:true})); controller.update({enabled:true,token:null,mode:'markdown'})
    await flush()
    expect(fetch).not.toHaveBeenCalled()
  })
  it('warns instead of silently adding a twenty-first recipient', async () => {
    const existing = Array.from({length:20}, (_,i)=>`[@x](/id${100+i}?mention=user.${100+i})`).join(' ')
    type(`${existing} @ан`); await flush()
    input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}))
    expect(input.value).toBe(`${existing} @ан`)
    expect(document.querySelector('[role=status]')?.textContent).toContain('до 20')
  })
  it('cleans up dropdown and listeners on editor destruction', async () => {
    type('@ан'); controller.destroy(); await flush()
    expect(document.querySelector('[role=listbox]')).toBeNull()
    expect(fetch).not.toHaveBeenCalled()
  })
  it('inserts HTML anchor in rich text across nested formatting and preserves trailing text', async () => {
    controller.destroy()
    root.innerHTML='<div contenteditable="true" tabindex="0">Привет @<b>ан</b>, завтра</div>'
    const editable=root.firstElementChild as HTMLElement
    controller=new MentionController(root,{enabled:true,token:'test',mode:'html'},'/api/mentions/suggest/')
    Range.prototype.getBoundingClientRect=()=>new DOMRect(0,0,100,20)
    editable.focus()
    const range=document.createRange()
    range.setStart(editable.querySelector('b')!.firstChild!,2);range.collapse(true)
    window.getSelection()!.removeAllRanges();window.getSelection()!.addRange(range)
    editable.dispatchEvent(new Event('input',{bubbles:true}));await flush()
    editable.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}))
    expect(editable.querySelector('a')?.getAttribute('href')).toBe(user.url)
    expect(editable.textContent).toBe('Привет @anna\u00a0, завтра')
  })
})
