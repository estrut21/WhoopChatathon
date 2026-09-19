import * as I from '../components/icons';
import { Splash, useSplash } from '../components/Shell';
import { TEAMS } from '../data';

export default function Community() {
  const loading = useSplash(900);
  if (loading) return <Splash color="#f5344b" />;

  return (
    <div className="fade-in">
      <div className="scroll" style={{ paddingTop: 22 }}>
        <div className="pad" style={{ textAlign: 'center', fontSize: 13, fontWeight: 700, letterSpacing: '0.14em', marginBottom: 26 }}>COMMUNITY</div>

        <button
          type="button"
          className="row"
          style={{ width: 'calc(100% - 36px)', margin: '0 18px 30px', gap: 14, padding: '14px 16px', textAlign: 'left', background: 'rgba(255,255,255,0.04)', border: '1.5px solid #c4c8cc', borderRadius: 14 }}
        >
          <I.HandCoin size={28} color="#c4c8cc" />
          <div>
            <div className="label" style={{ fontSize: 13 }}>REFER A FRIEND</div>
            <div style={{ fontSize: 12.5, color: '#b5bac0', marginTop: 3 }}>Get 1 month credit for each friend you refer</div>
          </div>
        </button>

        <div className="row pad" style={{ justifyContent: 'space-between', marginBottom: 20 }}>
          <h2 className="h2" style={{ fontSize: 26 }}>Teams</h2>
          <button type="button" aria-label="Team options" style={{ background: 'none', border: 'none', display: 'flex' }}>
            <I.Ellipsis size={26} color="#fff" />
          </button>
        </div>

        <div className="pad" style={{ marginBottom: 12 }}>
          <span className="label-dim" style={{ fontSize: 11.5 }}>GETTING STARTED</span>
        </div>
        {[
          ['ENTER INVITE CODE', I.PersonSearch],
          ['CREATE TEAM', I.Plus],
        ].map(([name, Icon]) => (
          <button
            key={name}
            type="button"
            className="row"
            style={{ width: 'calc(100% - 36px)', margin: '0 18px 10px', gap: 18, padding: '17px 18px', background: 'rgba(255,255,255,0.08)', border: 'none', borderRadius: 6, textAlign: 'left' }}
          >
            <span style={{ width: 28, display: 'flex', justifyContent: 'center' }}>
              {name === 'CREATE TEAM' ? (
                <span style={{ width: 26, height: 26, borderRadius: '50%', border: '1.5px solid #9aa0a6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Icon size={16} color="#9aa0a6" />
                </span>
              ) : (
                <Icon size={26} color="#9aa0a6" />
              )}
            </span>
            <span className="label" style={{ fontSize: 13.5 }}>{name}</span>
          </button>
        ))}

        <div className="row pad" style={{ justifyContent: 'space-between', margin: '26px 0 14px' }}>
          <span className="label-dim" style={{ fontSize: 11.5 }}>RECOMMENDED TEAMS</span>
          <button type="button" className="row label" style={{ background: 'none', border: 'none', gap: 8, fontSize: 12 }}>
            VIEW ALL <I.ArrowRight size={18} />
          </button>
        </div>
        <div style={{ display: 'flex', gap: 12, overflowX: 'auto', padding: '0 18px', scrollbarWidth: 'none' }}>
          {TEAMS.map((t, i) => (
            <button
              key={t.name}
              type="button"
              style={{
                flex: '0 0 180px',
                height: 202,
                border: 'none',
                borderRadius: 6,
                background: `linear-gradient(180deg, ${t.tint[0]}, ${t.tint[1]})`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 12,
              }}
            >
              <div
                style={{
                  width: 76,
                  height: 76,
                  borderRadius: '50%',
                  background: i === 0 ? 'rgba(255,255,255,0.25)' : '#1f7be0',
                  border: '2px solid rgba(255,255,255,0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <I.TabCommunity size={38} color="#fff" />
              </div>
              <div className="label" style={{ fontSize: 15, letterSpacing: '0.12em' }}>{t.name}</div>
              <div className="label-dim" style={{ fontSize: 10, color: '#c4c8cc' }}>{t.members} MEMBERS</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
