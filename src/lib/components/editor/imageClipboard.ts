export const getClipboardImages = (clipboard: DataTransfer | null): File[] => {
  if (!clipboard) return []
  const isImage = (file: File) => /^image\//i.test(file.type) || (!file.type && /\.(png|jpe?g|webp|gif)$/i.test(file.name))
  const files = Array.from(clipboard.items || [])
    .filter((item) => item.kind === 'file')
    .map((item) => item.getAsFile())
    .filter((file): file is File => Boolean(file && isImage(file)))
  return files.length ? files : Array.from(clipboard.files || []).filter(isImage)
}
