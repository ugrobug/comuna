type Point = { x: number; y: number }
type Size = { width: number; height: number }
export type PopoverBounds = Point & Size

/** Position a card beside its node, flipping at the canvas edges. */
export class NodePopover {
  static bounds(canvas: Size, top: number, left = 10, visible: PopoverBounds = { x: 0, y: 0, ...canvas }): PopoverBounds {
    const right = Math.min(canvas.width, visible.x + visible.width) - 10
    const bottom = Math.min(canvas.height - Math.min(70, canvas.height / 5), visible.y + visible.height - 10)
    // On short screens prefer a reachable scrolling card over a large toolbar inset.
    const x = Math.max(visible.x + 10, Math.min(left, right - 100))
    const y = Math.max(visible.y + 10, Math.min(top, bottom - 100))
    return { x, y, width: Math.max(0, right - x), height: Math.max(0, bottom - y) }
  }

  static place(anchor: Point, card: Size, canvas: Size, radius: number, top: number, left = 10, visible?: PopoverBounds): Point {
    const bounds = this.bounds(canvas, top, left, visible)
    const cardWidth = Math.min(card.width, bounds.width), cardHeight = Math.min(card.height, bounds.height)
    left = bounds.x; top = bounds.y
    const gap = radius + 12
    const right = bounds.x + bounds.width - cardWidth
    const bottom = bounds.y + bounds.height - cardHeight
    let x = anchor.x + gap, y = anchor.y - cardHeight / 2
    if (x > right) {
      if (anchor.x - gap - cardWidth >= left) x = anchor.x - gap - cardWidth
      else {
        x = anchor.x - cardWidth / 2
        y = anchor.y + gap
        if (y > bottom) y = anchor.y - gap - cardHeight
      }
    }
    return { x: Math.max(left, Math.min(x, right)), y: Math.max(top, Math.min(y, bottom)) }
  }
}
