<script lang="ts">
  import { Button, Modal, toast } from 'mono-svelte'
  import { Flag, Icon } from 'svelte-hero-icons'
  import {
    buildCommentReportUrl,
    buildPostReportUrl,
    type BackendContentReportReason,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { t } from '$lib/translations'

  export let open = false
  export let targetType: 'post' | 'comment'
  export let targetId: number

  let sendingReason: BackendContentReportReason | null = null

  const reasons: Array<{ value: BackendContentReportReason; label: string }> = [
    { value: 'sexualized', label: 'site.report.reasons.sexualized' },
    { value: 'illegal', label: 'site.report.reasons.illegal' },
    { value: 'harassment', label: 'site.report.reasons.harassment' },
    { value: 'spam_fraud', label: 'site.report.reasons.spamFraud' },
    { value: 'other', label: 'site.report.reasons.other' },
  ]

  async function submitReport(reason: BackendContentReportReason) {
    if (!$siteToken || !targetId || sendingReason) return
    sendingReason = reason
    try {
      const url =
        targetType === 'post'
          ? buildPostReportUrl(targetId)
          : buildCommentReportUrl(targetId)
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ reason }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || $t('site.report.error'))
      }
      open = false
      toast({ content: $t('site.report.success'), type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message || $t('site.report.error'),
        type: 'error',
      })
    } finally {
      sendingReason = null
    }
  }

  $: if (!open) sendingReason = null
</script>

<Modal bind:open dismissable title={$t('site.report.title')}>
  <div class="grid gap-2 w-full min-w-0 sm:min-w-[26rem]">
    {#each reasons as reason (reason.value)}
      <Button
        color="secondary"
        size="lg"
        class="!justify-start !text-left"
        disabled={sendingReason !== null}
        loading={sendingReason === reason.value}
        on:click={() => submitReport(reason.value)}
      >
        <Icon src={Flag} size="17" mini slot="prefix" />
        {$t(reason.label)}
      </Button>
    {/each}
  </div>
</Modal>
