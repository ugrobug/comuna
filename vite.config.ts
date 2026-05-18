import { sveltekit } from '@sveltejs/kit/vite'
import { defineConfig } from 'vite'
import { loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiProxyTarget =
    env.PUBLIC_BACKEND_URL ||
    (env.PUBLIC_INSTANCE_URL ? `https://${env.PUBLIC_INSTANCE_URL}` : 'http://127.0.0.1:8000')
  const apiProxyKeepsPrefix = Boolean(env.PUBLIC_BACKEND_URL || !env.PUBLIC_INSTANCE_URL)
  return {
    plugins: [sveltekit()],

    define: {
      __VERSION__: JSON.stringify(process.env.npm_package_version),
    },
    server: {
      watch: {
        ignored: ['!**/node_modules/mono-svelte/**'],
      },
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
          rewrite: (path) => (apiProxyKeepsPrefix ? path : path.replace(/^\/api/, ''))
        }
      },
      fs: {
        allow: ['static']
      }
    },
  }
})
