import { Link } from 'react-router-dom';
import Ring from '../components/Ring';
import * as I from '../components/icons';
import { DAYS, cognitiveFor, sleepFor } from '../persona';

const BAND_COLOR = { low: 'var(--red)', moderate: 'var(--yellow)', medium: 'var(--yellow)', high: 'var(--rec-green)' };
const MAX_PTS = 10;

function Factor({ f }) {
  const neg = f.pts < 0;
  const width = `${(Math.min(Math.abs(f.pts), MAX_PTS) / MAX_PTS) * 50}%`;
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 7 }}>
        <span style={{ fontSize: 13.5, fontWeight: 500 }}>{f.label}</span>
        <span className="num" style={{ fontSize: 14, fontWeight: 700, color: neg ? 'var(--pink)' : 'var(--mint)' }}>
          {f.pts > 0 ? '+' : ''}
          {f.pts} pts
        </span>
      </div>
      <div style={{ position: 'relative', height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.08)' }}>
        <div style={{ position: 'absolute', left: '50%', top: -3, bottom: -3, width: 1, background: 'rgba(255,255,255,0.3)' }} />
        <div
          style={{
            position: 'absolute',
            top: 0,
            bottom: 0,
            width,
            borderRadius: 4,
            background: neg ? 'var(--pink)' : 'var(--mint)',
            ...(neg ? { right: '50%' } : { left: '50%' }),
          }}
        />
      </div>
      <div className="num" style={{ fontSize: 11, color: '#8a9096', marginTop: 5 }}>z-score {f.z}</div>
    </div>
  );
}

export default function Cognitive() {
  const day = DAYS[DAYS.length - 1];
  const r = day.raw;
  const c = cognitiveFor(day);
  const sl = sleepFor(day);
  const bandColor = BAND_COLOR[c.band.toLowerCase()] || 'var(--pink)';

  return (
    <div className="fade-in">
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 62, zIndex: 5, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(180deg, rgba(20,22,24,0.96) 70%, transparent)' }}>
        <Link to="/" aria-label="Back" style={{ position: 'absolute', left: 16, width: 34, height: 34, borderRadius: '50%', background: 'rgba(255,255,255,0.09)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <I.ChevL size={16} />
        </Link>
        <span className="label" style={{ fontSize: 12.5, letterSpacing: '0.12em' }}>COGNITIVE READINESS</span>
      </div>

      <div className="scroll" style={{ padding: '76px 0 130px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <Ring pct={c.score} size={190} stroke={14} color="var(--pink)">
            <div style={{ textAlign: 'center' }}>
              <div className="num" style={{ fontSize: 50, fontWeight: 700, lineHeight: 1 }}>{Math.round(c.score)}%</div>
              <div className="label" style={{ fontSize: 11, marginTop: 6, color: bandColor }}>{c.band}</div>
            </div>
          </Ring>
          <div className="label-dim" style={{ marginTop: 14 }}>{day.long} &middot; {c.confidence} confidence</div>
          <p style={{ maxWidth: 300, textAlign: 'center', fontSize: 16, fontWeight: 500, lineHeight: 1.4, margin: '14px 0 0' }}>{c.message}</p>
        </div>

        <div className="card" style={{ marginTop: 26 }}>
          <div className="row" style={{ justifyContent: 'space-between', marginBottom: 18 }}>
            <span className="label">WHAT&rsquo;S DRIVING YOUR SCORE</span>
          </div>
          <div className="row" style={{ gap: 8, background: 'rgba(255,95,168,0.12)', borderRadius: 10, padding: '10px 12px', marginBottom: 20, fontSize: 13 }}>
            <I.Info size={17} color="var(--pink)" />
            <span>Top driver: <strong>{c.topDriver}</strong></span>
          </div>
          {c.factors.map((f) => (
            <Factor key={f.key} f={f} />
          ))}
        </div>

        <div className="card">
          <div className="label" style={{ marginBottom: 16 }}>BEHIND THE SCORE</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 14 }}>
            {[
              ['HRV', `${r.hrv} ms`, `baseline ${r.hrv_baseline}`],
              ['RESTING HR', `${r.resting_heart_rate} bpm`, `baseline ${r.rhr_baseline}`],
              ['SLEEP', sl.total, `${sl.efficiency}% efficiency`],
              ['REM', sl.rem, 'hrs:min'],
              ['DEEP', sl.deep, 'hrs:min'],
              ['WAKE-UPS', String(sl.wakeUps), `${sl.latency} min to fall asleep`],
            ].map(([label, value, sub]) => (
              <div key={label}>
                <div className="label-dim" style={{ fontSize: 10.5 }}>{label}</div>
                <div className="num" style={{ fontSize: 22, fontWeight: 700, marginTop: 4 }}>{value}</div>
                <div style={{ fontSize: 11.5, color: '#8a9096', marginTop: 2 }}>{sub}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
