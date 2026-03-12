<script>
  import EditableStaticPage from '$lib/components/static-pages/EditableStaticPage.svelte'
  import { env } from '$env/dynamic/public'

  export let data

  const seoTitle = `Авторам — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Публикуйте посты Telegram-канала на сайте, чтобы их находили в Google и Яндексе и подписывались на ваш канал.'
</script>

<EditableStaticPage
  {data}
  slug="authors"
  heading="Авторам"
  {description}
  {seoTitle}
/>
