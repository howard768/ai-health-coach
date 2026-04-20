# heymeld.com

The marketing site for Meld : the AI health coach for iOS.

## Stack

- **Astro 5** : zero-JS by default, islands for interactivity
- **Cloudflare Pages** : hosting (free tier, git-backed)
- **Cloudflare DNS** : heymeld.com zone
- **Railway FastAPI backend** : waitlist form endpoint (`POST /api/waitlist/subscribe`)
- **Roboto** (Google Fonts) : matches the iOS app
- **Design tokens** : mirror `Meld/DesignSystem/Colors.swift` (Purple 600 primary, Green 500 accent, Warm Amber mascot)

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
│   ├── components/            # home page sections + reusable bits
│   │   ├── Nav.astro
│   │   ├── Hero.astro
│   │   ├── InsightCardAnimated.astro   # animated hero insight card
│   │   ├── SourcesStrip.astro
│   │   ├── HowItWorks.astro            # 3 steps with mini animations
│   │   ├── Patterns.astro              # horizontal-scroll insight cards
│   │   ├── PhoneTour.astro             # interactive scrubber (4 screens)
│   │   ├── VsChatGPT.astro             # side-by-side comparison
│   │   ├── Science.astro               # citation cards, sticky intro
│   │   ├── PrivacyTrust.astro          # 4 "Never" promises
│   │   ├── FounderNote.astro
│   │   ├── FAQ.astro
│   │   ├── CTA.astro                   # full-bleed purple final CTA
│   │   ├── Footer.astro
│   │   ├── WaitlistForm.astro
│   │   └── Mascot.astro                # animatable inline SVG (breath, blink, eye-track, states)
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
