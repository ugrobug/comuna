<script lang="ts">
  import {
    formatPostVotePollDeadline,
    postVotePollOptionLabel,
    type PostVotePollTemplate,
  } from '$lib/postTemplates'

  export let template: PostVotePollTemplate
  export let fallbackTitle = ''

  $: data = template.data
  $: items = Array.isArray(data.items) ? data.items : []
  $: question = (data.question || fallbackTitle || 'Голосование за посты').trim()
  $: deadlineLabel = formatPostVotePollDeadline(data.ends_at)
  $: deadlineTimestamp = Date.parse(data.ends_at || '')
  $: isClosed = Number.isFinite(deadlineTimestamp) ? deadlineTimestamp <= Date.now() : false
</script>

<section class="vote-poll-hero overflow-hidden rounded-2xl border border-slate-200 dark:border-zinc-800">
  <div class="vote-poll-hero__bg"></div>
  <div class="vote-poll-hero__body">
    <div class="vote-poll-hero__head">
      <div class="vote-poll-hero__badge">Голосование за посты</div>
      {#if deadlineLabel}
        <div class={`vote-poll-hero__deadline ${isClosed ? 'is-closed' : ''}`}>
          {#if isClosed}
            Завершено: {deadlineLabel}
          {:else}
            До: {deadlineLabel}
          {/if}
        </div>
      {/if}
    </div>

    {#if question}
      <h2 class="vote-poll-hero__title">{question}</h2>
    {/if}

    {#if items.length}
      <div class="vote-poll-hero__items">
        {#each items as item, index (item.post_id)}
          <a
            class="vote-poll-item"
            href={item.path || `/b/post/${item.post_id}`}
            target="_blank"
            rel="noopener"
          >
            <span class="vote-poll-item__index">#{index + 1}</span>
            <span class="vote-poll-item__title">{postVotePollOptionLabel(item)}</span>
            {#if item.author_username}
              <span class="vote-poll-item__author">@{item.author_username}</span>
            {/if}
          </a>
        {/each}
      </div>
    {/if}
  </div>
</section>

<style lang="postcss">
  .vote-poll-hero {
    position: relative;
    background:
      radial-gradient(120% 130% at 5% 0%, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0) 56%),
      linear-gradient(135deg, rgba(15, 23, 42, 0.94), rgba(30, 41, 59, 0.9));
  }

  .vote-poll-hero__bg {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .vote-poll-hero__bg::before {
    content: '';
    position: absolute;
    inset: 0;
    opacity: 0.3;
    background-image:
      radial-gradient(circle at 15% 15%, rgba(148, 163, 184, 0.16) 0, transparent 38%),
      radial-gradient(circle at 80% 20%, rgba(16, 185, 129, 0.16) 0, transparent 34%);
  }

  .vote-poll-hero__body {
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    padding: 1rem;
    color: #e2e8f0;
  }

  .vote-poll-hero__head {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    justify-content: space-between;
  }

  .vote-poll-hero__badge {
    border-radius: 9999px;
    border: 1px solid rgba(16, 185, 129, 0.45);
    background: rgba(15, 23, 42, 0.5);
    color: #6ee7b7;
    font-size: 0.72rem;
    line-height: 1.2;
    padding: 0.26rem 0.62rem;
    font-weight: 600;
  }

  .vote-poll-hero__deadline {
    border-radius: 9999px;
    border: 1px solid rgba(148, 163, 184, 0.35);
    background: rgba(15, 23, 42, 0.45);
    color: #cbd5e1;
    font-size: 0.72rem;
    line-height: 1.2;
    padding: 0.26rem 0.62rem;
  }

  .vote-poll-hero__deadline.is-closed {
    border-color: rgba(251, 191, 36, 0.5);
    color: #fde68a;
  }

  .vote-poll-hero__title {
    margin: 0;
    color: #fff;
    font-size: clamp(1.15rem, 1.9vw, 1.55rem);
    line-height: 1.2;
    font-weight: 700;
    text-wrap: balance;
  }

  .vote-poll-hero__items {
    display: grid;
    gap: 0.45rem;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  }

  .vote-poll-item {
    border-radius: 0.72rem;
    border: 1px solid rgba(148, 163, 184, 0.24);
    background: rgba(15, 23, 42, 0.4);
    padding: 0.5rem 0.62rem;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: 0.25rem 0.55rem;
    text-decoration: none;
    color: inherit;
  }

  .vote-poll-item:hover {
    border-color: rgba(16, 185, 129, 0.5);
    background: rgba(15, 23, 42, 0.55);
  }

  .vote-poll-item__index {
    grid-row: span 2;
    color: #6ee7b7;
    font-size: 0.75rem;
    line-height: 1.2;
    font-weight: 700;
    min-width: 2rem;
  }

  .vote-poll-item__title {
    min-width: 0;
    color: #f8fafc;
    font-size: 0.9rem;
    line-height: 1.3;
    font-weight: 600;
  }

  .vote-poll-item__author {
    color: #94a3b8;
    font-size: 0.76rem;
    line-height: 1.2;
  }
</style>
