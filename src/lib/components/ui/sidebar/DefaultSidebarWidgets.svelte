<script lang="ts">
  import TopComunsSidebar from '$lib/components/ratings/TopComunsSidebar.svelte'
  import KeyboardShortcutsHint from '$lib/components/ui/sidebar/KeyboardShortcutsHint.svelte'
  import RecentComments from '$lib/components/ui/sidebar/RecentComments.svelte'

  export let keyboardShortcutsHintEnabled = false
</script>

<div class="flex flex-col gap-4">
  <KeyboardShortcutsHint enabled={keyboardShortcutsHintEnabled} />
  <TopComunsSidebar />
  <div class="h-px bg-slate-200 dark:bg-zinc-800"></div>
  <RecentComments />
</div>
