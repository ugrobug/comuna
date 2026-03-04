<script lang="ts">
  export let user: { username: string; displayName?: string | null }
</script>

<span class="flex gap-0 items-center flex-shrink max-w-full min-w-0 ml-0.5">
  <span class="username-text">{user.displayName || user.username}</span>
</span>
