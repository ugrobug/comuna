<script lang="ts">
  import { page } from '$app/stores'
  import { Bars3, BookOpen, Film, Home, Icon, ListBullet, MapPin, XMark } from 'svelte-hero-icons'

  let mobileMenuOpen = false

  const projects = [
    {
      title: 'Книга интернет сообщества',
      description: 'Общая книга по одному слову',
      href: '/s/book',
      icon: BookOpen,
    },
    {
      title: '365 фильмов',
      description: 'Один фильм в день',
      href: '/s/365-films',
      icon: Film,
    },
    {
      title: 'Имя на карте',
      description: 'Слова из спутниковых снимков',
      href: '/s/landname',
      icon: MapPin,
    },
  ]

  const isActiveProject = (href: string) =>
    $page.url.pathname === href || $page.url.pathname.startsWith(`${href}/`)

  $: if ($page.url.pathname) {
    mobileMenuOpen = false
  }

  const closeMobileMenu = () => {
    mobileMenuOpen = false
  }

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') {
      closeMobileMenu()
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="special-shell">
  <div class="mobile-menu-bar">
    <button
      class="mobile-menu-button"
      type="button"
      aria-label="Открыть меню спецпроектов"
      aria-expanded={mobileMenuOpen}
      aria-controls="special-projects-sidebar"
      on:click={() => (mobileMenuOpen = true)}
    >
      <Icon src={Bars3} size="18" mini />
      <span>Спецпроекты</span>
    </button>
  </div>

  {#if mobileMenuOpen}
    <button
      class="mobile-menu-backdrop"
      type="button"
      aria-label="Закрыть меню спецпроектов"
      on:click={closeMobileMenu}
    ></button>
  {/if}

  <aside
    id="special-projects-sidebar"
    class:mobile-open={mobileMenuOpen}
    class="special-sidebar"
    aria-label="Спецпроекты"
  >
    <nav class="special-nav">
      <button class="mobile-close-button" type="button" aria-label="Закрыть меню" on:click={closeMobileMenu}>
        <Icon src={XMark} size="18" mini />
      </button>

      <a class="site-link" href="/" on:click={closeMobileMenu}>
        <span class="nav-icon">
          <Icon src={Home} size="18" mini />
        </span>
        <span>На сайт</span>
      </a>

      <div class="projects-group">
        <div class="group-title">
          <span class="nav-icon">
            <Icon src={ListBullet} size="18" mini />
          </span>
          <span>Все спецпроекты</span>
        </div>

        <div class="project-links">
          {#each projects as project}
            <a
              class:active={isActiveProject(project.href)}
              class="project-link"
              href={project.href}
              aria-current={isActiveProject(project.href) ? 'page' : undefined}
              on:click={closeMobileMenu}
            >
              <span class="project-icon">
                <Icon src={project.icon} size="18" mini />
              </span>
              <span class="project-copy">
                <strong>{project.title}</strong>
                <small>{project.description}</small>
              </span>
            </a>
          {/each}
        </div>
      </div>
    </nav>
  </aside>

  <div class="special-content">
    <slot />
  </div>
</div>

<style>
  .special-shell {
    display: grid;
    grid-template-columns: 260px minmax(0, 1fr);
    min-height: 100vh;
    background: #f8fafc;
    color: #111827;
  }

  .mobile-menu-bar,
  .mobile-menu-backdrop,
  .mobile-close-button {
    display: none;
  }

  .special-sidebar {
    position: sticky;
    top: 80px;
    align-self: start;
    height: calc(100vh - 80px);
    border-right: 1px solid #e5e7eb;
    background: rgba(248, 250, 252, 0.96);
    padding: 18px 14px;
    overflow: auto;
    z-index: 20;
  }

  .special-nav,
  .projects-group,
  .project-links {
    display: grid;
    gap: 10px;
  }

  .site-link,
  .group-title,
  .project-link {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .site-link {
    min-height: 42px;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    background: #ffffff;
    color: #111827;
    font-weight: 700;
    padding: 0 12px;
    text-decoration: none;
    transition:
      border-color 160ms ease,
      background 160ms ease;
  }

  .site-link:hover {
    border-color: #cbd5e1;
    background: #f9fafb;
  }

  .projects-group {
    margin-top: 8px;
  }

  .group-title {
    min-height: 34px;
    color: #64748b;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0;
    padding: 0 8px;
    text-transform: uppercase;
  }

  .nav-icon,
  .project-icon {
    display: inline-flex;
    width: 28px;
    height: 28px;
    flex: 0 0 auto;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: #f1f5f9;
    color: #334155;
  }

  .project-link {
    min-height: 64px;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #1f2937;
    padding: 10px;
    text-decoration: none;
    transition:
      border-color 160ms ease,
      background 160ms ease,
      color 160ms ease;
  }

  .project-link:hover {
    border-color: #e2e8f0;
    background: #ffffff;
  }

  .project-link.active {
    border-color: #c7d2fe;
    background: #eef2ff;
    color: #1e3a8a;
  }

  .project-link.active .project-icon {
    background: #dbeafe;
    color: #1d4ed8;
  }

  .project-copy {
    display: grid;
    min-width: 0;
    gap: 3px;
  }

  .project-copy strong,
  .project-copy small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .project-copy strong {
    font-size: 14px;
    line-height: 1.15;
  }

  .project-copy small {
    color: #64748b;
    font-size: 12px;
    line-height: 1.2;
  }

  .special-content {
    min-width: 0;
    background: #ffffff;
  }

  :global(.dark) .special-shell {
    background: #09090b;
    color: #f4f4f5;
  }

  :global(.dark) .special-sidebar {
    border-right-color: #27272a;
    background: rgba(9, 9, 11, 0.96);
  }

  :global(.dark) .special-content {
    background: #09090b;
  }

  :global(.dark) .site-link,
  :global(.dark) .project-link:hover {
    border-color: #27272a;
    background: #18181b;
    color: #f4f4f5;
  }

  :global(.dark) .site-link:hover {
    border-color: #3f3f46;
    background: #1f1f23;
  }

  :global(.dark) .group-title,
  :global(.dark) .project-copy small {
    color: #a1a1aa;
  }

  :global(.dark) .nav-icon,
  :global(.dark) .project-icon {
    background: #27272a;
    color: #d4d4d8;
  }

  :global(.dark) .project-link {
    color: #e4e4e7;
  }

  :global(.dark) .project-link.active {
    border-color: #1d4ed8;
    background: #172554;
    color: #bfdbfe;
  }

  :global(.dark) .project-link.active .project-icon {
    background: #1e3a8a;
    color: #dbeafe;
  }

  @media (max-width: 900px) {
    .special-shell {
      display: block;
      margin-top: -16px;
    }

    .mobile-menu-bar {
      position: sticky;
      top: 64px;
      z-index: 30;
      display: flex;
      justify-content: flex-start;
      border-bottom: 1px solid #e5e7eb;
      background: rgba(255, 255, 255, 0.94);
      padding: 10px 12px;
      backdrop-filter: blur(12px);
    }

    .mobile-menu-button {
      display: inline-flex;
      min-height: 38px;
      align-items: center;
      gap: 8px;
      border: 1px solid #d1d5db;
      border-radius: 8px;
      background: #ffffff;
      color: #111827;
      font: inherit;
      font-size: 14px;
      font-weight: 800;
      letter-spacing: 0;
      padding: 0 12px;
    }

    .mobile-menu-backdrop {
      position: fixed;
      inset: 0;
      z-index: 49;
      display: block;
      border: 0;
      background: rgba(15, 23, 42, 0.46);
      padding: 0;
    }

    .mobile-close-button {
      display: inline-flex;
      width: 38px;
      height: 38px;
      align-items: center;
      justify-content: center;
      justify-self: end;
      border: 1px solid #e5e7eb;
      border-radius: 8px;
      background: #ffffff;
      color: #111827;
      padding: 0;
    }

    .special-sidebar {
      position: fixed;
      inset: 0 auto 0 0;
      z-index: 50;
      width: min(320px, 86vw);
      height: 100dvh;
      border-right: 1px solid #e5e7eb;
      border-bottom: 0;
      background: #f8fafc;
      padding: max(16px, env(safe-area-inset-top)) 14px 18px;
      transform: translateX(-105%);
      transition:
        transform 180ms ease,
        visibility 180ms ease;
      visibility: hidden;
      pointer-events: none;
    }

    .special-sidebar.mobile-open {
      transform: translateX(0);
      visibility: visible;
      pointer-events: auto;
    }

    .special-nav {
      gap: 12px;
    }

    .project-links {
      display: grid;
    }

    .project-link {
      min-width: 0;
    }

    .site-link {
      min-height: 38px;
    }

    :global(.dark) .mobile-menu-bar {
      border-bottom-color: #27272a;
      background: rgba(9, 9, 11, 0.92);
    }

    :global(.dark) .mobile-menu-button,
    :global(.dark) .mobile-close-button {
      border-color: #3f3f46;
      background: #18181b;
      color: #f4f4f5;
    }

    :global(.dark) .special-sidebar {
      border-right-color: #27272a;
      background: #09090b;
    }
  }
</style>
