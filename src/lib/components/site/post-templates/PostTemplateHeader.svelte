<script lang="ts">
import BugReportTemplateHeader from '$lib/components/site/post-templates/BugReportTemplateHeader.svelte'
import MovieReviewTemplateHeader from '$lib/components/site/post-templates/MovieReviewTemplateHeader.svelte'
import MusicReleaseTemplateHeader from '$lib/components/site/post-templates/MusicReleaseTemplateHeader.svelte'
import PostVotePollTemplateHeader from '$lib/components/site/post-templates/PostVotePollTemplateHeader.svelte'
import type { BackendPoll } from '$lib/api/backend'
import {
  isBugReportTemplate,
  isMusicReleaseTemplate,
  isMovieReviewTemplate,
  isPostVotePollTemplate,
  type SitePostTemplate,
} from '$lib/postTemplates'

  export let template: SitePostTemplate | null | undefined
  export let fallbackTitle = ''
  export let poll: BackendPoll | null = null
  export let pollPostId: number | null = null
  export let allowPollVoting = false
  export let compact = false
  export let canManageBugReportStatus = false
  export let postId: number | null = null
</script>

{#if isMovieReviewTemplate(template)}
  <MovieReviewTemplateHeader {template} {fallbackTitle} />
{:else if isMusicReleaseTemplate(template)}
  <MusicReleaseTemplateHeader {template} {fallbackTitle} />
{:else if isPostVotePollTemplate(template)}
  <PostVotePollTemplateHeader
    {template}
    {fallbackTitle}
    {poll}
    {pollPostId}
    {allowPollVoting}
  />
{:else if isBugReportTemplate(template)}
  <BugReportTemplateHeader
    {template}
    {compact}
    canManageStatus={canManageBugReportStatus}
    {postId}
    on:statuschange
  />
{/if}
