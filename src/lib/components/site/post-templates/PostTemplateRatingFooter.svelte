<script lang="ts">
  import { toast } from 'mono-svelte'
  import { buildPostRatingVoteUrl, type BackendPostRating } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'

  export let postId: number | null = null
  export let rating: BackendPostRating | null = null
  export let allowVoting = false

  let submitting = false
  let localRating: BackendPostRating | null = null
  let lastRatingRef: BackendPostRating | null = null

  $: if (rating !== lastRatingRef) {
    lastRatingRef = rating
    localRating = rating ? { ...rating } : null
  }

  $: scaleMin = Number(localRating?.scale_min ?? 1)
  $: scaleMax = Number(localRating?.scale_max ?? 10)
  $: values = Array.from(
    { length: Math.max(scaleMax - scaleMin + 1, 0) },
    (_, index) => scaleMin + index
  )
  $: selectedValue = Number(localRating?.user_vote ?? 0)
  $: votesCount = Math.max(Number(localRating?.votes_count ?? 0), 0)
  $: averageValue = typeof localRating?.average_value === 'number' ? localRating.average_value : null
  $: averageLabel =
    averageValue === null
      ? '—'
      : Number.isInteger(averageValue)
        ? String(averageValue)
        : averageValue.toFixed(1)

  const submitVote = async (value: number) => {
    if (!allowVoting || !postId) {
      toast({ content: 'Голосование доступно только в опубликованном посте', type: 'warning' })
      return
    }
    const token = $siteToken
    if (!token) {
      toast({ content: 'Необходимо зарегистрироваться', type: 'warning' })
      return
    }
    if (!Number.isInteger(value) || value < scaleMin || value > scaleMax || submitting) {
      return
    }

    submitting = true
    try {
      const response = await fetch(buildPostRatingVoteUrl(postId), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ value }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить оценку')
      }
      if (payload?.post_rating && typeof payload.post_rating === 'object') {
        localRating = { ...payload.post_rating }
      }
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось сохранить оценку',
        type: 'error',
      })
    } finally {
      submitting = false
    }
  }
</script>

{#if localRating}
  <section class="template-rating-footer">
    <div class="template-rating-footer__surface">
      <div class="template-rating-footer__copy">
        <div class="template-rating-footer__eyebrow">Рейтинг</div>
        <h3 class="template-rating-footer__title">Оцените материал</h3>
      </div>

      <div class="template-rating-footer__content">
        <div class="template-rating-scale" role="group" aria-label="Оценка материала от 1 до 10">
          {#each values as value}
            <button
              type="button"
              class={`template-rating-scale__item ${selectedValue === value ? 'is-selected' : ''}`}
              aria-pressed={selectedValue === value}
              disabled={submitting}
              on:click={() => submitVote(value)}
            >
              {value}
            </button>
          {/each}
        </div>

        <div class="template-rating-footer__stats" aria-live="polite">
          <div class="template-rating-footer__average">{averageLabel}</div>
          <div class="template-rating-footer__meta">
            <span>средняя оценка</span>
            <span>{votesCount} {votesCount === 1 ? 'голос' : votesCount < 5 ? 'голоса' : 'голосов'}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
{/if}

<style lang="postcss">
  .template-rating-footer {
    margin-top: 1.5rem;
  }

  .template-rating-footer__surface {
    position: relative;
    overflow: hidden;
    border-radius: 1.5rem;
    border: 1px solid rgba(245, 191, 64, 0.42);
    background:
      radial-gradient(circle at top left, rgba(250, 204, 21, 0.16), transparent 34%),
      linear-gradient(135deg, rgba(34, 40, 57, 0.98), rgba(45, 55, 72, 0.94));
    box-shadow:
      0 24px 52px rgba(15, 23, 42, 0.2),
      inset 0 1px 0 rgba(255, 255, 255, 0.08);
    padding: 1.3rem 1.4rem;
  }

  .template-rating-footer__copy {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .template-rating-footer__eyebrow {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: rgba(253, 224, 71, 0.82);
  }

  .template-rating-footer__title {
    margin: 0;
    font-size: 1.4rem;
    font-weight: 800;
    line-height: 1.05;
    color: #f8fafc;
  }

  .template-rating-footer__content {
    margin-top: 1rem;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 1rem;
    align-items: center;
  }

  .template-rating-scale {
    display: grid;
    grid-template-columns: repeat(10, minmax(0, 1fr));
    gap: 0.35rem;
    padding: 0.35rem;
    border-radius: 1rem;
    background: rgba(15, 23, 42, 0.26);
    border: 1px solid rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
  }

  .template-rating-scale__item {
    min-width: 0;
    height: 2.8rem;
    border: 0;
    border-radius: 0.8rem;
    background: rgba(255, 255, 255, 0.04);
    color: rgba(241, 245, 249, 0.9);
    font-size: 1rem;
    font-weight: 800;
    cursor: pointer;
    transition:
      transform 0.18s ease,
      background 0.18s ease,
      color 0.18s ease,
      box-shadow 0.18s ease;
  }

  .template-rating-scale__item:hover:not(:disabled) {
    transform: translateY(-1px);
    background: rgba(245, 191, 64, 0.18);
    color: #fff6d6;
    box-shadow: inset 0 0 0 1px rgba(245, 191, 64, 0.34);
  }

  .template-rating-scale__item.is-selected {
    background: linear-gradient(135deg, rgba(245, 191, 64, 0.92), rgba(251, 191, 36, 0.76));
    color: #1f2937;
    box-shadow:
      0 12px 26px rgba(245, 191, 64, 0.22),
      inset 0 1px 0 rgba(255, 255, 255, 0.25);
  }

  .template-rating-scale__item:disabled {
    cursor: default;
  }

  .template-rating-footer__stats {
    min-width: 9rem;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.3rem;
    color: rgba(226, 232, 240, 0.86);
  }

  .template-rating-footer__average {
    font-size: clamp(2rem, 5vw, 3rem);
    font-weight: 900;
    line-height: 0.95;
    color: #fff2bf;
  }

  .template-rating-footer__meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.05rem;
    font-size: 0.82rem;
    line-height: 1.25;
    text-align: right;
  }

  @media (max-width: 820px) {
    .template-rating-footer__content {
      grid-template-columns: 1fr;
    }

    .template-rating-footer__stats {
      min-width: 0;
      align-items: flex-start;
    }

    .template-rating-footer__meta {
      align-items: flex-start;
      text-align: left;
    }
  }

  @media (max-width: 640px) {
    .template-rating-footer__surface {
      padding: 1.1rem;
      border-radius: 1.25rem;
    }

    .template-rating-scale {
      overflow-x: auto;
      grid-template-columns: repeat(10, 3rem);
      padding-bottom: 0.55rem;
    }
  }
</style>
