import { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { TabHome, TabHealth, TabCommunity, TabMore, WLogo } from './icons';

const TABS = [
  { to: '/', label: 'Home', Icon: TabHome, end: true },
  { to: '/health', label: 'Health', Icon: TabHealth },
  { to: '/community', label: 'Community', Icon: TabCommunity },
  { to: '/more', label: 'More', Icon: TabMore },
];

export function useSplash(ms = 900) {
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const t = setTimeout(() => setLoading(false), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return loading;
}

export function Splash({ text, color = '#fff', bg = 'transparent' }) {
  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        background: bg,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 26,
        zIndex: 4,
      }}
    >
      {text ? (
        <>
          <div style={{ width: 104, height: 104, borderRadius: '50%', border: '3px solid #fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <WLogo size={54} color="#fff" sw={2.6} />
          </div>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.16em' }}>{text}</div>
        </>
      ) : (
        <div style={{ animation: 'pulse-w 1s ease-in-out infinite' }}>
          <WLogo size={46} color={color} sw={3} />
        </div>
      )}
    </div>
  );
}

export default function Shell() {
  const chat = useState(() => [
    { id: 0, role: 'assistant', text: 'Hi, I\u2019m WHOOP Coach. Ask me about your cognitive readiness, recovery, sleep or strain today.' },
  ]);

  return (
    <div className="phone">
      <div className="viewport">
        <Outlet context={{ chat }} />
      </div>

      <nav
        aria-label="Primary"
        style={{
          position: 'absolute',
          left: 12,
          right: 12,
          bottom: 18,
          height: 68,
          borderRadius: 34,
          background: 'rgba(38,42,46,0.82)',
          backdropFilter: 'blur(22px)',
          WebkitBackdropFilter: 'blur(22px)',
          border: '1px solid rgba(255,255,255,0.07)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-around',
          padding: '0 6px',
          zIndex: 10,
        }}
      >
        {TABS.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            style={({ isActive }) => ({
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 4,
              width: 64,
              padding: '8px 0 6px',
              borderRadius: 22,
              color: isActive ? '#fff' : '#8a9096',
              background: isActive ? 'rgba(255,255,255,0.07)' : 'transparent',
            })}
          >
            <Icon size={24} />
            <span style={{ fontSize: 10.5, fontWeight: 600 }}>{label}</span>
          </NavLink>
        ))}

        <NavLink
          to="/chat"
          aria-label="Ask WHOOP"
          style={({ isActive }) => ({
            width: 52,
            height: 52,
            borderRadius: '50%',
            border: '2px solid transparent',
            background: `linear-gradient(${isActive ? '#2c3140' : '#20242b'},${isActive ? '#2c3140' : '#20242b'}) padding-box, linear-gradient(135deg,#3fa9ff,#7a5cff 60%,#2ce8a0) border-box`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: isActive ? '0 0 18px rgba(80,120,255,0.55)' : '0 4px 16px rgba(60,120,255,0.22)',
          })}
        >
          <WLogo size={26} color="#dfe8ff" sw={2.2} />
        </NavLink>
      </nav>
    </div>
  );
}
