import { describe, expect, it } from 'vitest'
import { GraphPinch } from './GraphPinch'

describe('graph pinch zoom', () => {
  it('zooms around the point between the fingers while allowing two-finger panning', () => {
    const gesture = new GraphPinch({ x: 50, y: 100 }, { x: 150, y: 100 }, { scale: .5, tx: 20, ty: -30 })
    const view = gesture.move({ x: 40, y: 140 }, { x: 240, y: 140 })
    expect(view.scale).toBe(1)
    expect(160 * view.scale + view.tx).toBe(140)
    expect(260 * view.scale + view.ty).toBe(140)
    const smaller = gesture.move({ x: 75, y: 100 }, { x: 125, y: 100 })
    expect(smaller.scale).toBe(.25)
    expect(160 * smaller.scale + smaller.tx).toBe(100)
  })
  it('does not accumulate zoom between pointer updates', () => {
    const gesture = new GraphPinch({ x: 0, y: 0 }, { x: 100, y: 0 }, { scale: 1, tx: 0, ty: 0 })
    gesture.move({ x: 0, y: 0 }, { x: 200, y: 0 })
    expect(gesture.move({ x: 0, y: 0 }, { x: 100, y: 0 })).toEqual({ scale: 1, tx: 0, ty: 0 })
  })
  it('keeps zoom bounded and finite even when fingers meet', () => {
    const gesture = new GraphPinch({ x: 100, y: 100 }, { x: 100, y: 100 }, { scale: 1, tx: 20, ty: 30 })
    expect(gesture.move({ x: 100, y: 100 }, { x: 100, y: 100 }).scale).toBe(.03)
    const view = gesture.move({ x: 0, y: 0 }, { x: 10000, y: 10000 })
    expect(view.scale).toBe(3)
    expect(Object.values(view).every(Number.isFinite)).toBe(true)
  })
})
