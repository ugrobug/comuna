import type { RequestHandler } from './$types'

const APPLE_SDK_URL =
  'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js'

export const GET: RequestHandler = async ({ fetch }) => {
  try {
    const response = await fetch(APPLE_SDK_URL)
    if (!response.ok) {
      return new Response('Apple Sign In SDK is temporarily unavailable.', { status: 503 })
    }

    return new Response(await response.arrayBuffer(), {
      headers: {
        'Cache-Control': 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=604800',
        'Content-Type': 'application/javascript; charset=utf-8',
        'X-Content-Type-Options': 'nosniff',
      },
    })
  } catch {
    return new Response('Apple Sign In SDK is temporarily unavailable.', { status: 503 })
  }
}
