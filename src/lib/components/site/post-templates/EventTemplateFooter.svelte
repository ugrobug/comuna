<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { locale, t } from '$lib/translations'
  import { siteToken } from '$lib/siteAuth'
  import type { BackendEventAttendance } from '$lib/api/backend'
  import type { EventTemplate } from '$lib/postTemplates'
  import { ArrowTopRightOnSquare, CalendarDays, CheckCircle, Icon, XMark } from 'svelte-hero-icons'

  export let template: EventTemplate
  export let attendance: BackendEventAttendance | null = null
  export let postId: number
  export let title: string

  let updating = false
  let calendarPickerOpen = false
  let localAttendance: BackendEventAttendance | null = attendance
  let lastAttendance = attendance

  $: if (attendance !== lastAttendance) {
    lastAttendance = attendance
    localAttendance = attendance
  }
  $: startsAt = localAttendance?.starts_at || template.data.starts_at || ''
  $: startsAtDate = startsAt ? new Date(startsAt) : null
  $: validStartsAt = Boolean(startsAtDate && !Number.isNaN(startsAtDate.getTime()))
  $: formattedStartsAt = validStartsAt
    ? new Intl.DateTimeFormat($locale || 'ru', {
        dateStyle: 'long',
        timeStyle: 'short',
      }).format(startsAtDate as Date)
    : ''

  const escapeIcs = (value: string) =>
    value.replace(/\\/g, '\\\\').replace(/\r?\n/g, '\\n').replace(/,/g, '\\,').replace(/;/g, '\\;')

  const toIcsDate = (date: Date) =>
    date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')

  const getCalendarEvent = () => {
    if (!validStartsAt || !startsAtDate) return null
    const end = new Date(startsAtDate.getTime() + 60 * 60 * 1000)
    const postUrl = `${window.location.origin}${$page.url.pathname}`

    return { start: startsAtDate, end, postUrl }
  }

  const downloadCalendarEvent = () => {
    const event = getCalendarEvent()
    if (!event) return
    const ics = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Tambur//Event//RU',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'BEGIN:VEVENT',
      `UID:tambur-post-${postId}@tambur.pub`,
      `DTSTAMP:${toIcsDate(new Date())}`,
      `DTSTART:${toIcsDate(event.start)}`,
      `DTEND:${toIcsDate(event.end)}`,
      `SUMMARY:${escapeIcs(title)}`,
      `DESCRIPTION:${escapeIcs(event.postUrl)}`,
      `URL:${escapeIcs(event.postUrl)}`,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n')
    const url = URL.createObjectURL(new Blob([ics], { type: 'text/calendar;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `tambur-event-${postId}.ics`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
    calendarPickerOpen = false
  }

  const openWebCalendar = (provider: 'google' | 'yandex' | 'outlook') => {
    const event = getCalendarEvent()
    if (!event) return

    let url: URL
    if (provider === 'google') {
      url = new URL('https://calendar.google.com/calendar/render')
      url.searchParams.set('action', 'TEMPLATE')
      url.searchParams.set('text', title)
      url.searchParams.set('dates', `${toIcsDate(event.start)}/${toIcsDate(event.end)}`)
      url.searchParams.set('details', event.postUrl)
    } else if (provider === 'yandex') {
      url = new URL('https://calendar.yandex.ru/event')
      url.searchParams.set('name', title)
      url.searchParams.set('start_ts', event.start.toISOString())
      url.searchParams.set('end_ts', event.end.toISOString())
      url.searchParams.set('description', event.postUrl)
    } else {
      url = new URL('https://outlook.live.com/calendar/0/deeplink/compose')
      url.searchParams.set('path', '/calendar/action/compose')
      url.searchParams.set('rru', 'addevent')
      url.searchParams.set('subject', title)
      url.searchParams.set('startdt', event.start.toISOString())
      url.searchParams.set('enddt', event.end.toISOString())
      url.searchParams.set('body', event.postUrl)
    }

    calendarPickerOpen = false
    window.open(url.toString(), '_blank', 'noopener,noreferrer')
  }

  const handleCalendarPickerKeydown = (event: KeyboardEvent) => {
    if (calendarPickerOpen && event.key === 'Escape') calendarPickerOpen = false
  }

  const toggleAttendance = async () => {
    if (!$siteToken) {
      await goto(`/account?next=${encodeURIComponent($page.url.pathname + $page.url.search)}`)
      return
    }
    if (updating || !localAttendance?.can_attend) return
    updating = true
    try {
      const response = await fetch(`/api/posts/${postId}/event-attendance/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ attending: !localAttendance.is_attending }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.event_attendance) {
        throw new Error(payload?.error || 'attendance update failed')
      }
      localAttendance = payload.event_attendance
    } catch (error) {
      console.error('Failed to update event attendance:', error)
    } finally {
      updating = false
    }
  }
</script>

<svelte:window on:keydown={handleCalendarPickerKeydown} />

{#if validStartsAt}
  <section class="mt-5 border-t border-slate-200 pt-4 dark:border-zinc-800" aria-label={$t('site.event.title')}>
    <div class="flex items-center gap-2 text-sm font-semibold text-slate-900 dark:text-zinc-100">
      <Icon src={CalendarDays} size="20" />
      <time datetime={startsAt}>{formattedStartsAt}</time>
    </div>
    <div class="mt-3 flex flex-wrap gap-2">
      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 transition hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
        on:click={() => (calendarPickerOpen = true)}
      >
        <Icon src={CalendarDays} size="18" />
        {$t('site.event.addToCalendar')}
      </button>
      {#if localAttendance?.can_attend}
        <button
          type="button"
          class={`inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-semibold transition disabled:opacity-60 ${
            localAttendance.is_attending
              ? 'border border-emerald-300 bg-emerald-50 text-emerald-800 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-200'
              : 'bg-sky-600 text-white hover:bg-sky-700'
          }`}
          disabled={updating}
          on:click={toggleAttendance}
        >
          <Icon src={CheckCircle} size="18" />
          {updating
            ? $t('site.event.saving')
            : localAttendance.is_attending
              ? $t('site.event.notGoing')
              : $t('site.event.going')}
        </button>
      {/if}
    </div>
    {#if localAttendance?.is_attending}
      <p class="mt-2 text-xs text-slate-500 dark:text-zinc-400">{$t('site.event.reminderHint')}</p>
    {/if}
  </section>
{/if}

{#if calendarPickerOpen}
  <div
    class="fixed inset-0 z-[100] flex items-end justify-center bg-slate-950/40 p-3 backdrop-blur-[1px] sm:items-center"
    role="presentation"
    on:click|self={() => (calendarPickerOpen = false)}
  >
    <div
      class="w-full max-w-md rounded-lg bg-white p-4 shadow-2xl dark:bg-zinc-900 sm:p-5"
      role="dialog"
      aria-modal="true"
      aria-labelledby="event-calendar-picker-title"
    >
      <header class="flex items-center justify-between gap-3">
        <h2 id="event-calendar-picker-title" class="text-lg font-semibold text-slate-950 dark:text-zinc-50">
          {$t('site.event.chooseCalendar')}
        </h2>
        <button
          type="button"
          class="inline-flex size-9 shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
          aria-label={$t('site.event.closeCalendarPicker')}
          on:click={() => (calendarPickerOpen = false)}
        >
          <Icon src={XMark} size="20" />
        </button>
      </header>

      <div class="mt-4 grid gap-2">
        <button
          type="button"
          class="calendar-option dark:border-zinc-700 dark:text-zinc-100 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
          on:click={() => openWebCalendar('google')}
        >
          <span class="calendar-mark bg-white text-[#4285f4] ring-1 ring-slate-200">G</span>
          <span>Google Calendar</span>
          <Icon src={ArrowTopRightOnSquare} size="18" />
        </button>
        <button
          type="button"
          class="calendar-option dark:border-zinc-700 dark:text-zinc-100 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
          on:click={downloadCalendarEvent}
        >
          <span class="calendar-mark bg-slate-950 text-white dark:bg-white dark:text-slate-950">A</span>
          <span>Apple Calendar</span>
          <Icon src={CalendarDays} size="18" />
        </button>
        <button
          type="button"
          class="calendar-option dark:border-zinc-700 dark:text-zinc-100 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
          on:click={() => openWebCalendar('yandex')}
        >
          <span class="calendar-mark bg-[#fc3f1d] text-white">Я</span>
          <span>Яндекс Календарь</span>
          <Icon src={ArrowTopRightOnSquare} size="18" />
        </button>
        <button
          type="button"
          class="calendar-option dark:border-zinc-700 dark:text-zinc-100 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
          on:click={() => openWebCalendar('outlook')}
        >
          <span class="calendar-mark bg-[#0078d4] text-white">O</span>
          <span>Outlook</span>
          <Icon src={ArrowTopRightOnSquare} size="18" />
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .calendar-option {
    display: grid;
    grid-template-columns: 2.25rem minmax(0, 1fr) 1.125rem;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
    min-height: 3.5rem;
    padding: 0.625rem 0.75rem;
    border: 1px solid rgb(203 213 225);
    border-radius: 0.375rem;
    color: rgb(15 23 42);
    font-size: 0.9375rem;
    font-weight: 600;
    text-align: left;
    transition: background-color 150ms ease, border-color 150ms ease;
  }

  .calendar-option:hover {
    border-color: rgb(148 163 184);
    background: rgb(248 250 252);
  }

  .calendar-mark {
    display: inline-flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    border-radius: 0.375rem;
    font-weight: 700;
  }
</style>
