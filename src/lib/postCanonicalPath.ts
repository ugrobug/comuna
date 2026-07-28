export const canonicalPostRedirectPath = (
  requestedPath: string,
  canonicalPath: string
): string | null => (requestedPath === canonicalPath ? null : canonicalPath)
