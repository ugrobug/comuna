// See https://kit.svelte.dev/docs/types#app

import type { Action } from '$lib/components/ui/navbar/commands/actions'
import type { ComponentType, SvelteComponent } from 'svelte'

// for information about these interfaces
declare global {
  namespace App {
    // interface Error {}
    interface Locals {
      instance?: string
    }
    interface PageData {
      slots?: {
        sidebar?: {
          component?: ComponentType
          props?: any
        }
      }
      contextual?: {
        actions?: Action[]
      }
    }
    interface PageState {
      openImage?: string
      openImageAlt?: string
      openImageGallery?: Array<{
        url: string
        alt?: string | null
      }>
    }
    // interface Platform {}
  }
  declare const __VERSION__: string
}

export {}
declare const __VERSION__: string

declare module 'markdown-it-sub'
declare module 'markdown-it-sup'
