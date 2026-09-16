type Point = { x: number; y: number }
type Size = { width: number; height: number }

/** Position a card beside its node, flipping at the canvas edges. */
export class NodePopover {
  static place(anchor: Point, card: Size, canvas: Size, radius: number, top: number, left = 10): Point {
    const gap = radius + 12
    const right = canvas.width - card.width - 10
    const bottom = canvas.height - card.height - 70
    let x = anchor.x + gap, y = anchor.y - card.height / 2
    if (x > right) {
      if (anchor.x - gap - card.width >= left) x = anchor.x - gap - card.width
      else {
        x = anchor.x - card.width / 2
        y = anchor.y + gap
        if (y > bottom) y = anchor.y - gap - card.height
      }
    }
    return { x: Math.max(left, Math.min(x, right)), y: Math.max(top, Math.min(y, bottom)) }
  }
}
