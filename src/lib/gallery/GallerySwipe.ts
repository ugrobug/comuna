type Contact = { identifier: number; clientX: number; clientY: number }

/** A single horizontal gesture, cancelled by zooming, multiple fingers or scrolling. */
export class GallerySwipe {
  private start: Contact | null = null
  private blocked = false

  begin(touches: ArrayLike<Contact>, enabled: boolean): void {
    this.blocked = !enabled || touches.length !== 1
    this.start = this.blocked ? null : {
      identifier: touches[0].identifier, clientX: touches[0].clientX, clientY: touches[0].clientY,
    }
  }

  move(touches: ArrayLike<Contact>): void {
    if (touches.length !== 1 || (this.start &&
      (touches[0].identifier !== this.start.identifier ||
       Math.abs(touches[0].clientY - this.start.clientY) > Math.max(24, Math.abs(touches[0].clientX - this.start.clientX))))) {
      this.cancel()
    }
  }

  finish(touches: ArrayLike<Contact>, enabled: boolean): number {
    const start = this.start
    const blocked = this.blocked
    this.cancel()
    if (!enabled || blocked || !start || touches.length !== 1 || touches[0].identifier !== start.identifier) return 0
    const dx = touches[0].clientX - start.clientX
    const dy = touches[0].clientY - start.clientY
    return Math.abs(dx) >= 45 && Math.abs(dx) > Math.abs(dy) * 1.5 ? (dx < 0 ? 1 : -1) : 0
  }

  cancel(): void {
    this.start = null
    this.blocked = true
  }
}
