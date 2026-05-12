import '@tiptap/core'

declare module '@tiptap/core' {
  interface Commands<ReturnType> {
    gallery: {
      insertGallery: () => ReturnType
    }
  }
}
