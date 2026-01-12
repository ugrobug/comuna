export type SiteComment = {
  id: number
  body: string
  created_at: string
  updated_at: string
  parent_id?: number | null
  is_deleted?: boolean
  likes_count?: number
  liked_by_me?: boolean
  can_edit?: boolean
  user: {
    username: string
  }
}

export type SiteCommentNode = {
  comment: SiteComment
  children: SiteCommentNode[]
}
