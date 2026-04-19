# Meld Design System, SKILL.md

Use this skill when designing for **Meld**, an AI health-coach iOS app. Pre-launch, TestFlight, heymeld.com.

## Load first

- `colors_and_type.css`, all tokens (colors, type, spacing, radius, shadow, motion)
- `README.md`, full spec: content voice, visual foundations, iconography, what to avoid
- `assets/mascot.svg`, `assets/logo.svg`, `assets/favicon.svg`, the only branded elements; reuse, never redraw

## Required first step

Read `README.md` completely before producing anything. The product has strong content rules (no em dashes, 4th-grade reading level, always cite sources, second-person) and strong visual rules (Thin numerals for metrics, insight cards use `--purple-100` with NO shadow, mascot is the only warm color) that are easy to violate if you skim.

## Quick setup

```html
<link rel="stylesheet" href="colors_and_type.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/regular/style.css">
<link rel="stylesheet" href="https://unpkg.com/@phosphor-icons/web@2.1.1/src/fill/style.css">
```

## Signature patterns (copy these)

- **Metric card**, white, `--r-lg`, `--shadow-card`, 20pt padding, big value in `--fw-thin` at 48px with `-0.02em` letter-spacing, mini sparkline in `--green-500` (positive) or `--purple-500` (neutral).
- **Insight card**, `--purple-100` fill, `--r-xl`, 20pt padding, **no shadow**, mascot on left in 44pt `--amber-tint` bubble, one data claim + mechanism + citation line. Citation line is italic, `--text-tertiary`, 12px.
- **Mascot bubble**, circle, size-adaptive (32/44/72/96), background `--amber-tint`, mascot sized 66% of container.
- **Tab bar (iOS)**, glass (rgba white 0.75 + 24px blur), 28pt radius, floats 28pt from bottom with 14pt side inset, 5 tabs, Coach tab uses mascot instead of icon.
- **Hero gradient**, `var(--hero-gradient)`, ONLY on marketing hero and onboarding step 1. Nowhere else.

## Voice cheat-sheet

- Second person ("you/your"), never "we" in product copy.
- 4th-grade reading level. Short sentences.
- Every body-claim ends with source: *"From your Oura sleep + food log."*
- Numbers beat adjectives: "22%" > "significantly".
- **No em dashes anywhere.** Hard rule. Use commas, colons, parens.
- No emoji in product UI.
- No AI tells: never "I noticed", "Let's dive in", "I'm excited to".

## Do / don't

| Do | Don't |
|---|---|
| Use Thin/Light for metric numbers | Use Bold for numbers, looks like a fintech app |
| Put insight cards on solid white canvas | Put insight cards on the hero gradient |
| Cite every claim about the user | Assert patterns without saying where the data came from |
| Use Phosphor Duotone for active icons | Use emoji, Lucide, Heroicons, or Material |
| Let the mascot carry warmth | Add illustrated humans, photos, or gradients to UI |
| Use `--purple-600` for primary CTA | Use `--purple-500` for CTA, that's the hover shade |
| Use `--green-text` (#178066) for green text | Use `--green-500` for text, fails WCAG AA |

## Reference implementations

- `ui_kits/ios/index.html`, Dashboard, Coach chat, Onboarding (390×844 iPhone frames)
- `ui_kits/website/index.html`, Marketing site with hero, patterns, compare table, journal, waitlist
- `preview/*.html`, one concept per card (colors, type, components, spacing)

## If asked for assets not in this system

- **Data-source brand icons** (Oura, Garmin, Apple Health, Peloton): NOT included, these are third-party brand assets. Use a neutral circular placeholder with the first letter, or ask the user for originals.
- **Illustrations of people**: DO NOT add. Use the mascot and abstract data viz instead.
- **Photography**: DO NOT add without asking. If approved, must be warm-filtered or grayscale so it doesn't fight the amber mascot.

## Figma

The source-of-truth Figma is `SdHDNSLZVsCtYWs2NttWnj` (Design System page). Not pre-loaded. Ask Brock for a share link if component-level specs are needed beyond what's in `colors_and_type.css`.
