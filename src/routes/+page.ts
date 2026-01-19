import { buildHomeFeedUrl } from '$lib/api/backend'

export async function load({ fetch }) {
  let posts: any[] = []
  try {
    const response = await fetch(buildHomeFeedUrl())
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
