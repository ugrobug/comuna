<script>
  import EditableStaticPage from '$lib/components/static-pages/EditableStaticPage.svelte'
  import { env } from '$env/dynamic/public'

  export let data

  const seoTitle = `Реклама — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Рекламные возможности на Comuna: спонсорские блоки, интеграции и спецпроекты.'
</script>

<EditableStaticPage
  {data}
  slug="advertisement"
  heading="Реклама"
  {description}
  {seoTitle}
/>
