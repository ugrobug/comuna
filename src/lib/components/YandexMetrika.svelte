<script lang="ts">
  import { env } from '$env/dynamic/public';
  import { page } from '$app/stores';
  import { onDestroy, onMount } from 'svelte';
  import { startMeaningfulReadTracking } from '$lib/productAnalytics';
  
  const PUBLIC_YM_MEASUREMENT_ID = env.PUBLIC_YM_MEASUREMENT_ID || '106046128';
  let mounted = false;
  let stopMeaningfulReadTracking: () => void = () => undefined;

  $: if (mounted && $page.url.pathname) {
    stopMeaningfulReadTracking();
    stopMeaningfulReadTracking = startMeaningfulReadTracking($page.url.pathname);
  }

  onMount(() => {
  
    type MetrikaWindow = Window & {
      [key: string]: any;
    };

    (function(
      m: MetrikaWindow,
      e: Document,
      t: string,
      r: string,
      i: string,
      k?: HTMLScriptElement,
      a?: HTMLScriptElement
    ) {
      m[i] = m[i] || function(...args: any[]) {
        (m[i].a = m[i].a || []).push(args);
      };
      m[i].l = Number(new Date());
      
      for (let j = 0; j < document.scripts.length; j++) {
        if (document.scripts[j].src === r) { return; }
      }
      
      k = e.createElement(t) as HTMLScriptElement;
      a = e.getElementsByTagName(t)[0] as HTMLScriptElement;
      
      if (k && a && a.parentNode) {
        k.async = true;
        k.src = r;
        a.parentNode.insertBefore(k, a);
      }
    })(window, document, "script", `https://mc.yandex.ru/metrika/tag.js?id=${PUBLIC_YM_MEASUREMENT_ID}`, "ym");

    window.__TAMBUR_YM_COUNTER_ID__ = Number(PUBLIC_YM_MEASUREMENT_ID);
    window.ym(Number(PUBLIC_YM_MEASUREMENT_ID), "init", {
      ssr: true,
      webvisor:true,
      clickmap: true,
      ecommerce: "dataLayer",
      trackLinks: true,
      accurateTrackBounce: true
    });
    mounted = true;
  });

  onDestroy(() => stopMeaningfulReadTracking());
</script>

<noscript>
  <div>
    <img src={`https://mc.yandex.ru/watch/${PUBLIC_YM_MEASUREMENT_ID}`} style="position:absolute; left:-9999px;" alt="" />
  </div>
</noscript> 
