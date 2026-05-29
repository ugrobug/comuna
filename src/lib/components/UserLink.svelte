<script lang="ts">
  export let user: { displayName?: string; display_name?: string; username?: string; name?: string } = {}

  $: displayName = user.displayName || user.display_name || user.username || user.name || ''
</script>

<span class="flex gap-0 items-center flex-shrink max-w-full min-w-0 s-teo-aCtG4kMN ml-0.5">
    <span class="username-text false s-teo-aCtG4kMN">{displayName}</span>
</span> 
