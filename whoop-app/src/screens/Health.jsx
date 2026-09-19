import { useState } from 'react';
import * as I from '../components/icons';
import { StressSpark } from '../components/Charts';

const PARTICLES = Array.from({ length: 46 }, (_, i) => {
  const a = (i * 2.399) % (Math.PI * 2);
  const r = 24 + ((i * 37) % 86);
  return { x: 115 + Math.cos(a) * r, y: 115 + Math.sin(a) * r, s: 0.8 + ((i * 13) % 10) / 8, o: 0.35 + ((i * 7) % 6) / 10 };
});

function Orb() {
  return (
    <div style={{ position: 'relative', width: 230, height: 230, margin: '0 auto' }}>
      <div style={{ position: 'absolute', inset: -70, background: 'radial-gradient(circle, rgba(44,232,160,0.30) 0%, rgba(44,232,160,0) 65%)' }} />
      <svg width="230" height="230" viewBox="0 0 230 230" style={{ position: 'relative' }}>
        <defs>
          <radialGradient id="orb" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#020504" />
            <stop offset="0.68" stopColor="#03110d" />
            <stop offset="0.9" stopColor="#0f6f5c" />
            <stop offset="1" stopColor="#3fe0b0" />
          </radialGradient>
        </defs>
        <circle cx="115" cy="115" r="113" fill="url(#orb)" stroke="rgba(120,255,210,0.55)" strokeWidth="1.5" />
        {PARTICLES.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={p.s} fill="#7dffd6" opacity={p.o} />
        ))}
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
        <div className="num" style={{ fontSize: 46, fontWeight: 700, lineHeight: 1 }}>20.0</div>
        <div className="label" style={{ fontSize: 12 }}>WHOOP AGE</div>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--mint)', marginTop: 8 }}>2.7 years younger</div>
      </div>
    </div>
  );
}

function PaceRuler({ value }) {
  const ticks = Array.from({ length: 81 }, (_, i) => i);
  const pos = ((value + 1) / 4) * 100;
  return (
    <div style={{ position: 'relative', height: 46, margin: '0 4px' }}>
      <div style={{ position: 'absolute', left: `${pos}%`, top: -34, transform: 'translateX(-50%)', textAlign: 'center' }}>
        <div className="num" style={{ fontSize: 22, fontWeight: 700 }}>{value.toFixed(1)}x</div>
      </div>
      <div style={{ position: 'absolute', inset: '8px 0 0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        {ticks.map((t) => {
          const big = t % 20 === 0;
          const near = Math.abs(t / 20 - 1 - value) < 0.25;
          return <div key={t} style={{ width: 1.2, height: big ? 26 : near ? 24 : 20, background: near ? '#e8ecef' : 'rgba(255,255,255,0.28)' }} />;
        })}
      </div>
      <div style={{ position: 'absolute', left: `${pos}%`, top: 4, bottom: 0, width: 2, background: '#fff', transform: 'translateX(-50%)' }} />
    </div>
  );
}

export default function Health() {
  const [scrollTop, setScrollTop] = useState(0);
  const titleOpacity = Math.max(0, Math.min(1, (scrollTop - 30) / 40));

  return (
    <div className="fade-in">
      <div className="center-title" style={{ opacity: titleOpacity, background: `linear-gradient(180deg, rgba(20,22,24,${0.9 * titleOpacity}), transparent)` }}>
        HEALTH
      </div>
      <div className="scroll" style={{ paddingTop: 48 }} onScroll={(e) => setScrollTop(e.currentTarget.scrollTop)}>
        <Orb />

        <div className="card" style={{ marginTop: 36 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 26 }}>
            <span className="label" style={{ fontSize: 13 }}>PACE OF AGING</span>
            <span className="row" style={{ gap: 6, background: 'rgba(245,165,36,0.16)', color: 'var(--orange)', borderRadius: 6, padding: '5px 9px', fontSize: 11.5, fontWeight: 600 }}>
              <svg width="8" height="6" viewBox="0 0 9 7" fill="currentColor"><path d="M4.5 0L9 7H0z" /></svg>
              faster vs. last week
            </span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 24, fontSize: 14, color: '#b5bac0' }}>
            <span className="row" style={{ gap: 8 }}>
              <span style={{ width: 16, height: 16, borderRadius: '50%', background: '#6b7176', display: 'inline-block' }} /> Slow
            </span>
            <span className="row" style={{ gap: 8 }}>
              Fast <span style={{ width: 16, height: 16, borderRadius: '50%', background: '#6b7176', display: 'inline-block' }} />
            </span>
          </div>
          <PaceRuler value={0.7} />
          <div className="row num" style={{ justifyContent: 'space-between', fontSize: 12, fontWeight: 600, color: '#9aa0a6', margin: '8px 0 18px' }}>
            <span>-1.0x</span>
            <span>1.0x</span>
            <span>3.0x</span>
          </div>
          <button type="button" className="btn-soft">GO TO HEALTHSPAN</button>
        </div>

        <div className="card" style={{ background: 'linear-gradient(120deg, rgba(44,232,160,0.16), rgba(255,255,255,0.06) 55%)' }}>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div style={{ maxWidth: 200 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="label">ADVANCED LABS</span>
              </div>
              <div style={{ fontSize: 13.5, lineHeight: 1.5, color: '#d5d9dd', margin: '14px 0 16px' }}>
                Get deeper health insights, integrating your lab results from doctor visits with your data. No lab results? Test anytime.
              </div>
              <button type="button" className="link">GET STARTED <I.ArrowRight size={18} /></button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', justifyContent: 'space-between' }}>
              <I.ChevR size={16} color="#9aa0a6" />
              <svg width="92" height="92" viewBox="0 0 92 92" fill="none">
                <circle cx="46" cy="46" r="38" stroke="#2ce8a0" strokeWidth="6" strokeDasharray="3 3" />
                <rect x="40" y="16" width="12" height="62" rx="6" fill="#2b2f33" transform="rotate(20 46 46)" />
              </svg>
              <span style={{ fontSize: 9, fontWeight: 700, background: '#0c0e0f', border: '1px solid #3a3f44', borderRadius: 12, padding: '5px 9px' }}>HSA/FSA Eligible</span>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 20 }}>
            <span className="label">HEALTH MONITOR</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 16 }}>
            {[
              ['RESP', I.Lungs],
              ['SPO₂', I.Drop],
              ['RHR', I.HeartDown],
              ['HRV', I.Pulse],
              ['TEMP', I.Thermo],
            ].map(([n, Icon], i) => (
              <div key={n} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, borderLeft: i ? '1px solid rgba(255,255,255,0.1)' : 'none' }}>
                <Icon size={26} color="#c4c8cc" />
                <span className="label" style={{ fontSize: 11 }}>{n}</span>
                <div style={{ width: 24, height: 24, borderRadius: 6, background: 'rgba(44,232,160,0.16)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <I.Check size={15} color="var(--mint)" />
                </div>
              </div>
            ))}
          </div>
          <div className="row" style={{ gap: 12, background: 'rgba(0,0,0,0.28)', borderRadius: 10, padding: '10px 12px', fontSize: 13, fontWeight: 500 }}>
            <div style={{ width: 20, height: 20, borderRadius: 5, background: 'var(--mint)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <I.Check size={14} color="#0c0e0f" />
            </div>
            5/5 metrics within range
          </div>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 22 }}>
            <span className="label">BLOOD PRESSURE INSIGHTS</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div className="label-dim" style={{ color: '#c4c8cc' }}>TODAY&rsquo;S ESTIMATE</div>
              <div className="num" style={{ fontSize: 30, fontWeight: 700, marginTop: 10 }}>117/69</div>
            </div>
            <div className="row" style={{ gap: 12, alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.1)', borderBottom: '1px solid rgba(255,255,255,0.1)', padding: '18px 4px' }}>
              {[0, 1, 0, 1, 2, 0, 1].map((h, i) => (
                <div key={i} style={{ width: 11, height: 18, borderRadius: 3, background: 'rgba(255,255,255,0.12)', position: 'relative' }}>
                  <div style={{ position: 'absolute', left: -1, right: -1, top: 7 + (h === 2 ? -3 : 0), height: 2, background: 'var(--mint)' }} />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 20 }}>
            <span className="label">HEART SCREENER</span>
            <span className="label row" style={{ gap: 8, fontSize: 11.5, color: '#c4c8cc' }}>TAKE AN ECG <I.ChevR size={16} color="#9aa0a6" /></span>
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div className="label-dim" style={{ color: '#c4c8cc' }}>LAST ECG REPORT</div>
              <div style={{ fontSize: 19, fontWeight: 600, margin: '8px 0 10px' }}>Normal Sinus Rhythm</div>
              <span className="row" style={{ gap: 6, background: 'rgba(44,232,160,0.14)', color: 'var(--mint)', borderRadius: 6, padding: '4px 9px', fontSize: 11.5, fontWeight: 600, display: 'inline-flex' }}>
                <I.Check size={12} color="var(--mint)" /> Sep 18, 2026 - 11:44AM
              </span>
            </div>
            <svg width="90" height="90" viewBox="0 0 90 90" fill="none">
              <path d="M45 82C24 66 10 52 10 34c0-9 7-16 16-16 7 0 13 4 19 12 6-8 12-12 19-12 9 0 16 7 16 16 0 18-14 32-35 48z" fill="#4a4f55" opacity="0.7" />
            </svg>
          </div>
        </div>

        <div style={{ margin: '0 18px 14px', padding: 2, borderRadius: 22, background: 'linear-gradient(120deg,#ff8a6a,#b04bff)' }}>
          <div style={{ background: '#22262a', borderRadius: 20, padding: 18 }}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <div style={{ maxWidth: 210 }}>
                <span className="label">CONNECT HEALTH RECORDS</span>
                <div style={{ fontSize: 13.5, lineHeight: 1.5, color: '#d5d9dd', margin: '14px 0 14px' }}>
                  Securely connect your health records, including conditions, medications, and labs, to add deeper context to your insights.
                </div>
                <button type="button" className="link" style={{ color: '#d36bff' }}>GET STARTED <I.ArrowRight size={18} /></button>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <I.ChevR size={16} color="#9aa0a6" />
                <svg width="70" height="60" viewBox="0 0 70 60" fill="none">
                  <rect x="4" y="18" width="62" height="34" rx="5" fill="#3a3f45" />
                  <rect x="4" y="30" width="62" height="22" rx="5" fill="#2b2f33" />
                  <path d="M20 18c0-10 22-10 22 0" stroke="#8a9096" strokeWidth="2.5" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 18 }}>
            <span className="label">STRESS MONITOR</span>
            <I.ChevR size={16} color="#9aa0a6" />
          </div>
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <div>
              <div className="label-dim" style={{ color: '#c4c8cc' }}>TODAY&rsquo;S HIGH STRESS</div>
              <div style={{ margin: '10px 0 12px' }}>
                <span className="num" style={{ fontSize: 34, fontWeight: 700 }}>1:04</span>
                <span style={{ fontSize: 15, color: '#9aa0a6', marginLeft: 6 }}>hrs</span>
              </div>
              <span className="row" style={{ gap: 6, background: 'rgba(245,165,36,0.16)', color: 'var(--orange)', borderRadius: 6, padding: '4px 9px', fontSize: 11.5, fontWeight: 600, display: 'inline-flex' }}>
                <svg width="8" height="6" viewBox="0 0 9 7" fill="currentColor"><path d="M4.5 0L9 7H0z" /></svg>
                vs. typical Sat
              </span>
            </div>
            <div style={{ width: 170 }}>
              <StressSpark />
            </div>
          </div>
        </div>

        <p style={{ margin: '26px 18px 0', paddingTop: 22, borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: 13.5, lineHeight: 1.5, color: '#d5d9dd' }}>
          <strong style={{ color: '#fff' }}>The Heart Screener feature - ECG - is a medically regulated feature.</strong> Healthspan, Health Monitor, Blood Pressure Insights, and Stress Monitor are not medical devices and cannot diagnose or manage medical conditions. These features do not provide medical advice. WHOOP Advanced Labs provides information from independent, third-party laboratories and healthcare providers but is not itself a laboratory, healthcare provider, or medical device. Always consult your doctor for health concerns and never delay or modify medical care based on these features.
        </p>
      </div>
    </div>
  );
}
