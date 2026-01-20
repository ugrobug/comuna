import type { Handle } from '@sveltejs/kit';

export const handle: Handle = async ({ event, resolve }) => {
  const response = await resolve(event);

  // Prevent oversized response headers from SSR preload Link header.
  const headers = new Headers(response.headers);
  headers.delete('link');

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
};
