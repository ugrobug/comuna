import type { RequestHandler } from './$types'

export const GET: RequestHandler = ({ url }) => {
  const origin = url.origin.replace(/\/+$/, '')
  const body = [
    'User-agent: *',
    'Allow: /',
    '',
    `Host: ${origin.replace(/^https?:\/\//, '')}`,
    `Sitemap: ${origin}/sitemap.xml`,
    '',
  ].join('\n')

  return new Response(body, {
    headers: {
      'content-type': 'text/plain; charset=utf-8',
      'cache-control': 'public, max-age=3600',
    },
  })
}
