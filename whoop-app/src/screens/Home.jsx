import { useState } from 'react';
import Ring from '../components/Ring';
import { StressChart, StrainRecoveryChart } from '../components/Charts';
import * as I from '../components/icons';
import { Link } from 'react-router-dom';
import { recoveryColor, DISCOVER } from '../data';
import { DAYS, activitiesFor, dashboardFor, cognitiveFor, weekSlots, stressFor } from '../persona';

const STEEL = 'var(--steel)';
const BLUE = 'var(--blue)';
const PINK = 'var(--pink)';

function Trend({ kind }) {
  const map = {
    'down-orange': ['down', 'var(--orange)'],
    'down-green': ['down', 'var(--mint)'],
    'down-gray': ['down', '#8a9096'],
    'up-green': ['up', 'var(--mint)'],
    'up-orange': ['up', 'var(--orange)'],
    flat: ['dot', '#8a9096'],
  };
  const [dir, color] = map[kind];
  if (dir === 'dot') return <span style={{ width: 7, height: 7, borderRadius: '50%', background: color, display: 'inline-block' }} />;
  return (
    <svg width="9" height="7" viewBox="0 0 9 7" fill={color}>
      {dir === 'up' ? <path d="M4.5 0L9 7H0z" /> : <path d="M4.5 7L0 0h9z" />}
    </svg>
  );
}

const DASH_ICONS = { hrv: I.Pulse, rhr: I.HeartDown, resp: I.Lungs, temp: I.Thermo, z13: I.HeartZones, z45: I.HeartZones, cal: I.FlameOutline };

function SummaryRing({ label, pct, display, color, to, size = 78, stroke = 6 }) {
  const Wrap = to ? Link : 'div';
  return (
    <Wrap to={to} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
      <Ring pct={pct} size={size} stroke={stroke} color={color}>
        <div className="num" style={{ fontSize: 23, fontWeight: 700 }}>
          {display}
        </div>
      </Ring>
      <div className="label" style={{ fontSize: 10, letterSpacing: '0.08em', display: 'flex', alignItems: 'center', gap: 2 }}>
        {label}
        <I.ChevR size={11} color="#9aa0a6" />
      </div>
    </Wrap>
  );
}

function ActivityRow({ a }) {
  const tile = a.kind === 'sleep' ? STEEL : BLUE;
  const Icon = a.kind === 'sleep' ? I.Moon : a.kind === 'walk' ? I.Walk : a.kind === 'lift' ? I.Dumbbell : I.Stopwatch;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 14, background: 'rgba(255,255,255,0.06)', borderRadius: 14, padding: '9px 10px', marginBottom: 10 }}>
      <div style={{ width: 76, height: 40, borderRadius: 10, background: tile, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
        <Icon size={19} color="#fff" />
        <span className="num" style={{ fontSize: 19, fontWeight: 700 }}>
          {a.value}
        </span>
      </div>
      <div className="label" style={{ flexGrow: 1, fontSize: 12.5 }}>
        {a.name}
      </div>
      {a.detail && (
        <div className="num" style={{ fontSize: 12, fontWeight: 500, color: '#c4c8cc', textAlign: 'right' }}>
          {a.detail}
        </div>
      )}
      <div style={{ width: 2, height: 32, background: '#3fa9ff', borderRadius: 2 }} />
    </div>
  );
}

export default function Home() {
  const [day, setDay] = useState(DAYS.length - 1);
  const [scrollTop, setScrollTop] = useState(0);
  const [alarm, setAlarm] = useState(false);
  const [journal, setJournal] = useState([true, true, true, true, true, true, false]);

  const d = DAYS[day];
  const isLast = day === DAYS.length - 1;
  const dayLabel = d.long;
  const slots = weekSlots(DAYS[DAYS.length - 1].date);
  const selectedSlot = slots.findIndex((s) => s.date === d.date);
  const activities = activitiesFor(d);
  const dashboard = dashboardFor(d);
  const cog = cognitiveFor(d);
  const stress = stressFor(d);
  const miniOpacity = Math.max(0, Math.min(1, (scrollTop - 240) / 50));

  const rings = [
    { label: 'SLEEP', pct: d.sleep, display: `${Math.round(d.sleep)}%`, color: STEEL },
    { label: 'COGNITIVE', pct: d.cognitive, display: `${Math.round(d.cognitive)}%`, color: PINK, to: '/cognitive' },
    { label: 'RECOVERY', pct: d.recovery, display: `${Math.round(d.recovery)}%`, color: recoveryColor(d.recovery) },
    { label: 'STRAIN', pct: (d.strain / 21) * 100, display: d.strain.toFixed(1), color: BLUE },
  ];

  return (
    <div className="fade-in">
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 64,
          zIndex: 5,
          opacity: miniOpacity,
          pointerEvents: 'none',
          background: 'linear-gradient(180deg, rgba(18,20,22,0.96) 60%, rgba(18,20,22,0))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-around',
          padding: '4px 12px 0',
        }}
      >
        {rings.map((r) => (
          <div key={r.label} className="row" style={{ gap: 6 }}>
            <Ring pct={r.pct} size={24} stroke={3} color={r.color} />
            <span className="label" style={{ fontSize: 9.5, letterSpacing: '0.06em' }}>
              {r.label}
            </span>
          </div>
        ))}
      </div>

      <div className="scroll" onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}>
        <div className="row pad" style={{ justifyContent: 'space-between', height: 44 }}>
          <div className="row" style={{ gap: 12 }}>
            <button type="button" aria-label="Profile" style={{ background: 'none', border: 'none', padding: 0, display: 'flex' }}>
              <I.UserCircle size={34} color="#fff" />
            </button>
            <div className="row" style={{ gap: 5, background: 'rgba(255,255,255,0.09)', borderRadius: 20, padding: '6px 12px 6px 9px' }}>
              <I.Flame size={17} color="#f5732a" />
              <span className="num" style={{ fontSize: 15, fontWeight: 700 }}>
                107
              </span>
            </div>
          </div>

          <div className="row" style={{ background: 'rgba(255,255,255,0.09)', borderRadius: 22, height: 34, width: 138, justifyContent: 'space-between', padding: '0 4px' }}>
            <button
              type="button"
              aria-label="Previous day"
              disabled={day === 0}
              onClick={() => setDay((v) => Math.max(0, v - 1))}
              style={{ background: 'none', border: 'none', display: 'flex', opacity: day === 0 ? 0.3 : 1, padding: 6 }}
            >
              <I.ChevL size={13} />
            </button>
            <span className="label" style={{ fontSize: 11.5 }}>
              {dayLabel}
            </span>
            <button
              type="button"
              aria-label="Next day"
              disabled={isLast}
              onClick={() => setDay((v) => Math.min(DAYS.length - 1, v + 1))}
              style={{ background: 'none', border: 'none', display: 'flex', opacity: isLast ? 0.3 : 1, padding: 6 }}
            >
              <I.ChevR size={13} />
            </button>
          </div>

          <div className="row" style={{ gap: 6 }}>
            <span className="num" style={{ fontSize: 12.5, fontWeight: 500, color: '#9aa0a6' }}>
              46%
            </span>
            <div style={{ position: 'relative', display: 'flex' }}>
              <I.Band size={26} color="#dfe3e6" />
              <span style={{ position: 'absolute', top: -1, right: -3, width: 8, height: 8, borderRadius: '50%', background: 'var(--mint)' }} />
            </div>
          </div>
        </div>

        <div style={{ textAlign: 'center', marginTop: 16, fontSize: 15, fontWeight: 300, letterSpacing: '0.32em', color: '#e6e9ec' }}>WHOOP</div>

        <div style={{ display: 'flex', justifyContent: 'space-around', padding: '22px 8px 0' }}>
          {rings.map((r) => (
            <SummaryRing key={r.label} {...r} />
          ))}
        </div>

        <div style={{ position: 'relative', textAlign: 'center', padding: '44px 0 40px' }}>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <div style={{ width: 52, height: 52, borderRadius: '50%', border: '2px solid #6b7176', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <I.Check size={24} color="#8a9096" />
            </div>
          </div>
          <div style={{ marginTop: 12, fontSize: 20, fontWeight: 500, color: '#6b7176' }}>You&rsquo;re all set.</div>
          <div
            style={{
              position: 'absolute',
              right: 0,
              top: 12,
              width: 56,
              height: 56,
              borderRadius: '14px 0 0 14px',
              background: 'linear-gradient(135deg,#6a5cff,#3fa9ff)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <I.Check size={26} color="#fff" />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, padding: '0 18px', marginBottom: 26 }}>
          <button type="button" className="card" style={{ flex: 1, margin: 0, padding: 14, textAlign: 'left', minWidth: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="label" style={{ fontSize: 10.5, letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>HEALTH MONITOR</span>
              <I.ChevR size={16} color="#9aa0a6" />
            </div>
            <div className="row" style={{ gap: 10, marginTop: 14 }}>
              <div style={{ width: 30, height: 30, borderRadius: 8, background: 'rgba(44,232,160,0.16)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <I.Check size={16} color="var(--mint)" />
              </div>
              <div>
                <div style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--mint)', letterSpacing: '0.04em', whiteSpace: 'nowrap' }}>WITHIN RANGE</div>
                <div style={{ fontSize: 12, color: '#c4c8cc', marginTop: 2 }}>5/5 Metrics</div>
              </div>
            </div>
          </button>
          <button type="button" className="card" style={{ flex: 1, margin: 0, padding: 14, textAlign: 'left', minWidth: 0 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <span className="label" style={{ fontSize: 10.5, letterSpacing: '0.06em', whiteSpace: 'nowrap' }}>STRESS MONITOR</span>
              <I.ChevR size={16} color="#9aa0a6" />
            </div>
            <div className="row" style={{ gap: 10, marginTop: 14 }}>
              <div className="num" style={{ width: 30, height: 30, borderRadius: 8, background: stress.tint, display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, color: stress.color, fontSize: 15 }}>
                {stress.current}
              </div>
              <div>
                <div style={{ fontSize: 11.5, fontWeight: 700, color: stress.color, letterSpacing: '0.06em' }}>{stress.band}</div>
                <div style={{ fontSize: 12, color: '#c4c8cc', marginTop: 2 }}>{stress.lastUpdated}</div>
              </div>
            </div>
          </button>
        </div>

        <div className="row pad" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
          <h2 className="h2">My Day</h2>
          <button type="button" aria-label="Add to my day" style={{ width: 42, height: 42, borderRadius: 12, border: 'none', background: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <I.Plus size={22} color="#000" />
          </button>
        </div>

        <Link
          to="/cognitive"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            margin: '0 18px 14px',
            minHeight: 54,
            borderRadius: 14,
            background: 'linear-gradient(90deg,#77705f,#525c68)',
            padding: '10px 16px',
          }}
        >
          <I.Sun size={22} color="#f3e9d2" />
          <span style={{ flexGrow: 1 }}>
            <span style={{ display: 'block', fontSize: 15.5, fontWeight: 600 }}>Daily Outlook</span>
            <span style={{ display: 'block', fontSize: 12, color: '#e6e0d0', marginTop: 2, lineHeight: 1.35 }}>{cog.message}</span>
          </span>
          <I.ChevR size={16} color="#f0c674" />
        </Link>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
            <span className="label">TODAY&rsquo;S ACTIVITIES</span>
            <I.Expand size={18} color="#9aa0a6" />
          </div>
          {activities.map((a) => (
            <ActivityRow key={a.name} a={a} />
          ))}
          {!d.raw.workout_completed && (
            <div style={{ fontSize: 12.5, color: '#9aa0a6', margin: '2px 2px 14px' }}>Rest day. No activity logged.</div>
          )}
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <button type="button" className="btn-soft" style={{ fontSize: 11.5 }}>
              <I.Plus size={16} /> ADD ACTIVITY
            </button>
            <button type="button" className="btn-soft" style={{ fontSize: 11.5 }}>
              <I.Stopwatch size={16} /> START ACTIVITY
            </button>
          </div>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="label">TONIGHT&rsquo;S SLEEP</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-around', margin: '22px 0 20px' }}>
            <div style={{ textAlign: 'center' }}>
              <div className="row" style={{ gap: 8, justifyContent: 'center' }}>
                <I.Sunrise size={24} color="#c4c8cc" />
                <span className="num" style={{ fontSize: 26, fontWeight: 700 }}>12:45</span>
              </div>
              <div className="label-dim" style={{ marginTop: 6, color: '#c4c8cc', lineHeight: 1.5 }}>
                RECOMMENDED
                <br />
                BEDTIME
              </div>
            </div>
            <div style={{ width: 70, borderTop: '1px dashed rgba(255,255,255,0.25)' }} />
            <div style={{ textAlign: 'center' }}>
              <div className="row" style={{ gap: 8, justifyContent: 'center' }}>
                <I.Sunrise size={24} color="#c4c8cc" />
                <span className="num" style={{ fontSize: 26, fontWeight: 700 }}>9:00</span>
              </div>
              <div className="label-dim" style={{ marginTop: 6, color: alarm ? 'var(--mint)' : 'var(--orange)', fontWeight: 700 }}>
                {alarm ? 'ALARM ON' : 'ALARM OFF'}
              </div>
            </div>
          </div>
          <button type="button" className="btn-soft" onClick={() => setAlarm((v) => !v)}>
            <I.Alarm size={18} /> {alarm ? 'CANCEL ALARM' : 'SET ALARM'}
          </button>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 18 }}>
            <span className="label">MY JOURNAL</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-between', padding: '0 4px', marginBottom: 20 }}>
            {['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'].map((name, i) => (
              <div key={name} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
                <span className="label-dim" style={{ fontSize: 10.5, color: i === 6 ? '#fff' : 'var(--dim)', fontWeight: 700 }}>
                  {name}
                </span>
                <button
                  type="button"
                  aria-label={`Toggle ${name} journal`}
                  aria-pressed={journal[i]}
                  onClick={() => setJournal((j) => j.map((v, k) => (k === i ? !v : v)))}
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: '50%',
                    border: 'none',
                    background: journal[i] ? 'var(--mint)' : '#8a9096',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 0,
                  }}
                >
                  {journal[i] && <I.Check size={15} color="#0c0e0f" />}
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-soft">
            <I.Bulb size={18} /> BEHAVIOR INSIGHTS
          </button>
        </div>

        <div className="pad" style={{ margin: '26px 0 14px' }}>
          <h2 className="h2">My Plan</h2>
        </div>
        <div className="card row" style={{ justifyContent: 'space-between', gap: 8, padding: 22 }}>
          <div style={{ maxWidth: 200 }}>
            <div style={{ fontSize: 15.5, fontWeight: 600 }}>Build Your Best Self</div>
            <div style={{ fontSize: 13, lineHeight: 1.5, color: '#b5bac0', margin: '8px 0 14px' }}>Set goals, track progress, and turn small actions into long-term wins.</div>
            <button type="button" className="link">
              EXPLORE PLANS <I.ArrowRight size={18} />
            </button>
          </div>
          <svg width="110" height="110" viewBox="0 0 110 110" fill="none" style={{ flexShrink: 0 }}>
            <circle cx="70" cy="34" r="26" stroke="#2ce8a0" strokeWidth="3" strokeDasharray="7 5" fill="rgba(255,255,255,0.08)" />
            <circle cx="24" cy="54" r="15" stroke="#5a6068" strokeWidth="2" fill="rgba(255,255,255,0.06)" />
            <circle cx="52" cy="84" r="19" stroke="#2ce8a0" strokeWidth="3" strokeDasharray="7 5" fill="rgba(255,255,255,0.08)" />
            <path d="M64 28a9 9 0 1010 10 7 7 0 01-10-10z" fill="#c4c8cc" />
          </svg>
        </div>

        <div className="row pad" style={{ justifyContent: 'space-between', margin: '26px 0 14px' }}>
          <h2 className="h2">My Dashboard</h2>
          <button
            type="button"
            style={{ border: 'none', borderRadius: 6, padding: '9px 14px', background: 'linear-gradient(90deg,#ff7a8a,#b04bff)', display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, fontWeight: 700, letterSpacing: '0.1em' }}
          >
            CUSTOMIZE <I.Pencil size={16} />
          </button>
        </div>
        {dashboard.map((m) => {
          const Icon = DASH_ICONS[m.key];
          return (
            <div key={m.key} className="card row" style={{ justifyContent: 'space-between', padding: '16px 18px', marginBottom: 10 }}>
              <div className="row" style={{ gap: 14 }}>
                <Icon size={24} color="#c4c8cc" />
                <span className="label" style={{ fontSize: 12 }}>{m.label}</span>
              </div>
              <div className="row" style={{ gap: 7, alignItems: 'flex-start' }}>
                <div style={{ textAlign: 'right' }}>
                  <div className="num" style={{ fontSize: 24, fontWeight: 700, lineHeight: 1 }}>{m.value}</div>
                  {m.prev && <div className="num" style={{ fontSize: 12, color: '#8a9096', marginTop: 3 }}>{m.prev}</div>}
                </div>
                {m.trend && (
                  <div style={{ paddingTop: 9 }}>
                    <Trend kind={m.trend} />
                  </div>
                )}
              </div>
            </div>
          );
        })}

        <div className="card" style={{ marginTop: 14 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 14 }}>
            <span className="label">STRESS MONITOR</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 13, color: '#b5bac0' }}>Last updated {stress.lastUpdated}</span>
            <span className="row" style={{ gap: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: stress.color, letterSpacing: '0.06em' }}>{stress.band}</span>
              <span className="num" style={{ fontSize: 22, fontWeight: 700 }}>{stress.current}</span>
            </span>
          </div>
          <StressChart series={stress.series} nowMin={stress.nowMin} />
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 10 }}>
            <span className="label">STRAIN &amp; RECOVERY</span>
            <I.Info size={20} color="#9aa0a6" />
          </div>
          <StrainRecoveryChart slots={slots} selected={selectedSlot} />
        </div>

        <div className="pad" style={{ margin: '26px 0 14px' }}>
          <h2 className="h2">Discover More</h2>
        </div>
        {DISCOVER.map((c) => (
          <div key={c.title} className="card row" style={{ gap: 16, padding: 16, marginBottom: 12 }}>
            <div style={{ width: 82, height: 82, borderRadius: 12, flexShrink: 0, background: `linear-gradient(135deg, ${c.tint[0]}, ${c.tint[1]})` }} />
            <div>
              <div style={{ fontSize: 15.5, fontWeight: 500, lineHeight: 1.3 }}>{c.title}</div>
              <div style={{ fontSize: 12.5, lineHeight: 1.45, color: '#b5bac0', margin: '6px 0 10px' }}>{c.body}</div>
              <button type="button" className="link">
                {c.cta} <I.ArrowRight size={17} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
