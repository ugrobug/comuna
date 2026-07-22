<script lang="ts">
  import StaticPageSeo from '$lib/components/static-pages/StaticPageSeo.svelte'
  import { brandNameForLanguage } from '$lib/brand'
  import { APPS_PAGE_LOCALIZATION } from '$lib/staticPageContent'
  import { normalizePostLanguage } from '$lib/postLanguages'
  import { locale } from '$lib/translations'
  import { deserializeEditorModel } from '$lib/util'

  export let data

  $: meta = APPS_PAGE_LOCALIZATION[normalizePostLanguage(data?.language)]
  $: pageHeading = data?.pageTitle || meta.title
  $: brandName = brandNameForLanguage($locale)
  $: seoTitle = `${pageHeading} — ${brandName}`
  $: intro = extractIntro(data?.pageContent, meta.intro)

  const stripHtml = (value: unknown) =>
    String(value ?? '')
      .replace(/<br\s*\/?>/gi, ' ')
      .replace(/<[^>]+>/g, '')
      .replace(/&nbsp;/gi, ' ')
      .replace(/&amp;/gi, '&')
      .replace(/\s+/g, ' ')
      .trim()

  const extractIntro = (content: unknown, fallback: string) => {
    if (typeof content !== 'string' || !content.trim()) return fallback
    const model = deserializeEditorModel(content)
    const blocks = Array.isArray(model?.blocks) ? model.blocks : []
    for (const block of blocks) {
      const text = stripHtml(block?.data?.text)
      if (
        text &&
        !text.includes('apps.apple.com') &&
        !text.includes('play.google.com') &&
        !text.includes('rustore.ru')
      ) {
        return text
      }
    }
    return fallback
  }

  const stores = [
    {
      name: 'App Store',
      platform: 'iPhone & iPad',
      href: 'https://apps.apple.com/ru/app/tambur/id6784176665',
      accent: 'apple',
    },
    {
      name: 'Google Play',
      platform: 'Android',
      href: 'https://play.google.com/store/apps/details?id=ru.comuna.mobile',
      accent: 'google',
    },
    {
      name: 'RuStore',
      platform: 'Android',
      href: 'https://www.rustore.ru/catalog/app/ru.comuna.mobile?_rsc=tf3rt',
      accent: 'rustore',
    },
  ]
</script>

<main class="apps-page">
  <img class="apps-page__icon" src="/logo_512.png" alt="" width="104" height="104" />
  <p class="apps-page__eyebrow">{pageHeading}</p>
  <h1>{brandName}</h1>
  <p class="apps-page__intro">{intro}</p>

  <nav class="apps-page__stores" aria-label={pageHeading}>
    {#each stores as store}
      <a
        class={`store-button store-button--${store.accent}`}
        href={store.href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${store.name}, ${store.platform}`}
      >
        <span class="store-button__label">
          <strong>{store.name}</strong>
          <span>{store.platform}</span>
        </span>
        <span class="store-button__arrow" aria-hidden="true">&nearr;</span>
      </a>
    {/each}
  </nav>
</main>

<StaticPageSeo
  title={seoTitle}
  description={meta.description}
  language={data?.language}
  languageVersions={data?.languageVersions}
/>

<style>
  .apps-page {
    display: flex;
    width: min(100%, 36rem);
    flex-direction: column;
    align-items: flex-start;
    padding: 1.5rem 0 2.5rem;
  }

  .apps-page__icon {
    width: 6.5rem;
    height: 6.5rem;
    margin-bottom: 1.5rem;
    border: 1px solid #e2e8f0;
    border-radius: 1.5rem;
    background: #fff;
    object-fit: cover;
    box-shadow: 0 10px 28px rgba(15, 23, 42, 0.1);
  }

  .apps-page__eyebrow {
    margin: 0 0 0.4rem;
    color: #64748b;
    font-size: 0.875rem;
    font-weight: 650;
  }

  h1 {
    margin: 0;
    color: #0f172a;
    font-size: 2.25rem;
    font-weight: 750;
    line-height: 1.12;
    letter-spacing: 0;
  }

  .apps-page__intro {
    max-width: 34rem;
    margin: 1rem 0 0;
    color: #475569;
    font-size: 1.05rem;
    line-height: 1.65;
  }

  .apps-page__stores {
    display: flex;
    width: min(100%, 27rem);
    flex-direction: column;
    gap: 0.75rem;
    margin-top: 2rem;
  }

  .store-button {
    --store-accent: #334155;
    display: flex;
    min-height: 4rem;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    border: 1px solid #cbd5e1;
    border-left: 4px solid var(--store-accent);
    border-radius: 0.5rem;
    background: #fff;
    padding: 0.7rem 1rem;
    color: #0f172a;
    text-decoration: none;
    transition:
      border-color 150ms ease,
      background-color 150ms ease,
      transform 150ms ease;
  }

  .store-button:hover {
    border-color: var(--store-accent);
    background: #f8fafc;
    transform: translateY(-1px);
  }

  .store-button:focus-visible {
    outline: 3px solid rgba(37, 99, 235, 0.25);
    outline-offset: 2px;
  }

  .store-button--apple {
    --store-accent: #111827;
  }

  .store-button--google {
    --store-accent: #2563eb;
  }

  .store-button--rustore {
    --store-accent: #0f766e;
  }

  .store-button__label {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.15rem;
  }

  .store-button__label strong {
    font-size: 1rem;
    font-weight: 700;
  }

  .store-button__label span {
    color: #64748b;
    font-size: 0.78rem;
  }

  .store-button__arrow {
    flex: 0 0 auto;
    color: var(--store-accent);
    font-size: 1.15rem;
    line-height: 1;
  }

  :global(.dark) .apps-page__icon {
    border-color: #3f3f46;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.25);
  }

  :global(.dark) h1 {
    color: #fafafa;
  }

  :global(.dark) .apps-page__eyebrow,
  :global(.dark) .apps-page__intro {
    color: #a1a1aa;
  }

  :global(.dark) .store-button {
    border-color: #3f3f46;
    border-left-color: var(--store-accent);
    background: #18181b;
    color: #fafafa;
  }

  :global(.dark) .store-button:hover {
    border-color: var(--store-accent);
    background: #27272a;
  }

  :global(.dark) .store-button__label span {
    color: #a1a1aa;
  }

  @media (max-width: 640px) {
    .apps-page {
      padding-top: 0.75rem;
    }

    .apps-page__icon {
      width: 5.25rem;
      height: 5.25rem;
      margin-bottom: 1.25rem;
      border-radius: 1.25rem;
    }

    h1 {
      font-size: 1.9rem;
    }

    .apps-page__stores {
      width: 100%;
    }
  }
</style>
