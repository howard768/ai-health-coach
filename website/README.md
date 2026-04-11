# heymeld.com

The marketing site for Meld — the AI health coach for iOS.

## Stack

- **Astro 5** — zero-JS by default, islands for interactivity
- **Cloudflare Pages** — hosting (free tier, git-backed)
- **Cloudflare DNS** — heymeld.com zone
- **Railway FastAPI backend** — waitlist form endpoint (`POST /api/waitlist/subscribe`)
- **Roboto** (Google Fonts) — matches the iOS app
- **Design tokens** — mirror `Meld/DesignSystem/Colors.swift` (Purple 600 primary, Green 500 accent, Warm Amber mascot)

## Local dev

```bash
cd website
npm install
npm run dev           # http://localhost:4321
```

## Build + preview

```bash
npm run build
npm run preview
```

## Deploy

Pushed to `main` → Cloudflare Pages auto-builds and deploys. The project is wired to `ai-health-coach` repo under the `website/` directory as the build root.

## Structure

```
website/
├── astro.config.mjs           # Astro config + sitemap
├── package.json
├── public/                    # static files served at root
│   ├── robots.txt             # explicitly allows all major AI crawlers
│   ├── llms.txt               # AI crawler manifest
│   ├── favicon.svg
│   └── _headers               # Cloudflare Pages custom headers
├── src/
│   ├── components/            # 14 components, one per home page section
│   │   ├── Nav.astro
│   │   ├── Hero.astro
│   │   ├── Problem.astro
│   │   ├── Solution.astro
│   │   ├── HowItWorks.astro
│   │   ├── InsideApp.astro
│   │   ├── ResearchGrounded.astro
│   │   ├── DataSources.astro
│   │   ├── PrivacyTrust.astro
│   │   ├── FounderNote.astro
│   │   ├── FAQ.astro
│   │   ├── FinalCTA.astro
│   │   ├── Footer.astro
│   │   ├── WaitlistForm.astro
│   │   └── Mascot.astro       # inline SVG squat blob B
│   ├── content/
│   │   └── journal/           # markdown posts for /journal/*
│   │       └── why-meld.md
│   ├── layouts/
│   │   └── Layout.astro       # shared head, SEO, JSON-LD, fonts
│   ├── pages/
│   │   ├── index.astro        # home (composes all sections)
│   │   ├── privacy.astro
│   │   ├── terms.astro
│   │   └── journal/
│   │       ├── index.astro
│   │       └── [...slug].astro
│   └── styles/
│       ├── tokens.css         # Meld design system tokens
│       └── global.css
└── tsconfig.json
```

## Design system mirror

All tokens match the iOS app's design system. See `src/styles/tokens.css` for the authoritative list, and `[[Design System]]` in the Obsidian wiki for rationale.

## Waitlist wiring

`WaitlistForm.astro` posts to `POST ${PUBLIC_API_BASE}/api/waitlist/subscribe` with `{ email, source, utm_* }`. The `PUBLIC_API_BASE` env var is set to the Railway URL in production and `http://localhost:8000` in dev.
