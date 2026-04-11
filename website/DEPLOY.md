# Deploy guide — heymeld.com

The Meld marketing site deploys to Cloudflare Pages via `wrangler pages deploy`.

## Stack summary

| Piece | Where |
|---|---|
| Static site | Astro 5 → `dist/` |
| Waitlist endpoint | Cloudflare Pages Function at `/api/waitlist/subscribe` (TypeScript in `functions/api/waitlist/subscribe.ts`) |
| Waitlist storage | Cloudflare D1 database `heymeld-waitlist` |
| Domain | heymeld.com, zone on account `howard.768@gmail.com` (id `9660df22e259a1dd1fb76d66cb42a706`) |
| DNS | Two proxied CNAMEs: `@` and `www` → `heymeld.pages.dev` |
| Analytics | TelemetryDeck via `PUBLIC_TELEMETRYDECK_APP_ID` env at build time |

## Local dev

```bash
npm install
npm run dev   # http://localhost:4321
```

For the waitlist function to work locally, use `wrangler pages dev` instead:

```bash
npm run build
npx wrangler pages dev dist  # Emulates Pages Functions + D1 locally
```

## Deploying

**Requirements:**
1. Logged into the `howard.768@gmail.com` Cloudflare account via wrangler:
   ```bash
   npx wrangler whoami
   # Should show: Howard.768@gmail.com's Account (9660df22e259a1dd1fb76d66cb42a706)
   ```
2. `PUBLIC_TELEMETRYDECK_APP_ID` set in your shell (optional — falls back to no analytics if unset).
3. `CLOUDFLARE_ACCOUNT_ID` exported because wrangler sometimes falls back to a stale cached account ID from a previous login:
   ```bash
   export CLOUDFLARE_ACCOUNT_ID=9660df22e259a1dd1fb76d66cb42a706
   ```

**Deploy command:**
```bash
PUBLIC_TELEMETRYDECK_APP_ID=FC65E700-0B81-4B6E-8DB7-C5D29B5626BF npm run build
npx wrangler pages deploy dist \
  --project-name heymeld \
  --branch main \
  --commit-message "Your change summary" \
  --commit-dirty=true
```

The preview URL will be `https://<hash>.heymeld.pages.dev`. The production URL is `https://heymeld.com`.

## Gotchas (learned the hard way, 2026-04-11)

1. **`CLOUDFLARE_ACCOUNT_ID` must be exported in the shell, not passed inline.** `FOO=bar npx wrangler ...` silently ignored the env var for `pages deploy`. `export FOO=bar; npx wrangler ...` works.
2. **Wrangler OAuth tokens cannot hit zone-scoped endpoints via direct curl.** For DNS record writes, use a scoped token from `dash.cloudflare.com/profile/api-tokens` (Zone DNS: Edit, restricted to heymeld.com).
3. **Cloudflare doesn't auto-create DNS records** when you add a custom domain to Pages via the API. You must create the CNAME records manually (both `@` and `www` → `heymeld.pages.dev`, proxied).
4. **macOS default browser must be Chrome (not Safari, not Incognito)** for `wrangler login` to complete the OAuth callback correctly.
5. **D1 schema changes:** update `d1-schema.sql`, then run:
   ```bash
   export CLOUDFLARE_ACCOUNT_ID=9660df22e259a1dd1fb76d66cb42a706
   npx wrangler d1 execute heymeld-waitlist --remote --file=./d1-schema.sql
   ```

## Bindings (wrangler.toml)

The Pages Function uses a D1 binding declared in `wrangler.toml`:

```toml
[[d1_databases]]
binding = "DB"
database_name = "heymeld-waitlist"
database_id = "c01d73ef-8195-4b71-ae15-96ada5455acd"
```

Accessed inside `functions/api/waitlist/subscribe.ts` as `env.DB`.

## Production env variables

Set in Cloudflare dashboard: **Workers & Pages → heymeld → Settings → Variables**.

| Variable | Scope | Value |
|---|---|---|
| `PUBLIC_TELEMETRYDECK_APP_ID` | Production + Preview | `FC65E700-0B81-4B6E-8DB7-C5D29B5626BF` (Meld Web app ID) |

These are read at **build time** by Astro via `import.meta.env`, so they must be set before `npm run build` runs. When deploying via `wrangler pages deploy dist`, the build happens locally, so set the env var in your shell before running the build. When deploying via Git integration, Cloudflare sets them for you from the dashboard.

## Git-based deploy (not currently wired)

If you want auto-deploy on push, connect the Pages project to a GitHub repo in the dashboard:

1. Workers & Pages → heymeld → Settings → Git
2. Connect to GitHub repo `howard768/ai-health-coach` (or whichever is canonical)
3. Production branch: `main`
4. Build command: `cd website && npm install && npm run build`
5. Build output directory: `website/dist`
6. Root directory: `/` (the repo root, not `website/`)

Every push to `main` will then auto-deploy without needing `wrangler pages deploy`.

## Rollbacks

```bash
npx wrangler pages deployment list --project-name heymeld
```

Then in the Pages dashboard, click any historical deployment and "Retry deployment" or "Rollback to this version".
