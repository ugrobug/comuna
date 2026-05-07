import { backendPostToPostView, type BackendPost, type BackendAuthor } from '$lib/api/backend'
import type { SiteUserPost } from '$lib/siteAuth'

export const siteUserPostToBackendPost = (post: SiteUserPost): BackendPost => ({
  id: post.id,
  title: post.title || '',
  content: post.content || '',
  template: post.template ?? null,
  enabled_template_editor_blocks: post.enabled_template_editor_blocks ?? [],
  post_ratings: post.post_ratings ?? {},
  post_rating: post.post_rating ?? null,
  created_at: post.created_at,
  tags: (post.tags ?? []).map((tag) =>
    typeof tag === 'string' ? { name: tag } : { name: tag.name, lemma: tag.lemma ?? null }
  ),
  author: {
    username: post.author?.username || 'author',
    title: post.author?.title ?? null,
    avatar_url: post.author?.avatar_url ?? null,
  },
})

export const siteUserPostToPostView = (post: SiteUserPost) => {
  const backendAuthor: BackendAuthor = {
    username: post.author?.username || 'author',
    title: post.author?.title ?? null,
    avatar_url: post.author?.avatar_url ?? null,
  }

  const postView = backendPostToPostView(siteUserPostToBackendPost(post), backendAuthor)
  postView.post.updated = post.updated_at || post.created_at
  return postView
}
