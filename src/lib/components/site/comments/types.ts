export type SiteComment = {
  id: number
  body: string
  original_body?: string
  original_language?: string
  created_at: string
  updated_at: string
  parent_id?: number | null
  is_deleted?: boolean
  is_translated?: boolean
  language?: string
  likes_count?: number
  liked_by_me?: boolean
  can_edit?: boolean
  user: {
    id?: number | null
    username: string
    display_name?: string | null
    avatar_url?: string | null
    profile_url?: string | null
    is_mask?: boolean
    is_deleted?: boolean
  }
}

export type SiteCommentMask = {
  key: string
  username: string
  display_name?: string | null
}

export type SiteCommentNode = {
  comment: SiteComment
  children: SiteCommentNode[]
}
