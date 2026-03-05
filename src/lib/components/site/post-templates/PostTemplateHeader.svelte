<script lang="ts">
  import MovieReviewTemplateHeader from '$lib/components/site/post-templates/MovieReviewTemplateHeader.svelte'
  import PostVotePollTemplateHeader from '$lib/components/site/post-templates/PostVotePollTemplateHeader.svelte'
  import {
    isMovieReviewTemplate,
    isPostVotePollTemplate,
    type SitePostTemplate,
  } from '$lib/postTemplates'

  export let template: SitePostTemplate | null | undefined
  export let fallbackTitle = ''
</script>

{#if isMovieReviewTemplate(template)}
  <MovieReviewTemplateHeader {template} {fallbackTitle} />
{:else if isPostVotePollTemplate(template)}
  <PostVotePollTemplateHeader {template} {fallbackTitle} />
{/if}
