<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import Portal from '$lib/mono/popover/Portal.svelte'

  export let label = 'Карточка увлечения'
  const dispatch = createEventDispatcher<{ dismiss: void }>()
  let closeButton: HTMLButtonElement

  function trapTab(event: KeyboardEvent) {
    if (event.key !== 'Tab') return
    const controls = [...(event.currentTarget as HTMLElement).querySelectorAll<HTMLElement>('a[href], button:not(:disabled), input:not(:disabled), summary, [tabindex="0"]')].filter(element => element.getClientRects().length)
    const first = controls[0], last = controls[controls.length - 1]
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
  }

  function lockPageScroll() {
    const previousOverflow = document.body.style.overflow
    const previousFocus = document.activeElement as HTMLElement | null
    document.body.style.overflow = 'hidden'
    return { destroy() {
      document.body.style.overflow = previousOverflow
      if (previousFocus?.isConnected) previousFocus.focus({ preventScroll: true })
    } }
  }
</script>

<Portal on:mounted={() => closeButton.focus({ preventScroll: true })}>
  <section class="mobile-card" role="dialog" aria-modal="true" aria-label={label} tabindex="-1" on:keydown={trapTab} use:lockPageScroll>
    <header><span>{label}</span><button bind:this={closeButton} aria-label="Закрыть карточку" on:click={() => dispatch('dismiss')}>×</button></header>
    <div class="card-content"><slot /></div>
  </section>
</Portal>

<style>
  .mobile-card{--explore-surface:#fff;--explore-ink:#2d3650;--explore-canvas:#f6f7fb;position:fixed;inset:0;z-index:90;width:100%;height:100dvh;display:flex;flex-direction:column;overflow:hidden;background:var(--explore-surface);color:var(--explore-ink);box-sizing:border-box}
  header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-shrink:0;padding:calc(8px + env(safe-area-inset-top,0px)) max(16px,env(safe-area-inset-right,0px)) 8px max(16px,env(safe-area-inset-left,0px));border-bottom:1px solid #b2b8ca40;font-size:13px;font-weight:600}
  button{display:flex;align-items:center;justify-content:center;flex-shrink:0;width:44px;height:44px;border:0;border-radius:10px;background:#8174ce12;color:inherit;font-size:28px;cursor:pointer}
  button:focus-visible{outline:2px solid #8174ce;outline-offset:2px}
  .card-content{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain;padding:16px max(16px,env(safe-area-inset-right,0px)) calc(24px + env(safe-area-inset-bottom,0px)) max(16px,env(safe-area-inset-left,0px));-webkit-overflow-scrolling:touch}
  .card-content :global(.close-selection){display:none}
  :global(.dark) .mobile-card{--explore-surface:#242631;--explore-ink:#d9dfec;--explore-canvas:#1d202a}
</style>
