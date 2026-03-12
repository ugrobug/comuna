<script>
  import EditableStaticPage from '$lib/components/static-pages/EditableStaticPage.svelte'
  import { env } from '$env/dynamic/public'

  export let data

  const seoTitle = `Правила — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Правила публикации и модерации контента на Comuna для владельцев Telegram-каналов.'
</script>

<EditableStaticPage
  {data}
  slug="rules"
  heading="Правила"
  {description}
  {seoTitle}
/>
