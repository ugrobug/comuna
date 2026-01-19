import { buildHomeFeedUrl } from '$lib/api/backend'

const PAGE_SIZE = 10

export async function load({ fetch }) {
  let posts: any[] = []
  try {
    const url = new URL(buildHomeFeedUrl())
    url.searchParams.set('limit', String(PAGE_SIZE))
    const response = await fetch(url.toString())
    if (response.ok) {
      const data = await response.json()
      posts = data.posts ?? []
    }
  } catch (error) {
    console.error('Failed to load home feed:', error)
  }

  return {
    posts,
  }
}
