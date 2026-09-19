import { useId, useState } from 'react';
import { ChevDown } from './icons';
import { evidenceFor, ATTRIBUTION, TOPIC_LABEL } from '../evidence';

const linkStyle = { fontSize: 11.5, fontWeight: 700, letterSpacing: '0.06em', color: '#5aa9f0' };

function Claim({ tone, label, glyph, text }) {
  return (
    <div style={{ marginTop: 10 }}>
      <div className="row" style={{ gap: 6, fontSize: 10, fontWeight: 700, letterSpacing: '0.1em', color: tone }}>
        <span aria-hidden="true" style={{ fontSize: 12, lineHeight: 1 }}>{glyph}</span>
        {label}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.45, color: '#d5d9dd', marginTop: 3 }}>{text}</div>
    </div>
  );
}

function Paper({ p }) {
  return (
    <article style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 14, padding: 13, marginTop: 8 }}>
      <span style={{ display: 'inline-block', fontSize: 9.5, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#c4c8cc', background: 'rgba(255,255,255,0.09)', borderRadius: 5, padding: '3px 7px' }}>
        {p.evidence_tier}
      </span>
      <div style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.35, marginTop: 8 }}>{p.title}</div>
      <div style={{ fontSize: 11, color: '#8a9096', marginTop: 4 }}>{p.short_citation}</div>
      <Claim tone="var(--mint)" glyph={'✓'} label="WHAT IT SUPPORTS" text={p.supports} />
      <Claim tone="var(--orange)" glyph={'✕'} label="WHAT IT DOES NOT SUPPORT" text={p.does_not_support} />
      <div className="row" style={{ gap: 16, marginTop: 12 }}>
        <a href={p.url} target="_blank" rel="noopener noreferrer" style={linkStyle}>PUBMED &#8599;</a>
        {p.doi_url && (
          <a href={p.doi_url} target="_blank" rel="noopener noreferrer" style={linkStyle}>DOI &#8599;</a>
        )}
      </div>
    </article>
  );
}

export default function Evidence({ topic, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = useId();
  const papers = evidenceFor(topic);
  if (!papers.length) return null;
  const count = `${papers.length} ${papers.length === 1 ? 'paper' : 'papers'}`;

  return (
    <div style={{ marginTop: 8 }}>
      <button
        type="button"
        aria-expanded={open}
        aria-label={open ? 'Hide the research' : `Explain: show the research (${count})`}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
        className="row"
        style={{ gap: 7, background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 16, padding: '7px 12px', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em' }}
      >
        {open ? 'HIDE' : 'EXPLAIN'}
        <ChevDown size={13} style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }} />
      </button>

      {open && (
        <section id={panelId} aria-label={`Literature on ${TOPIC_LABEL[topic]}`} style={{ marginTop: 10 }}>
          <div className="label-dim" style={{ fontSize: 10.5 }}>LITERATURE &middot; PUBMED &middot; {TOPIC_LABEL[topic].toUpperCase()}</div>
          <div style={{ fontSize: 11.5, color: '#9aa0a6', lineHeight: 1.4, marginTop: 4 }}>
            Background from other people&rsquo;s studies. It is not evidence about your own numbers.
          </div>
          {papers.map((p) => (
            <Paper key={p.pmid} p={p} />
          ))}
          <div style={{ fontSize: 11.5, lineHeight: 1.4, color: '#d5d9dd', background: 'rgba(245,165,36,0.12)', borderRadius: 10, padding: '9px 11px', marginTop: 8 }}>
            <strong style={{ letterSpacing: '0.06em' }}>POPULATION CAVEAT.</strong> This is mostly athlete and exercise research. None of it studies desk-based workers like you.
          </div>
          <div style={{ fontSize: 10.5, color: '#6b7176', lineHeight: 1.4, marginTop: 8 }}>{ATTRIBUTION}</div>
        </section>
      )}
    </div>
  );
}
