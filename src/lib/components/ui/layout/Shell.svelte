<script lang="ts" context="module">
  const calculateDockProperties = (
    settings: {
      top: boolean | null
      noGap: boolean | null
    },
    screenWidth: number
  ): {
    noGap: boolean
    top: boolean
  } => {
    let panel = false
    let top = false

    if (screenWidth >= 1000) {
      panel = true
      top = true
    } else {
      // Для всех устройств меньше 1000px навбар всегда сверху
      panel = false
      top = true
    }

    panel = settings.noGap ?? panel
    top = settings.top ?? top

    return {
      noGap: panel,
      top: top,
    }
  }

  export const calculatePadding = (
    panel: boolean,
    top: boolean,
    content: boolean,
    screenWidth = 1000
  ): {
    top: number
    bottom: number
    class: string
  } => {
    if (panel) {
      if (top) {
        if (content) return { top: 80, class: '!pt-20', bottom: 0 }
        else
          return {
            top: 64,
            class: 'top-16 !max-h-[calc(100vh-4rem)]',
            bottom: 0,
          }
      } else return { top: 0, class: '!pb-20', bottom: 80 }
    } else {
      if (!content) return { top: 0, class: '', bottom: 0 }

      if (top) {
        if (screenWidth < 768) return { top: 112, class: '!pt-28', bottom: 0 }
        return { top: 72, class: '!pt-18', bottom: 0 } // Уменьшили с 96px до 72px
      }
      else return { top: 0, class: '!pb-24', bottom: 96 }
    }

    return { top: 0, class: ' failed-to-calculate', bottom: 0 }
  }

  export let screenWidth = writable(1000)
  export let dockProps: Readable<ReturnType<typeof calculateDockProperties>> =
    derived([userSettings, screenWidth], ([$settings, $screenWidth], set) => {
      set(calculateDockProperties($settings.dock, $screenWidth))
    })
  export let contentPadding: Readable<ReturnType<typeof calculatePadding>> =
    derived([dockProps, screenWidth], ([$dockProps, $screenWidth], set) =>
      set(calculatePadding($dockProps.noGap, $dockProps.top, true, $screenWidth))
    )
</script>

<script lang="ts">
  import { userSettings } from '$lib/settings.js'
  import { themeVars } from '$lib/ui/colors'
  import { routes } from '$lib/util.js'
  import { derived, writable, type Readable, type Writable } from 'svelte/store'
  import { GlobeAlt } from 'svelte-hero-icons'

  export let route: { id: string | null } | undefined = undefined
  export let fullBleed = false

  $: title = route ? routes[(route.id as keyof typeof routes) ?? ''] : ''

  $: sidePadding = calculatePadding($dockProps.noGap, $dockProps.top, false, $screenWidth)
  $: topPanel = $dockProps.noGap && $dockProps.top
</script>

<svelte:window bind:innerWidth={$screenWidth} />

<div
  {...$$restProps}
  class="shell bg-slate-50 dark:bg-zinc-950 {$$props.class}"
  style={themeVars}
>
  <slot />
  <div
    class="w-full z-50 pointer-events-none {topPanel ? 'fixed top-0' : 'fixed'} { $dockProps.top ? 'top-0' : 'bottom-0'}"
    style="grid-area: navbar;
    transition-property: padding, top, bottom;
    transition-duration: 250ms;
    transition-timing-function: cubic-bezier(0.075, 0.82, 0.165, 1);"
  >
    <slot
      name="navbar"
      class="
      {$dockProps.noGap
        ? $dockProps.top
          ? 'border-b shadow-none rounded-none'
          : 'border-t rounded-none'
        : 'border rounded-full'}
       
       dark:bg-transparent transition-colors duration-500
      pointer-events-auto backdrop-blur-xl {topPanel
        ? 'bg-slate-50/50 dark:bg-zinc-950/90 border-slate-100 dark:border-zinc-900'
        : `border-slate-200 dark:border-zinc-800 shadow-2xl
        bg-white/50 dark:bg-zinc-950/70`}"
      {title}
      style="transition: border-radius 250ms;"
    />
  </div>
  <div
    class="content min-h-screen {$userSettings.newWidth
      ? 'limit-width'
      : ''} {fullBleed ? 'full-bleed' : ''}"
  >
    <slot
      name="sidebar"
      class="shell-sidebar hidden md:flex sticky top-0 left-0 h-max bg-slate-50 dark:bg-zinc-950
      z-40
      {sidePadding.class}"
      style="grid-area: sidebar; width: 100% !important;"
    />
    <slot
      name="main"
      class="shell-main w-full bg-slate-50 dark:bg-zinc-950 justify-self-center z-0
      {$contentPadding.class} main"
      style="grid-area: main"
    />
  </div>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: 1fr;
    grid-template-rows: auto 1fr;
    grid-template-areas:
      'navbar'
      'content';
  }

  .content {
    width: 100%;
    display: grid;
    margin-left: auto;
    margin-right: auto;
    grid-area: content;
    grid-template-columns: 1fr;
    grid-template-areas: 'main';
    justify-items: start;
  }

  .content.limit-width {
    max-width: 1280px;
  }

  .content.full-bleed,
  .content.full-bleed.limit-width {
    max-width: none;
    grid-template-columns: 1fr;
    grid-template-areas: 'main';
    justify-items: start;
  }
  
  @media (max-width: 1279px) {
    .content.limit-width:not(.full-bleed) {
      max-width: 960px;
    }
  }

  .content > * {
    width: 100%; /* Full width for immediate children */
  }

  @media (min-width: 768px) {
    .content.limit-width:not(.full-bleed) {
      max-width: none;
    }

    .content:not(.full-bleed) {
      grid-template-columns: minmax(calc(30px + 14rem + 30px), 1fr) minmax(0, min(60vw, 52rem)) minmax(24px, 1fr);
      justify-items: stretch;
      grid-template-areas: '. main .';
    }

    :global(.content:not(.full-bleed) > .shell-sidebar) {
      grid-area: auto !important;
      position: fixed !important;
      left: 30px;
      top: 72px !important;
      z-index: 40;
      width: 14rem !important;
      max-height: calc(100vh - 72px);
      overflow-y: auto;
    }
  }

  @media (min-width: 1280px) {
    .content {
      width: 100%;
    }

    .content.limit-width:not(.full-bleed) {
      max-width: none;
    }

    .content:not(.full-bleed) {
      grid-template-columns: minmax(calc(30px + 17.25rem + 30px), 1fr) minmax(0, 55.5rem) minmax(24px, 1fr);
      justify-items: stretch;
      grid-template-areas: '. main .';
    }

    .content.limit-width:not(.full-bleed) {
      grid-template-columns: minmax(calc(30px + 17.25rem + 30px), 1fr) minmax(0, 55.5rem) minmax(24px, 1fr);
    }

    :global(.content:not(.full-bleed) > .shell-sidebar),
    :global(.content.limit-width:not(.full-bleed) > .shell-sidebar) {
      max-width: 17.25rem;
      justify-self: start;
      width: 17.25rem !important;
    }

    .main {
      width: 100%;
    }
  }
</style>
