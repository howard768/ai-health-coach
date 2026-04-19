# Meld Design System

A complete design system for **Meld**, an AI-powered health coaching iOS app. Meld reads sleep, recovery, workouts and nutrition from Oura, Apple Health, Garmin and Peloton, then coaches the user with literature-grounded, cross-domain insights.

- **Product**: Meld (iOS 17+, FastAPI backend, Astro marketing site)
- **Positioning**: *"Your health, synthesized"*, eliminates the friction between fragmented health data and an AI coach
- **Founder**: Brock Howard (ex-VP Product, Lark)
- **Status**: Pre-launch, TestFlight
- **Domain**: heymeld.com

## Sources

This system is derived from the attached codebase `howard768/ai-health-coach` (not pre-loaded, browsed on demand via GitHub):

| Source | What was lifted |
|---|---|
| `Meld/DesignSystem/Tokens/DSColor.swift` | Colors (primary, text, purple, green, status, glass) |
| `Meld/DesignSystem/Tokens/DSTypography.swift` | Roboto scale (Thin/Light/Regular/Medium/Bold) |
| `Meld/DesignSystem/Tokens/DSSpacing.swift` | 4pt spacing grid |
| `Meld/DesignSystem/Tokens/DSRadius.swift` | Continuous corner radii |
| `Meld/DesignSystem/Tokens/DSElevation.swift` | Adaptive light/dark shadow system |
| `Meld/DesignSystem/Tokens/DSMotion.swift` | Spring animation tokens |
| `Meld/DesignSystem/Components/` | Buttons, cards, chips, lists, inputs, avatars |
| `Meld/DesignSystem/Effects/GlassMorphism.swift` | Frosted glass modifier |
| `Meld/DesignSystem/Mascot/MeldMascot.swift` | Squat Blob mascot |
| `Meld/Views/*` | Dashboard, Coach, Onboarding (visual reference) |
| `website/src/styles/tokens.css`, `global.css` | Web mapping of iOS tokens |
| `website/public/favicon.svg` | Pixel-art mascot reused as brand mark |
| `website/public/llms.txt`, `content/journal/why-meld.md` | Voice, tone, positioning |

**Figma (referenced in code)**: `SdHDNSLZVsCtYWs2NttWnj`, Design System page. Not pre-loaded; ask Brock for a share link if you need component-level Figma access.

---

## Index

```
colors_and_type.css       CSS vars (colors, type, spacing, radius, shadow, motion)
README.md                 this file
SKILL.md                  skill manifest for portable use
assets/
  logo.svg                Meld wordmark + mascot lockup
  mascot.svg              Squat Blob mascot (standalone)
  favicon.svg             Purple tile + mascot (browser tab)
preview/                  design-system preview cards (one concept per card)
ui_kits/
  ios/                    Meld iOS app recreation, dashboard, coach chat, onboarding
  website/                Meld marketing site recreation, hero, waitlist, journal
```

---

## CONTENT FUNDAMENTALS

Meld's voice is **second-person, plain, warm, science-backed, and never performative**. It is the voice of a human coach who has already seen your numbers.

### Register

- **Reading level: 4th grade.** Short sentences. No jargon unless immediately explained. Onboarding copy is explicitly audited for this.
- **You/your, not we.** The app talks *to* the user. "We" is reserved for the company (marketing, privacy policy).
- **Never perform intelligence.** No "I noticed an interesting correlation." Just: *"Your deep sleep goes up 22% on days you eat more protein."*
- **Loss-framing over hype.** "Are you reading them?" instead of "Unlock your potential!"
- **Cite the source, always.** Every claim about the user's body ends with where the data came from: *"From your Oura sleep + food log."* Every claim about biology cites research.

### Mechanics

- **Casing**: sentence case. Not Title Case. Not ALL CAPS except for 11pt uppercase `.label` tokens (eyebrow labels, section headers in lists).
- **No em dashes. Anywhere.** This is a hard project rule. Use commas, colons, parens, or sentence breaks.
- **No AI tells**: never "I'm excited to", "I'd be happy to", "Let's dive in", "I noticed", "It seems like".
- **No emoji** in product copy. The mascot carries all warmth. (Emoji acceptable in marketing social posts.)
- **Numbers beat adjectives.** "22%" beats "significantly". "7h 12m" beats "a decent night".
- **Proactive, not chatty.** Coach speaks when it has a real finding. Silence is respected.

### Vocabulary patterns

- **Meld says**: synthesize, connect, pattern, signal, trend, baseline, citation, literature, recovery, readiness, meld (verb), coach (noun + verb).
- **Meld avoids**: journey, unlock, empower, level up, boost, hack, optimize (in isolation), wellness, holistic, mindful, biohack.

### Examples (lifted verbatim from the product)

- Hook: *"Your body sends signals every night. Are you reading them?"*
- Insight card: *"Your deep sleep goes up 22% on days you eat more protein. From your Oura sleep + food log."*
- Proof: *"Meld connects your health data, finds hidden patterns, and tells you exactly what to do each day."*
- Differentiation: *"Meld already knows. ChatGPT knows nothing about your body until you feed it screenshots."*
- Privacy: *"Never sold, never rented, never shared with advertisers. Never used to train generic AI models."*
- Coach reply structure: one data claim → one mechanism → one suggested action → one citation line. Never more than three bullets.

### Copy-decision shortcut

If a sentence could appear unchanged on a crypto landing page, rewrite it.

---

## VISUAL FOUNDATIONS

Meld's visual language is **calm, clinical-but-warm, low-chrome, with one mascot doing the heavy lifting**. It reads like a health product that respects you, not a gamified wellness app.

### Colors

- **Primary brand**: Purple 600 `#5438a6` (favicon, links, primary CTA). Purple 500 `#6b52b8` is the default interactive.
- **Accent**: Green 500 `#219e80` (active tab, success, positive trend). Note: green-500 fails WCAG AA for text on white, so `--green-text: #178066` (green-600) is the only green used for text.
- **Warm amber mascot**: `#e5a84b` body, `#6b4b1a` eyes, `#faf0da` tint background. Mascot is the *only* warm color in the system. It does the emotional work so the rest of the UI can stay cool and restrained.
- **Neutrals**: near-black text `#121217`, 3-step gray backgrounds `#f7f7fa` / `#f2f2f5`.
- **Status**: warning `#e5a626`, error `#d94040`, info `#4d80d9`. Used sparingly, never decoratively.
- **Dark mode**: first-class. Every adaptive color pair defined. Dark mode uses border glows instead of shadows.

### Type

- **Roboto**, exactly 5 weights: Thin 100, Light 300, Regular 400, Medium 500, Bold 700.
- **Display + metric values use Thin.** Large thin numerals are a signature, `48pt Thin` for the big score, `32pt Light` for secondary metrics. This is where the calm comes from.
- **Body copy is Light 300, not Regular.** Unusual but deliberate. Regular reads too heavy next to thin display.
- **Labels are 11pt Medium uppercase with 0.8px tracking.** Eyebrows. Section headers in settings lists.
- **Dynamic Type supported everywhere** via SwiftUI `relativeTo:`.

### Spacing & layout

- **4pt base grid.** Tokens `xxs 2 / xs 4 / sm 8 / md 12 / lg 16 / xl 20 / 2xl 24 / 3xl 32 / 4xl 40 / 5xl 48`.
- **Screen margin is 20pt** on iOS, `clamp(1.25rem, 2.5vw, 2rem)` on web.
- **Vertical rhythm is 8pt.** All gaps between sections are multiples of 8.
- **Cards have 20pt inner padding** (metric cards, insight cards).

### Corners & cards

- **Continuous corners** (iOS squircle). Never the sharp `.circular` style.
- **Radii**: chip 8, input/small card 12, metric card 16, insight card 20, modal 28, pill full.
- **Concentric rule**: inner radius = outer radius minus padding.
- **Metric card** = white surface, 16pt radius, `shadow: 0 2px 16px rgba(0,0,0,0.06)`, 20pt inner padding.
- **Insight card** = `--purple-100` (`#f2edfc`) fill, 20pt radius, **no shadow**. The color alone does the elevation work. This is the single most recognizable pattern in the app.
- **Glass card** = `ultraThinMaterial` + 0.25 white stroke + soft shadow. Used for the tab bar and mascot-adjacent surfaces only.

### Shadows & elevation

- Light mode: five levels, `none`, `low 0 1 2 4%`, `medium 0 2 16 6%`, `high 0 8 32 10%`, `modal 0 16 48 16%`. All blacks, no colored shadows except one hover state (`0 8 32 rgba(84,56,166,0.12)`).
- Dark mode: shadows are replaced with a 1px `white / 0.08` stroke overlay on the same radius. Don't try to use drop shadows on dark surfaces, they don't read.

### Borders & strokes

- Dividers are `#f2f2f5` (bg-tertiary), 1px, inset 16pt from leading edge.
- Inputs: 1px `--text-disabled` default → 2px `--purple-600` focus ring with `--purple-200` outline-offset glow.
- Glassmorphic strokes: `white / 0.25` light mode, `white / 0.12` dark mode.

### Backgrounds

- **Primary app background is solid white / solid near-black.** Not gradient.
- **One gradient exists** and it is only used on the marketing hero and onboarding: `--hero-gradient`, soft purple + soft mint radial blobs over a vertical white-to-purple-50 fade. It reads as atmosphere, not chrome.
- **No repeating patterns, no textures, no grain, no noise overlays, no illustrations-of-humans-doing-yoga.** The mascot carries identity; the canvas is empty on purpose.
- **No full-bleed photography.** If imagery is ever introduced (future), it must be grayscale or warm-filtered to not fight the amber mascot.

### Motion

- **Spring-based, not linear.** Tokens: `micro 0.2s/0.9`, `standard 0.35s/0.85`, `emphasis 0.5s/0.8`, `bouncy 0.5s/0.65`, `snappy 0.25s/0.9`.
- **Bouncy is reserved for the mascot.** The rest of the UI is `snappy` or `standard`.
- **Ambient motion**: mascot breathes (scale 1.0 → 1.03, 2s ease-in-out, repeat). This is the only always-on animation.
- **Page transitions**: fade + 16px translate-Y, 600ms ease-out. No slide-from-right.
- **Reduced motion respected** at every level, all animations become instant.

### Interaction states

- **Hover**: `translateY(-1px)` on primary buttons + shadow intensifies to purple-tinted `--shadow-high`. Cards get `translateY(-2px)`. Links darken from purple-600 → purple-500 (lighter on hover is the rule here, the default is deep purple).
- **Press**: scale 0.98 + haptic selection. No color change.
- **Focus**: 2px purple-600 outline with 3px offset. Non-negotiable, every focusable element has it.
- **Disabled**: 0.6 opacity, `cursor: not-allowed`, no hover transform.
- **Selected**: purple-500 fill + white text (chips, pills) OR green-500 dot indicator (tab bar).

### Transparency & blur

- **Glass is rare.** Only the tab bar and a few modal overlays. Blur 24px + 70% white bg + 0.6 white stroke.
- **Never blur the main content.** Never frost a whole screen.
- **Protection gradients** only under the tab bar to help glass read over scrolling content.

### Iconography vibe

- **Phosphor Duotone** for everything except the mascot. See ICONOGRAPHY below.
- **24pt icons** in tab bar, **13pt semibold chevrons** in list rows.
- **Mascot replaces the Coach tab icon.** This is intentional, the mascot IS the coach.

### Data viz

Four custom primitives: **ArcGauge** (sleep efficiency), **RangeBand** (HRV / RHR relative to baseline), **DotArray** (weekly consistency), **Sparkline** (trends). All use the same 4-color rule: purple for baseline, green for positive trend, warning-amber for caution, error-red for negative. Mini variants (28–48pt) live inside metric cards; full variants live on detail screens.

### Layout rules (fixed)

- **Tab bar**: glass, 5 tabs, 80pt tall, 20pt horizontal padding, safe-area inset, stays put when keyboard opens.
- **Top nav (web)**: 96pt scroll-padding to clear sticky nav on jump links.
- **Prose max-width**: 65ch for paragraphs, 720px for long-form columns.
- **Container max**: 1200px, centered.
- **Section rhythm**: `padding-block: clamp(3rem, 8vw, 6rem)` on marketing.

### What Meld specifically AVOIDS

- Bluish-purple-gradient heroes (flagged explicitly in the code-review agent).
- Rounded-corner cards with a colored left-border accent.
- Emoji cards.
- Hand-drawn illustrated characters (the mascot is pixel-art, on purpose).
- Em dashes, anywhere.
- Full-bleed photography of people.

---

## ICONOGRAPHY

### The mascot (primary brand element)

**The Squat Blob** is the single most distinctive Meld asset. It is a pixel-art character rendered on a 10×7 grid with 4.8-unit square cells, warm-amber body `#e5a84b` with two dark-amber eye pixels `#6b4b1a`. It lives at `assets/mascot.svg` and `assets/favicon.svg` (purple-tile version).

The mascot has six animation states: `idle` (breathing), `thinking` (rotation + opacity pulse), `celebrating` (bouncy scale), `concerned` (gentle shrink), `greeting` (rise-in + fade-in), `error` (horizontal shake). It is rendered at size 24–96pt throughout the app and **replaces the Coach tab icon**.

### Icon set

- **Phosphor Icons** (`phosphor-icons/web` on CDN, or `PhosphorSwift` on iOS), **Light** weight for inactive, **Duotone** for active/selected.
- Used in: tab bar, list rows, empty states, data source badges.
- On iOS, a few SF Symbols are used where no Phosphor equivalent exists (chevron, hand.thumbsup, person.fill). When substituting on web, use the matching Phosphor name.

**CDN (web)**:
```html
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/fill/style.css">
<i class="ph ph-house"></i>           <!-- inactive -->
<i class="ph-fill ph-house"></i>      <!-- active -->
```

### Data-source badges

Each connected data source has a square badge (`Meld/Resources/Assets.xcassets/DataSourceIcons/`): Apple Health, Oura, Garmin, Peloton. The iOS app ships a proprietary Oura SVG (`oura-icon.svg`, 33KB) and `.imageset` placeholders for the others. **These are brand-owned assets and are not reproduced here**, when mocking a screen that needs them, either use a neutral circle placeholder with the brand's initial letter, or ask the user for the originals.

### Emoji

**Not used.** The mascot does all the emotional work. A single exception: social-media marketing copy may use one emoji per post. Product UI never.

### Unicode

- `•` (U+2022) as the bullet glyph in coach markdown, rendered in `--purple-500`.
- `↑ ↓` for trend indicators in metric subtitles (e.g. *"↑ 14% vs baseline"*). Inherits text color, green-text for positive, status-error for negative.

### Substitutions flagged

- **Roboto** is loaded from Google Fonts here; the iOS app ships the TTFs directly. No substitution, same typeface family.
- **Phosphor Icons** on web matches Phosphor Duotone on iOS, no substitution.
- **No substitutions** for the mascot, wordmark, or favicon. All are original.

---

## Quick usage

Link the stylesheet and you get every token:

```html
<link rel="stylesheet" href="colors_and_type.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/fill/style.css">
```

```css
.my-card {
  background: var(--surface-primary);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-card);
  padding: var(--sp-xl);
}
.my-insight {
  background: var(--purple-100);
  border-radius: var(--r-xl);
  padding: var(--sp-xl);
  /* no shadow by design */
}
```

See `ui_kits/` for working examples.
