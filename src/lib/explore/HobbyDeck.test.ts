import { describe, it, expect } from 'vitest'
import { HobbyDeck, HobbyHistory } from './HobbyDeck'
import type { ExploreNode } from './types'
const hobby = (id: number, property_ids: number[], extra: Partial<ExploreNode> = {}): ExploreNode => ({
  id, title: String(id), property_ids, description: '', kind: 'element', is_active: true, subscribed: false,
  community_id: null, community_url: null, show_properties: false, ...extra
})
const nodes = [hobby(1,[1,2]), hobby(2,[1,2]), hobby(3,[1]), hobby(4,[3]), hobby(5,[],{kind:'community'}), hobby(6,[],{is_active:false})]
function setup() {
  const data = new Map<string,string>()
  const store = {getItem: (k:string) => data.get(k) ?? null, setItem: (k:string,v:string) => {data.set(k,v)}}
  const deck = (key = 'guest') => new HobbyDeck(nodes, new HobbyHistory(key,store), () => .1)
  return { deck, data }
}
describe('hobby discovery', () => {
  it('lowers related options after a pass without excluding them', () => {
    const d = setup().deck(); expect(d.remaining).toBe(4)
    d.choose(1,false); expect(d.next()?.id).toBe(4); d.choose(4,false)
    expect(d.next()?.id).toBe(3); d.choose(3,false); expect(d.next()?.id).toBe(2)
    d.choose(2,false); expect(d.next()).toBeNull()
  })
  it('likes favor matching features, survive a reopen and stay scoped to the profile', () => {
    const {deck} = setup(); const d = deck()
    d.choose(1,true); expect(d.choose(1,false)).toBe(false)
    expect(deck().next()?.id).toBe(2); expect(deck().picked.map(n => n.id)).toEqual([1])
    expect(deck('account:12').picked).toEqual([]); deck().reset(); expect(deck().remaining).toBe(4)
  })
  it('ignores stale, invalid and duplicate entries; remains usable without storage', () => {
    const {deck,data} = setup(); data.set('guest','[1,-1,999,5,6,"3",null,0]')
    expect(deck().remaining).toBe(3); data.set('guest','corrupt'); expect(deck().remaining).toBe(4)
    const off = () => {throw Error()}; const d=new HobbyDeck(nodes,new HobbyHistory('x',{getItem:off,setItem:off}))
    expect(d.choose(1,false)).toBe(true); expect(d.remaining).toBe(3)
  })
})
