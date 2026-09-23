import { redirect } from '@sveltejs/kit'

// Keep old bookmarks working; editing now lives on the graph.
export const load = () => { redirect(307, '/explore') }
