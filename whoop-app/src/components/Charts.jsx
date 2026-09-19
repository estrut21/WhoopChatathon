import { recoveryColor } from '../data';

export function StressChart({ series, nowMin }) {
  const W = 360;
  const H = 200;
  const L = 34;
  const R = 12;
  const T = 26;
  const B = 32;
  const pw = W - L - R;
  const ph = H - T - B;
  const x = (min) => L + (min / nowMin) * pw;
  const y = (v) => T + ph - (v / 3) * ph;
  const d = series.map(([m, v], i) => `${i ? 'L' : 'M'}${x(m).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const xEnd = x(nowMin);
  const workFrom = x(540);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="stress-grad" x1="0" y1={y(3)} x2="0" y2={y(0.3)} gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#ff5c5c" />
          <stop offset="0.35" stopColor="#ffd60a" />
          <stop offset="0.7" stopColor="#7be36b" />
          <stop offset="1" stopColor="#2cc7c0" />
        </linearGradient>
      </defs>
      <rect x={workFrom} y={T} width={xEnd - workFrom} height={ph} fill="rgba(10,139,232,0.14)" />
      {[0, 1, 2, 3].map((g) => (
        <g key={g}>
          <line x1={L} x2={xEnd} y1={y(g)} y2={y(g)} stroke={g === 3 ? '#7fa3bd' : 'rgba(255,255,255,0.14)'} strokeWidth={g === 3 ? 2 : 1} />
          <text x={L - 8} y={y(g) + 3.5} textAnchor="end" fontSize="10" fontWeight="600" fill="#9aa0a6">
            {g.toFixed(1)}
          </text>
        </g>
      ))}
      <line x1={workFrom} x2={xEnd} y1={y(3)} y2={y(3)} stroke="#0a8be8" strokeWidth="3" />
      <text x={(workFrom + xEnd) / 2} y={T - 8} textAnchor="middle" fontSize="10.5" fontWeight="700" letterSpacing="1" fill="#5aa9f0">
        WORK
      </text>
      <path d={d} fill="none" stroke="url(#stress-grad)" strokeWidth="2" strokeLinejoin="round" />
      <line x1={xEnd} x2={xEnd} y1={T - 4} y2={T + ph} stroke="#fff" strokeDasharray="3 3" />
      <circle cx={xEnd} cy={y(series[series.length - 1][1])} r="3.5" fill="#fff" />
      {[
        [0, '12 AM', 'start'],
        [360, '6 AM', 'middle'],
        [540, '9 AM', 'middle'],
        [720, '12 PM', 'middle'],
      ].map(([m, t, anchor]) => (
        <text key={t} x={x(m)} y={H - 8} textAnchor={anchor} fontSize="10" fontWeight="600" fill="#9aa0a6">
          {t}
        </text>
      ))}
    </svg>
  );
}

export function StressSpark({ series, nowMin }) {
  const W = 190;
  const H = 70;
  const d = series.map(([m, v], i) => `${i ? 'L' : 'M'}${((m / nowMin) * (W - 12)).toFixed(1)} ${(H - 8 - (v / 3) * (H - 16)).toFixed(1)}`).join(' ');
  const lastV = series[series.length - 1][1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="spark-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ff5c5c" />
          <stop offset="0.35" stopColor="#ffd60a" />
          <stop offset="0.7" stopColor="#7be36b" />
          <stop offset="1" stopColor="#2cc7c0" />
        </linearGradient>
      </defs>
      {[0, 1, 2].map((i) => (
        <line key={i} x1="0" x2={W - 10} y1={10 + i * 25} y2={10 + i * 25} stroke="rgba(255,255,255,0.12)" />
      ))}
      <path d={d} fill="none" stroke="url(#spark-grad)" strokeWidth="1.8" strokeLinejoin="round" />
      <line x1={W - 12} x2={W - 12} y1="2" y2={H - 4} stroke="#fff" strokeDasharray="2 3" />
      <circle cx={W - 12} cy={H - 8 - (lastV / 3) * (H - 16)} r="4" fill="#fff" />
    </svg>
  );
}

export function StrainRecoveryChart({ slots, selected }) {
  const W = 360;
  const H = 300;
  const L = 30;
  const R = 34;
  const T = 26;
  const B = 44;
  const pw = W - L - R;
  const ph = H - T - B;
  const x = (i) => L + 10 + (i / 6) * (pw - 20);
  const yS = (v) => T + ph - (v / 21) * ph;
  const yR = (v) => T + ph - (v / 100) * ph;

  const pts = slots.map((s, i) => ({ i, day: s.day })).filter((p) => p.day);
  const line = (fn) => pts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i)} ${fn(p.day)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      <rect x={x(selected) - 17} y={T - 6} width="34" height={ph + B - 4} rx="3" fill="rgba(255,255,255,0.12)" />
      {[
        [21, '21'],
        [14, '14'],
        [7, '7'],
      ].map(([v, t]) => (
        <text key={t} x={L - 12} y={yS(v) + 4} fontSize="11" fontWeight="700" fill="#0a8be8">
          {t}
        </text>
      ))}
      {[
        [100, '#3ef03e', '100%'],
        [66, '#ffd60a', '66%'],
        [33, '#f5344b', '33%'],
      ].map(([v, c, t]) => (
        <text key={t} x={W - R + 6} y={yR(v) + 4} fontSize="11" fontWeight="700" fill={c}>
          {t}
        </text>
      ))}
      {pts.length > 1 && <path d={line((d) => yR(d.recovery))} fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="2" />}
      {pts.length > 1 && <path d={line((d) => yS(d.strain))} fill="none" stroke="#0a8be8" strokeWidth="2" />}
      {slots.map((s, i) => {
        const sel = i === selected;
        return (
          <g key={s.date}>
            {s.day && (
              <>
                <circle cx={x(i)} cy={yS(s.day.strain)} r="4.5" fill="#15181a" stroke="#0a8be8" strokeWidth="2" />
                <text x={x(i)} y={yS(s.day.strain) + 17} textAnchor="middle" fontSize="12" fontWeight="700" fill="#0a8be8">
                  {s.day.strain.toFixed(1)}
                </text>
                <circle cx={x(i)} cy={yR(s.day.recovery)} r="4.5" fill="#15181a" stroke={recoveryColor(s.day.recovery)} strokeWidth="2" />
                <text x={x(i)} y={yR(s.day.recovery) - 10} textAnchor="middle" fontSize="12" fontWeight="700" fill={recoveryColor(s.day.recovery)}>
                  {Math.round(s.day.recovery)}%
                </text>
              </>
            )}
            <text x={x(i)} y={H - 22} textAnchor="middle" fontSize="11" fontWeight={sel ? 700 : 500} fill={sel ? '#fff' : '#9aa0a6'}>
              {s.short}
            </text>
            <text x={x(i)} y={H - 8} textAnchor="middle" fontSize="11" fontWeight={sel ? 700 : 500} fill={sel ? '#fff' : '#9aa0a6'}>
              {s.dom}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
