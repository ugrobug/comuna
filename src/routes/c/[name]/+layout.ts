import { getClient } from '$lib/lemmy.js'

export async function load(req: any) {
  const community = await getClient(undefined, req.fetch).getCommunity({
    name: req.params.name,
  })

  return {
    community: community,
  }
}
