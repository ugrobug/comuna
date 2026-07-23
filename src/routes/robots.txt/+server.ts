import type { RequestHandler } from './$types'

export const GET: RequestHandler = ({ url }) => {
  const origin = url.origin.replace(/\/+$/, '')
  const body = [
    'User-agent: GPTBot',
    'Disallow: /',
    '',
    'User-agent: ClaudeBot',
    'Disallow: /',
    '',
    'User-agent: Bytespider',
    'Disallow: /',
    '',
    'User-agent: meta-externalagent',
    'Disallow: /',
    '',
    'User-agent: SemrushBot',
    'Disallow: /',
    '',
    'User-agent: *',
    'Disallow: /admin/',
    'Disallow: /settings/',
    'Disallow: /accounts/',
    'Disallow: /inbox/',
    'Disallow: /inbox/messages/',
    'Disallow: /*?thread=',
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
