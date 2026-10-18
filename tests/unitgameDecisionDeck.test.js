import { describe, expect, it } from 'vitest'
import { DecisionDeck } from '../backend/unitgame_app/static/unitgame_app/decision-deck.js'
import { deck } from '../backend/unitgame_app/static/unitgame_app/cards.js'

const ordered = (cards) => cards
const resolve = (choice, state) => ({
  instant: { ...choice?.instant, ...choice?.instantFn?.(state) },
  after: { ...choice?.after, ...choice?.afterFn?.(state) },
})
const saving = { id: 'saving', right: { after: { fixed: -30 } } }
const other = { id: 'other', right: { instant: { cost: -5, fixed: 10 } } }

describe('Unit Game decision eligibility', () => {
  it.each([0, 19, 19.99])('skips fixed-cost reductions at %s rubles', (fixed) => {
    const cards = new DecisionDeck([saving, other], ordered, resolve)
    expect(cards.draw({ fixed }).id).toBe('other')
  })

  it.each([20, 21, 70])('keeps reductions available at %s rubles', (fixed) => {
    const cards = new DecisionDeck([saving, other], ordered, resolve)
    expect(cards.draw({ fixed }).id).toBe('saving')
  })

  it('rechecks queued cards after costs drop and restores them after costs rise', () => {
    const cards = new DecisionDeck([other, saving, { id: 'third' }], ordered, resolve)
    expect(cards.draw({ fixed: 70 }).id).toBe('other')
    expect(cards.draw({ fixed: 0 }).id).toBe('third')
    expect(cards.draw({ fixed: 20 }).id).toBe('saving')
  })

  it('refills without offering a blocked card or mutating the source', () => {
    const source = [saving, other]
    const cards = new DecisionDeck(source, ordered, resolve)
    for (let i = 0; i < 100; i++) expect(cards.draw({ fixed: 0 }).id).toBe('other')
    expect(source).toEqual([saving, other])
    cards.reset()
    expect(cards.draw({ fixed: 70 }).id).toBe('saving')
  })

  it('checks both choices, both timings and state-dependent effects', () => {
    const blocked = [
      { left: { instant: { fixed: -1 } } },
      { left: { after: { fixed: -1 } } },
      { right: { instantFn: (state) => ({ fixed: -state.fixed }) } },
      { right: { afterFn: () => ({ fixed: -1 }) } },
    ]
    const cards = new DecisionDeck([...blocked, other], ordered, resolve)
    expect(cards.draw({ fixed: 19 }).id).toBe('other')
  })

  it('uses the resolved effect when a formula overrides a static delta', () => {
    const overridden = { id: 'overridden', right: {
      instant: { fixed: -20 }, instantFn: () => ({ fixed: 5 }),
    } }
    const cards = new DecisionDeck([overridden, other], ordered, resolve)
    expect(cards.draw({ fixed: 0 }).id).toBe('overridden')
  })

  it('fails explicitly for an empty or fully blocked deck instead of looping', () => {
    for (const source of [[], [saving]]) {
      const cards = new DecisionDeck(source, ordered, resolve)
      expect(() => cards.draw({ fixed: 0 })).toThrow('No eligible decisions')
    }
  })

  it('covers the real deck, including a reduction on the No choice', () => {
    const state = { fixed: 0, balance: 2200, visitors: 900, conversion: 0.01, price: 100, cost: 90, cac: 25 }
    const expectedBlocked = [
      'cut_fixed', 'cut_people', 'cost_optimization', 'outsourcing', 'energy_audit',
      'tax_scheme', 'support_bot', 'lean_inventory', 'salary_review',
      'internal_tools', 'warehouse_robot', 'partial_remote',
    ]
    const cards = new DecisionDeck(deck, ordered, resolve)
    const seen = new Set()
    for (let i = 0; i < 2 * deck.length; i++) seen.add(cards.draw(state).id)
    expect(deck.filter(card => !seen.has(card.id)).map(card => card.id).sort())
      .toEqual(expectedBlocked.sort())
    const unfiltered = new DecisionDeck(deck, ordered, resolve)
    expect(Array.from({ length: deck.length }, () => unfiltered.draw({ ...state, fixed: 20 }).id))
      .toEqual(deck.map(card => card.id))
  })
})
