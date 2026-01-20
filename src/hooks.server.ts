import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);

  // Prevent oversized response headers from SSR preload Link header.
  response.headers.delete('link');

  return response;
};
