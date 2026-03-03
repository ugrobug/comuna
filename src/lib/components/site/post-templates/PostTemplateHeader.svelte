<script lang="ts">
  import MovieReviewTemplateHeader from '$lib/components/site/post-templates/MovieReviewTemplateHeader.svelte'
  import { isMovieReviewTemplate, type SitePostTemplate } from '$lib/postTemplates'

  export let template: SitePostTemplate | null | undefined
  export let fallbackTitle = ''
</script>

{#if isMovieReviewTemplate(template)}
  <MovieReviewTemplateHeader {template} {fallbackTitle} />
{/if}
