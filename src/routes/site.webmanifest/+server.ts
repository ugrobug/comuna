import type { RequestHandler } from './$types'
import { brandNameForLanguage } from '$lib/brand'
import {
  languageFromAcceptLanguage,
  originalPostLanguage,
  postLanguageLocales,
} from '$lib/postLanguages'

const descriptionByLanguage = {
  ru: 'Технологии и стартапы',
  en: 'Technology and startups',
  es: 'Tecnología y startups',
  pt: 'Tecnologia e startups',
  de: 'Technologie und Startups',
  fr: 'Technologie et startups',
  tr: 'Teknoloji ve girişimler',
  id: 'Teknologi dan startup',
}

export const GET: RequestHandler = ({ request }) => {
  const language =
    languageFromAcceptLanguage(request.headers.get('Accept-Language')) || originalPostLanguage
  const brandName = brandNameForLanguage(language)

  return new Response(
    JSON.stringify(
      {
        short_name: brandName,
        name: brandName,
        lang: postLanguageLocales[language],
        start_url: language === originalPostLanguage ? '/' : `/${language}/`,
        icons: [
          {
            src: '/pwa-192.png',
            type: 'image/png',
            sizes: '192x192',
            purpose: 'any',
          },
          {
            src: '/pwa-512.png',
            type: 'image/png',
            sizes: '512x512',
            purpose: 'any',
          },
          {
            src: '/pwa-192.png',
            type: 'image/png',
            sizes: '192x192',
            purpose: 'maskable',
          },
          {
            src: '/pwa-512.png',
            type: 'image/png',
            sizes: '512x512',
            purpose: 'maskable',
          },
        ],
        background_color: '#000000',
        display: 'standalone',
        scope: '/',
        theme_color: '#000000',
        description: descriptionByLanguage[language],
        screenshots: [
          {
            form_factor: 'wide',
            label: 'Desktop interface',
            type: 'image/webp',
            src: '/img/pwa/wide.webp',
            sizes: '3692x1948',
          },
          {
            form_factor: 'narrow',
            label: 'Mobile interface',
            src: '/img/pwa/narrow.webp',
            sizes: '962x1948',
          },
        ],
        shortcuts: [
          {
            name: 'Inbox',
            url: '/inbox',
          },
          {
            name: 'Create post',
            url: '/create/post',
          },
          {
            name: 'Profile',
            url: '/profile/user',
          },
        ],
        categories: ['entertainment', 'news', 'social'],
      },
      null,
      2
    ),
    {
      headers: {
        'Content-Type': 'application/manifest+json; charset=utf-8',
        'Cache-Control': 'public, max-age=300, s-maxage=300',
        Vary: 'Accept-Language',
      },
    }
  )
}
