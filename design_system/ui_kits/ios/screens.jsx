/* global React */
// Meld iOS screens, Dashboard, Coach, Onboarding
// All copy uses Meld voice: 2nd-person, plain, citation-forward, no em dashes.

const C = {
  bg: '#F2F2F7', surface: '#fff', textPrimary: '#121217', textSecondary: '#666673',
  textTertiary: '#737380', purple50: '#faf7ff', purple100: '#f2edfc', purple200: '#ded6f2',
  purple500: '#6b52b8', purple600: '#5438a6', green100: '#e5f7f0', green500: '#219e80',
  greenText: '#178066', amberBody: '#e5a84b', amberTint: '#faf0da',
};

const SANS = '"Roboto", -apple-system, system-ui, sans-serif';

function Mascot({ size = 48, tint = true }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: tint ? C.amberTint : 'transparent',
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
    }}>
      <img src="../../assets/mascot.svg" alt="" style={{ width: size * 0.66, height: size * 0.66 }} />
    </div>
  );
}

// ========== DASHBOARD ==========
function Dashboard() {
  return (
    <div style={{ fontFamily: SANS, background: C.bg, minHeight: '100%', paddingBottom: 100 }}>
      {/* Header */}
      <div style={{ padding: '68px 20px 8px' }}>
        <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary, marginBottom: 6 }}>
          Tue · Apr 16
        </div>
        <div style={{ fontSize: 28, fontWeight: 300, letterSpacing: '-0.015em', color: C.textPrimary, lineHeight: 1.2 }}>
          Good evening, Brock.
        </div>
      </div>

      {/* Readiness hero */}
      <div style={{ margin: '16px 20px', background: C.surface, borderRadius: 20, padding: 22, boxShadow: '0 2px 16px rgba(0,0,0,0.06)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary, marginBottom: 8 }}>
              Readiness
            </div>
            <div>
              <span style={{ fontSize: 56, fontWeight: 100, letterSpacing: '-0.02em', lineHeight: 1, color: C.textPrimary }}>87</span>
              <span style={{ fontSize: 18, color: C.textSecondary, marginLeft: 2 }}>/100</span>
            </div>
            <div style={{ fontSize: 13, color: C.greenText, marginTop: 8 }}>↑ 14 vs your 7-day baseline</div>
          </div>
          {/* Arc gauge */}
          <svg width="84" height="84" viewBox="0 0 84 84">
            <circle cx="42" cy="42" r="36" fill="none" stroke={C.purple100} strokeWidth="6" />
            <circle cx="42" cy="42" r="36" fill="none" stroke={C.purple500} strokeWidth="6"
              strokeLinecap="round" strokeDasharray={`${2 * Math.PI * 36 * 0.87} ${2 * Math.PI * 36}`}
              transform="rotate(-90 42 42)" />
          </svg>
        </div>
        <div style={{ fontSize: 14, fontWeight: 300, color: C.textSecondary, lineHeight: 1.5 }}>
          Your HRV bounced back overnight. Green light for a hard session today.
        </div>
      </div>

      {/* Metric row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, padding: '0 20px' }}>
        {[
          { label: 'Sleep', val: '7h 42m', trend: '↑ 32m', good: true, spark: '0,20 20,16 40,18 60,12 80,14 100,10 120,8' },
          { label: 'HRV', val: '68', unit: 'ms', trend: 'Stable', good: null, spark: '0,14 20,12 40,15 60,11 80,13 100,10 120,12' },
          { label: 'Resting HR', val: '54', unit: 'bpm', trend: '↓ 3', good: true, spark: '0,8 20,10 40,12 60,14 80,16 100,18 120,18' },
          { label: 'Steps', val: '4,218', trend: '62% of goal', good: null, spark: '0,20 20,20 40,18 60,12 80,10 100,14 120,16' },
        ].map((m, i) => (
          <div key={i} style={{ background: C.surface, borderRadius: 16, padding: 16, boxShadow: '0 2px 16px rgba(0,0,0,0.06)' }}>
            <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary, marginBottom: 8 }}>
              {m.label}
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 3 }}>
              <span style={{ fontSize: 32, fontWeight: 300, lineHeight: 1, color: C.textPrimary }}>{m.val}</span>
              {m.unit && <span style={{ fontSize: 13, color: C.textSecondary }}>{m.unit}</span>}
            </div>
            <svg width="100%" height="24" viewBox="0 0 120 24" preserveAspectRatio="none" style={{ marginTop: 8 }}>
              <polyline points={m.spark} fill="none" stroke={m.good ? C.green500 : C.purple500} strokeWidth="1.5" />
            </svg>
            <div style={{ fontSize: 12, fontWeight: 300, color: m.good ? C.greenText : C.textTertiary, marginTop: 4 }}>{m.trend}</div>
          </div>
        ))}
      </div>

      {/* Today's insight */}
      <div style={{ padding: '24px 20px 8px' }}>
        <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary, marginBottom: 12 }}>
          Today's pattern
        </div>
      </div>
      <div style={{ margin: '0 20px', background: C.purple100, borderRadius: 20, padding: 20, display: 'flex', gap: 14 }}>
        <Mascot size={44} />
        <div>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.purple600, marginBottom: 4 }}>
            Pattern found · 21 days
          </div>
          <div style={{ fontSize: 16, fontWeight: 500, color: C.textPrimary, lineHeight: 1.35, marginBottom: 6 }}>
            Your deep sleep goes up 22% on days you eat more protein.
          </div>
          <div style={{ fontSize: 13, fontWeight: 300, color: C.textSecondary, lineHeight: 1.5 }}>
            Front-loading at lunch, not dinner, correlates best. From your Oura sleep + food log.
          </div>
        </div>
      </div>

      {/* Workouts */}
      <div style={{ padding: '24px 20px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary }}>
            Recent
          </div>
          <div style={{ fontSize: 13, color: C.purple600, fontWeight: 500 }}>See all</div>
        </div>
      </div>
      <div style={{ margin: '8px 20px 0', background: C.surface, borderRadius: 16, boxShadow: '0 2px 16px rgba(0,0,0,0.06)', overflow: 'hidden' }}>
        {[
          { t: 'Peloton · 30 min ride', s: 'Yesterday · 312 kcal · avg 142 bpm', d: '●' },
          { t: 'Outdoor walk', s: 'Apr 14 · 48 min · 5,204 steps', d: '●' },
          { t: 'Strength · upper', s: 'Apr 13 · 44 min', d: '●' },
        ].map((w, i, a) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', padding: '14px 16px', borderBottom: i < a.length - 1 ? `1px solid ${C.bg}` : 'none' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.purple500, marginRight: 14 }} />
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, color: C.textPrimary }}>{w.t}</div>
              <div style={{ fontSize: 12, fontWeight: 300, color: C.textTertiary, marginTop: 2 }}>{w.s}</div>
            </div>
            <span style={{ color: C.textTertiary, fontSize: 14 }}>›</span>
          </div>
        ))}
      </div>

      <div style={{ height: 20 }} />
      <TabBar active="home" />
    </div>
  );
}

// ========== TAB BAR ==========
// 5 tabs on a 24pt icon baseline. Coach uses the mascot scaled into the same
// 24pt box as the other icons so everything sits on the same optical line.
// Active state: green-500 dot below label (per DSColor.TabBar.active).
function TabIcon({ name, active }) {
  const stroke = active ? C.purple600 : C.textTertiary;
  const w = active ? 1.8 : 1.5;
  const common = { width: 24, height: 24, viewBox: '0 0 24 24', fill: 'none', stroke, strokeWidth: w, strokeLinecap: 'round', strokeLinejoin: 'round' };
  if (name === 'home')   return <svg {...common}><path d="M4 11l8-6 8 6v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1v-8z"/></svg>;
  if (name === 'trends') return <svg {...common}><path d="M3 17l5-5 4 4 8-8"/><path d="M14 8h6v6"/></svg>;
  if (name === 'log')    return <svg {...common}><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 9v6M9 12h6"/></svg>;
  if (name === 'you')    return <svg {...common}><circle cx="12" cy="9" r="3.5"/><path d="M5 20c1.5-3.5 4.2-5 7-5s5.5 1.5 7 5"/></svg>;
  return null;
}
function TabBar({ active }) {
  const tabs = [
    { id: 'home',   label: 'Today' },
    { id: 'trends', label: 'Trends' },
    { id: 'coach',  label: 'Coach', mascot: true },
    { id: 'log',    label: 'Log' },
    { id: 'you',    label: 'You' },
  ];
  return (
    <div style={{
      position: 'absolute', bottom: 28, left: 14, right: 14,
      background: 'rgba(255,255,255,0.75)',
      backdropFilter: 'blur(24px) saturate(180%)', WebkitBackdropFilter: 'blur(24px) saturate(180%)',
      border: '0.5px solid rgba(255,255,255,0.6)',
      borderRadius: 28, padding: '10px 8px 12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
      display: 'flex', justifyContent: 'space-around',
    }}>
      {tabs.map(t => {
        const isActive = active === t.id;
        return (
          <div key={t.id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '4px 4px 0', flex: 1 }}>
            {/* 24pt icon box, mascot matches the icon box so baselines align */}
            <div style={{ width: 24, height: 24, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {t.mascot ? (
                <img src="../../assets/mascot.svg" alt=""
                  style={{ width: 24, height: 24, opacity: isActive ? 1 : 0.6, transition: 'opacity 200ms' }} />
              ) : (
                <TabIcon name={t.id} active={isActive} />
              )}
            </div>
            <div style={{ fontSize: 10, fontWeight: 500, color: isActive ? C.purple600 : C.textTertiary, letterSpacing: '0.02em', lineHeight: 1 }}>
              {t.label}
            </div>
            {/* Active indicator dot, green-500 per DSColor.TabBar.active */}
            <div style={{ width: 4, height: 4, borderRadius: '50%', background: isActive ? C.green500 : 'transparent' }} />
          </div>
        );
      })}
    </div>
  );
}

// ========== COACH CHAT ==========
function Coach() {
  return (
    <div style={{ fontFamily: SANS, background: C.bg, minHeight: '100%', paddingBottom: 120 }}>
      {/* Header */}
      <div style={{ padding: '64px 20px 16px', background: C.surface, borderBottom: `1px solid ${C.bg}`, display: 'flex', alignItems: 'center', gap: 12 }}>
        <Mascot size={40} />
        <div>
          <div style={{ fontSize: 16, fontWeight: 500, color: C.textPrimary }}>Meld</div>
          <div style={{ fontSize: 12, fontWeight: 300, color: C.greenText, display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.green500 }} />
            Synced 2 min ago
          </div>
        </div>
      </div>

      {/* Messages */}
      <div style={{ padding: '16px 16px 8px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Date stamp */}
        <div style={{ textAlign: 'center', fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.textTertiary, padding: '8px 0' }}>
          Today · 6:42 PM
        </div>

        {/* Meld message with insight card */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <Mascot size={32} />
          <div style={{ flex: 1, background: C.purple100, borderRadius: 20, borderTopLeftRadius: 6, padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 300, color: C.textPrimary, lineHeight: 1.5 }}>
              Your HRV climbed back to 68 ms last night, up from 51 the night before. That tracks with your earlier bedtime and the lighter dinner you logged.
            </div>
            <div style={{ height: 1, background: 'rgba(84,56,166,0.12)', margin: '14px 0' }} />
            <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.purple600, marginBottom: 6 }}>
              Suggested today
            </div>
            <div style={{ fontSize: 14, fontWeight: 400, color: C.textPrimary, lineHeight: 1.45 }}>
              A harder workout. Your readiness is in the top 15% for this month.
            </div>
            <div style={{ fontSize: 12, fontWeight: 300, color: C.textTertiary, marginTop: 10, fontStyle: 'italic' }}>
              Sources: Oura HRV, your food log, Plews 2017 on HRV-guided training.
            </div>
          </div>
        </div>

        {/* User message */}
        <div style={{ alignSelf: 'flex-end', maxWidth: '78%' }}>
          <div style={{ background: C.purple600, color: '#fff', borderRadius: 20, borderTopRightRadius: 6, padding: '12px 16px', fontSize: 14, fontWeight: 400, lineHeight: 1.5 }}>
            Why was last night so different from the one before?
          </div>
        </div>

        {/* Meld reply with bullets */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <Mascot size={32} />
          <div style={{ flex: 1, background: C.purple100, borderRadius: 20, borderTopLeftRadius: 6, padding: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 300, color: C.textPrimary, lineHeight: 1.55 }}>
              Three things lined up on the better night:
            </div>
            <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                ['Bedtime', '10:47 PM vs 11:52 PM the night before.'],
                ['Last meal', '3h 10m before sleep vs 1h 20m.'],
                ['Alcohol', '0 drinks vs 2. Alcohol blunts HRV for roughly 24h.'],
              ].map(([k, v], i) => (
                <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                  <span style={{ color: C.purple500, fontSize: 12, marginTop: 2 }}>•</span>
                  <div style={{ fontSize: 13, fontWeight: 300, color: C.textPrimary, lineHeight: 1.5 }}>
                    <span style={{ fontWeight: 500 }}>{k}:</span> {v}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Quick replies */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', paddingLeft: 42 }}>
          {['Plan tomorrow', 'Show the data', 'Got it'].map(q => (
            <div key={q} style={{ background: C.surface, border: `1px solid ${C.purple200}`, color: C.purple600, padding: '8px 14px', borderRadius: 9999, fontSize: 13, fontWeight: 500 }}>
              {q}
            </div>
          ))}
        </div>
      </div>

      {/* Composer */}
      <div style={{
        position: 'absolute', bottom: 28, left: 14, right: 14,
        background: 'rgba(255,255,255,0.82)', backdropFilter: 'blur(24px) saturate(180%)', WebkitBackdropFilter: 'blur(24px) saturate(180%)',
        border: '0.5px solid rgba(255,255,255,0.6)', borderRadius: 28, padding: '8px 10px 8px 18px',
        boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <input placeholder="Ask Meld anything…" style={{
          flex: 1, border: 'none', background: 'transparent', outline: 'none',
          fontFamily: SANS, fontSize: 15, fontWeight: 300, color: C.textPrimary, padding: '10px 0',
        }} />
        <button style={{
          background: C.purple600, color: '#fff', border: 'none', width: 40, height: 40, borderRadius: 20,
          fontSize: 18, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>↑</button>
      </div>
    </div>
  );
}

// ========== ONBOARDING ==========
function Onboarding() {
  return (
    <div style={{
      fontFamily: SANS, minHeight: '100%',
      background: 'radial-gradient(ellipse 80% 60% at 15% 10%, rgba(184,168,227,0.35) 0%, rgba(184,168,227,0) 55%), radial-gradient(ellipse 70% 50% at 85% 35%, rgba(115,212,186,0.22) 0%, rgba(115,212,186,0) 60%), linear-gradient(180deg, #faf7ff 0%, #ffffff 60%)',
      padding: '80px 24px 40px', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}>
        <Mascot size={96} />
        <div style={{ fontSize: 11, fontWeight: 500, letterSpacing: '0.08em', textTransform: 'uppercase', color: C.purple600, marginTop: 32, marginBottom: 12 }}>
          Step 2 of 4
        </div>
        <div style={{ fontSize: 32, fontWeight: 100, letterSpacing: '-0.02em', color: C.textPrimary, lineHeight: 1.2, marginBottom: 14, maxWidth: 320 }}>
          Let's connect your data.
        </div>
        <div style={{ fontSize: 16, fontWeight: 300, color: C.textSecondary, lineHeight: 1.55, maxWidth: 300 }}>
          Pick the sources you already use. Meld reads them, never sells them, never feeds them to anyone else's AI.
        </div>
      </div>

      {/* Data source cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
        {[
          { name: 'Oura Ring', desc: 'Sleep stages, HRV, readiness', connected: true },
          { name: 'Apple Health', desc: 'Heart, workouts, steps, weight', connected: true },
          { name: 'Peloton', desc: 'Rides, strength, runs', connected: false },
          { name: 'Garmin', desc: 'Training load, recovery', connected: false },
        ].map(s => (
          <div key={s.name} style={{
            background: C.surface, borderRadius: 16, padding: '14px 16px',
            boxShadow: '0 2px 16px rgba(0,0,0,0.06)',
            display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              background: s.connected ? C.green100 : C.bg,
              color: s.connected ? C.greenText : C.textTertiary,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 18, fontWeight: 500,
            }}>{s.name[0]}</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 15, fontWeight: 500, color: C.textPrimary }}>{s.name}</div>
              <div style={{ fontSize: 12, fontWeight: 300, color: C.textTertiary, marginTop: 2 }}>{s.desc}</div>
            </div>
            {s.connected ? (
              <div style={{ fontSize: 12, fontWeight: 500, color: C.greenText, display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: C.green500 }} /> Connected
              </div>
            ) : (
              <div style={{ fontSize: 13, fontWeight: 500, color: C.purple600, background: C.purple100, padding: '6px 12px', borderRadius: 9999 }}>
                Connect
              </div>
            )}
          </div>
        ))}
      </div>

      {/* CTA */}
      <button style={{
        background: C.purple600, color: '#fff', border: 'none',
        padding: '16px 24px', borderRadius: 16, fontFamily: SANS, fontSize: 16, fontWeight: 500,
        boxShadow: '0 8px 24px rgba(84,56,166,0.25)', cursor: 'pointer', marginBottom: 8,
      }}>
        Continue with 2 sources
      </button>
      <button style={{ background: 'transparent', border: 'none', color: C.textTertiary, fontSize: 14, fontWeight: 400, padding: 12, cursor: 'pointer' }}>
        Add more later
      </button>
    </div>
  );
}

Object.assign(window, { Dashboard, Coach, Onboarding });
