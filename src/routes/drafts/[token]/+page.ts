export const ssr = false

export const load = async ({ params }) => {
  return {
    shareToken: params.token,
  }
}
