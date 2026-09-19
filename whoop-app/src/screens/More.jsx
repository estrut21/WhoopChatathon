import * as I from '../components/icons';
import { Splash, useSplash } from '../components/Shell';
import { SHOP, SHOP_CATEGORIES } from '../data';

function BandArt({ tone, accent }) {
  return (
    <svg width="100%" height="100%" viewBox="0 0 160 118" preserveAspectRatio="xMidYMid meet">
      <path d="M40 78c0-30 22-50 52-50s34 18 34 40" fill="none" stroke={tone} strokeWidth="16" strokeLinecap="round" />
      <rect x="66" y="34" width="34" height="46" rx="8" fill={accent} transform="rotate(-8 83 57)" />
      <rect x="72" y="42" width="22" height="30" rx="4" fill={tone} opacity="0.85" transform="rotate(-8 83 57)" />
    </svg>
  );
}

function Product({ p }) {
  return (
    <button type="button" style={{ flex: '0 0 176px', textAlign: 'left', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: 10, padding: 5, paddingBottom: 12 }}>
      <div style={{ height: 118, borderRadius: 7, background: '#e3e6e8', overflow: 'hidden' }}>{p.tone && <BandArt tone={p.tone} accent={p.accent} />}</div>
      <div style={{ fontSize: 12.5, fontWeight: 500, lineHeight: 1.4, margin: '10px 6px 8px', minHeight: 35 }}>{p.name}</div>
      <div className="num" style={{ margin: '0 6px', fontSize: 14, fontWeight: 700 }}>{p.price}</div>
    </button>
  );
}

export default function More() {
  const loading = useSplash(1000);
  if (loading) return <Splash text="OPENING MORE" bg="#000" />;

  return (
    <div className="fade-in">
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 62, zIndex: 5, display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 18px 0', background: 'linear-gradient(180deg, rgba(20,22,24,0.95) 70%, transparent)' }}>
        <button type="button" aria-label="Settings" style={{ background: 'none', border: 'none', display: 'flex' }}>
          <I.Gear size={28} />
        </button>
        <span className="label" style={{ fontSize: 13, letterSpacing: '0.14em' }}>MORE</span>
        <button type="button" aria-label="Cart" style={{ background: 'none', border: 'none', display: 'flex' }}>
          <I.Cart size={28} />
        </button>
      </div>

      <div className="scroll" style={{ paddingTop: 70 }}>
        {SHOP.map((section) => (
          <section key={section.title} style={{ marginBottom: 26 }}>
            <h2 className="h2 pad" style={{ fontSize: 22, marginBottom: 12 }}>{section.title}</h2>
            <div style={{ display: 'flex', gap: 12, overflowX: 'auto', padding: '0 18px', scrollbarWidth: 'none' }}>
              {section.items.map((p) => (
                <Product key={p.name} p={p} />
              ))}
            </div>
          </section>
        ))}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '0 18px' }}>
          {SHOP_CATEGORIES.map((c) => (
            <button
              key={c.name}
              type="button"
              style={{
                height: 134,
                border: 'none',
                borderRadius: 14,
                background: `linear-gradient(120deg, ${c.tint[0]}, ${c.tint[1]})`,
                display: 'flex',
                alignItems: 'flex-end',
                justifyContent: 'space-between',
                padding: '0 18px 18px',
                fontSize: 16,
                fontWeight: 600,
              }}
            >
              {c.name}
              <I.ChevR size={18} />
            </button>
          ))}
        </div>

        <div className="row pad" style={{ justifyContent: 'space-between', margin: '26px 0 10px', fontSize: 16, fontWeight: 500 }}>
          <span>Shopping in United States</span>
          <span className="row" style={{ gap: 14 }}>
            <svg width="22" height="15" viewBox="0 0 22 15" aria-label="United States flag">
              <rect width="22" height="15" fill="#f5f5f5" />
              {[0, 2, 4, 6, 8, 10, 12, 14].map((y) => (
                <rect key={y} y={y} width="22" height="1.1" fill="#d22f3f" />
              ))}
              <rect width="10" height="8" fill="#2b4a9a" />
            </svg>
            <I.ChevDown size={20} />
          </span>
        </div>
      </div>
    </div>
  );
}
