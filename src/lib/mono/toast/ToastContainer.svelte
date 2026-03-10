<script lang="ts">
  import Toast from './Toast.svelte'
  import { flip } from 'svelte/animate'
  import { toasts } from './toasts.js'
  import { backInOut, backOut, expoOut } from 'svelte/easing'
</script>

<div
  class="fixed inset-x-0 top-0 flex flex-col items-center justify-start z-[200] px-4 pt-4
  group overflow-visible pointer-events-none gap-4"
>
  {#each $toasts as toast, index (toast.id)}
    <div
      animate:flip={{ duration: 500, easing: expoOut }}
      class="pointer-events-auto transition-all max-w-[min(32rem,calc(100vw-2rem))]
      duration-300"
    >
      <Toast {toast} />
    </div>
  {/each}
</div>
