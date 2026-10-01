import { getBackendBaseUrl } from '$lib/api/backend'
import { MentionController, type MentionOptions } from './MentionController'
import './mentions.css'

export function mentionSuggestions(node: HTMLElement, options: MentionOptions) {
  const controller = new MentionController(node, options, `${getBackendBaseUrl()}/api/mentions/suggest/`)
  return { update: (next: MentionOptions) => controller.update(next), destroy: () => controller.destroy() }
}
