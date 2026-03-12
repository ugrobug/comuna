export const ssr = false

export const load = async ({ params }) => ({
  postId: Number(params.id),
})
