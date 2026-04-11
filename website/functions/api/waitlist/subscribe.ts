/**
 * Waitlist subscribe — Cloudflare Pages Function.
 *
 * POST /api/waitlist/subscribe
 *
 * Body (JSON):
 *   {
 *     email: string (required),
 *     source?: string,
 *     utm_source?: string,
 *     utm_medium?: string,
 *     utm_campaign?: string,
 *     utm_term?: string,
 *     utm_content?: string,
 *   }
 *
 * Response (200):
 *   { status: "ok", message: string, new: boolean }
 *
 * Behavior:
 *   - Idempotent: duplicate email bumps `submissions` counter and refreshes
 *     metadata to the latest values, rather than creating a duplicate row.
 *   - Never stores raw IP: SHA-256 hashed and truncated to 32 chars.
 *   - Country code read from Cloudflare's cf.country (free, no PII).
 *   - Rate-limited at the Pages edge (200 req/min/IP default on free tier).
 *
 * Bindings required (wrangler.toml / Pages env):
 *   - DB: D1 database `heymeld-waitlist`
 */

interface Env {
  DB: D1Database;
}

interface SubscribeBody {
  email?: unknown;
  source?: unknown;
  utm_source?: unknown;
  utm_medium?: unknown;
  utm_campaign?: unknown;
  utm_term?: unknown;
  utm_content?: unknown;
}

const CORS_HEADERS: Record<string, string> = {
  // Same-origin by default — the site and function share a host — but allow
  // the Pages preview subdomains + localhost dev for convenience.
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Access-Control-Max-Age': '86400',
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_EMAIL_LEN = 320;
const MAX_FIELD_LEN = 128;

function json(body: Record<string, unknown>, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      ...CORS_HEADERS,
    },
  });
}

function str(v: unknown, max = MAX_FIELD_LEN): string | null {
  if (typeof v !== 'string') return null;
  const trimmed = v.trim();
  if (!trimmed) return null;
  return trimmed.slice(0, max);
}

async function sha256(input: string): Promise<string> {
  const buf = new TextEncoder().encode(input);
  const hashBuf = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hashBuf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, 32);
}

export const onRequestOptions: PagesFunction<Env> = async () =>
  new Response(null, { status: 204, headers: CORS_HEADERS });

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
  if (!env.DB) {
    return json({ status: 'error', detail: 'Waitlist storage not configured.' }, 500);
  }

  // Parse body defensively.
  let body: SubscribeBody;
  try {
    body = (await request.json()) as SubscribeBody;
  } catch {
    return json({ status: 'error', detail: 'Invalid JSON body.' }, 400);
  }

  // Email validation.
  const rawEmail = typeof body.email === 'string' ? body.email.trim() : '';
  if (!rawEmail || rawEmail.length > MAX_EMAIL_LEN || !EMAIL_RE.test(rawEmail)) {
    return json({ status: 'error', detail: 'Please enter a valid email address.' }, 422);
  }
  const email = rawEmail.toLowerCase();

  // Sanitize optional fields.
  const source = str(body.source, 64);
  const utmSource = str(body.utm_source);
  const utmMedium = str(body.utm_medium);
  const utmCampaign = str(body.utm_campaign);
  const utmTerm = str(body.utm_term);
  const utmContent = str(body.utm_content);

  // Request metadata.
  const referer = request.headers.get('referer')?.slice(0, 512) ?? null;
  const userAgent = request.headers.get('user-agent')?.slice(0, 512) ?? null;
  const ip =
    request.headers.get('cf-connecting-ip') ??
    request.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ??
    null;
  const ipHash = ip ? await sha256(ip) : null;
  // @ts-expect-error — cf is present at runtime on Cloudflare Workers / Pages
  const cfCountry: string | null = (request.cf?.country as string | undefined) ?? null;

  // Look up existing row.
  const existing = (await env.DB.prepare(
    'SELECT id, submissions FROM waitlist_signups WHERE email = ?1'
  )
    .bind(email)
    .first<{ id: number; submissions: number }>()) ?? null;

  if (existing) {
    // Idempotent: bump submissions + refresh metadata to latest values.
    await env.DB.prepare(
      `UPDATE waitlist_signups
       SET submissions = submissions + 1,
           source       = COALESCE(?1, source),
           utm_source   = COALESCE(?2, utm_source),
           utm_medium   = COALESCE(?3, utm_medium),
           utm_campaign = COALESCE(?4, utm_campaign),
           utm_term     = COALESCE(?5, utm_term),
           utm_content  = COALESCE(?6, utm_content),
           updated_at   = datetime('now')
       WHERE id = ?7`
    )
      .bind(source, utmSource, utmMedium, utmCampaign, utmTerm, utmContent, existing.id)
      .run();

    return json({
      status: 'ok',
      message: "You're already on the list. We'll be in touch.",
      new: false,
    });
  }

  // Insert new row. If a race created one between the SELECT and INSERT,
  // the UNIQUE constraint on email will surface here — treat as success.
  try {
    await env.DB.prepare(
      `INSERT INTO waitlist_signups
         (email, source, utm_source, utm_medium, utm_campaign, utm_term, utm_content,
          referer, ip_hash, user_agent, cf_country)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11)`
    )
      .bind(
        email,
        source,
        utmSource,
        utmMedium,
        utmCampaign,
        utmTerm,
        utmContent,
        referer,
        ipHash,
        userAgent,
        cfCountry
      )
      .run();
  } catch (err) {
    // UNIQUE violation race — treat as a dedupe hit.
    const message = err instanceof Error ? err.message : String(err);
    if (/UNIQUE/i.test(message)) {
      return json({
        status: 'ok',
        message: "You're already on the list. We'll be in touch.",
        new: false,
      });
    }
    console.error('waitlist insert failed:', message);
    return json(
      { status: 'error', detail: 'Could not save your email. Please try again.' },
      500
    );
  }

  return json({
    status: 'ok',
    message: "You're on the list. We'll be in touch.",
    new: true,
  });
};
