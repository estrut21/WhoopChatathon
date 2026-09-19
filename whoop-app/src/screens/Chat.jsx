import { forwardRef, useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { WLogo, ArrowRight } from '../components/icons';
import Evidence from '../components/Evidence';
import { topicOf, TOPIC_LABEL } from '../evidence';
import { DAYS, PERSONA, cognitiveFor, sleepFor, dashboardFor, stressFor } from '../persona';

const day = DAYS[DAYS.length - 1];
const r = day.raw;
const cog = cognitiveFor(day);
const sl = sleepFor(day);
const st = stressFor(day);
const metric = (key) => dashboardFor(day).find((m) => m.key === key);

const SUGGESTIONS = ['How stressed am I?', 'How is my cognitive readiness?', 'What does research say about HRV?', 'How did I sleep?'];

const RULES = [
  {
    test: /research|evidence|stud(y|ies)|paper|pubmed|literature|science|citation|cite/,
    topic: (q) => topicOf(q),
    openEvidence: true,
    answer: (q) => {
      const topic = topicOf(q);
      return topic
        ? `Here is what the curated PubMed papers say about ${TOPIC_LABEL[topic]}. Each one lists what it supports and what it does not.`
        : 'Ask about a specific topic, such as HRV, resting heart rate, sleep, stress, training load or cognitive readiness, and I will show the papers behind it.';
    },
  },
  {
    test: /stress|anxious|anxiety|pressure|overwhelm|calm|tense/,
    topic: 'stress',
    answer: () =>
      `Your stress reads ${st.current} (${st.band}) as of ${st.lastUpdated} and peaked at ${st.peak.value} around ${st.peak.time}. ${st.highMin === 0 ? 'It stayed below the high zone (2.0 and above) all day. ' : `You spent ${st.highLabel} hrs in the high zone. `}Resting heart rate is ${r.resting_heart_rate} bpm against a ${r.rhr_baseline} baseline, and HRV is ${Math.round((1 - r.hrv / r.hrv_baseline) * 100)}% below its baseline.`,
  },
  {
    test: /cognitive|focus|mental|brain|sharp|readiness/,
    topic: 'cognitive',
    answer: () => {
      const worst = [...cog.factors].sort((a, b) => a.pts - b.pts)[0];
      return `Your cognitive readiness is ${Math.round(cog.score)}% (${cog.band}, ${cog.confidence} confidence). ${cog.message} The biggest drag is ${worst.label.toLowerCase()} at ${worst.pts} pts; your top driver is ${cog.topDriver}.`;
    },
  },
  {
    test: /recover|ready/,
    topic: 'recovery',
    answer: () => {
      const zone = day.recovery >= 67 ? 'green' : day.recovery >= 34 ? 'yellow' : 'red';
      return `Your recovery is ${Math.round(day.recovery)}% (${zone} zone). HRV is ${metric('hrv').value} ms against a baseline of ${metric('hrv').prev}, and resting heart rate is ${metric('rhr').value} bpm against ${metric('rhr').prev}.`;
    },
  },
  {
    test: /\bsleep|slept|\brest\b|\brem\b|\bdeep\b/,
    topic: 'sleep',
    answer: () =>
      `You slept ${sl.total} for a ${Math.round(sl.performance)}% sleep performance and ${sl.efficiency}% efficiency: ${sl.light} light, ${sl.rem} REM and ${sl.deep} deep. You woke up ${sl.wakeUps} time${sl.wakeUps === 1 ? '' : 's'} and took ${sl.latency} minutes to fall asleep.`,
  },
  {
    test: /strain|workout|exercise|swim|activity|calor/,
    topic: 'strain',
    answer: () =>
      `Your day strain is ${day.strain.toFixed(1)} out of 21 with ${Math.round(r.calories_burned).toLocaleString('en-US')} calories burned. ${r.workout_completed ? `You logged ${r.activity_type} for ${r.activity_duration_min} minutes.` : 'Today was a rest day, with no workout logged.'}`,
  },
  {
    test: /hrv|heart rate variab/,
    topic: 'hrv',
    answer: () => `Your HRV is ${r.hrv} ms, below your baseline of ${r.hrv_baseline} ms. It's the biggest factor pulling your cognitive readiness down.`,
  },
  {
    test: /rhr|resting/,
    topic: 'rhr',
    answer: () => `Your resting heart rate is ${r.resting_heart_rate} bpm, against a baseline of ${r.rhr_baseline}.`,
  },
  {
    test: /resp|breath/,
    answer: () => `Your respiratory rate is ${r.respiratory_rate} breaths per minute, and your skin temperature is ${r.skin_temp_deviation}\u00b0 from baseline.`,
  },
  {
    test: /who am i|profile|about me/,
    answer: () => `You're a ${PERSONA.age}-year-old ${PERSONA.gender.toLowerCase()}, ${PERSONA.heightCm} cm and ${PERSONA.weightKg} kg, at a ${PERSONA.fitness.toLowerCase()} fitness level with ${PERSONA.sport.toLowerCase()} as your main sport.`,
  },
  {
    test: /^(hi|hey|hello|yo)\b/,
    answer: () => 'Hey! Ask me about your cognitive readiness, recovery, sleep, strain or heart metrics.',
  },
];

function respond(text) {
  const q = text.toLowerCase().trim();
  const rule = RULES.find((rl) => rl.test.test(q));
  if (!rule) {
    return { text: 'I can answer questions about your cognitive readiness, recovery, sleep, strain, stress, HRV and resting heart rate. Try one of those.' };
  }
  return { text: rule.answer(q), topic: typeof rule.topic === 'function' ? rule.topic(q) : rule.topic, openEvidence: rule.openEvidence };
}

const Bubble = forwardRef(function Bubble({ m }, ref) {
  const mine = m.role === 'user';
  return (
    <div ref={ref} style={{ display: 'flex', justifyContent: mine ? 'flex-end' : 'flex-start', gap: 8, marginBottom: 12, scrollMarginTop: 66 }}>
      {!mine && (
        <div style={{ width: 28, height: 28, flexShrink: 0, borderRadius: '50%', background: '#20242b', border: '1.5px solid #4d63d8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <WLogo size={15} color="#dfe8ff" sw={2.4} />
        </div>
      )}
      <div style={{ maxWidth: mine ? '78%' : 'calc(100% - 36px)', minWidth: 0 }}>
        <div
          style={{
            display: 'inline-block',
            padding: '11px 14px',
            fontSize: 14,
            lineHeight: 1.45,
            borderRadius: mine ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
            background: mine ? 'linear-gradient(135deg,#4d63d8,#2f8df0)' : 'rgba(255,255,255,0.09)',
            color: '#fff',
            maxWidth: '100%',
          }}
        >
          {m.text}
        </div>
        {m.topic && <Evidence topic={m.topic} defaultOpen={m.openEvidence} />}
      </div>
    </div>
  );
});

export default function Chat() {
  const {
    chat: [messages, setMessages],
  } = useOutletContext();
  const [draft, setDraft] = useState('');
  const [typing, setTyping] = useState(false);
  const endRef = useRef(null);
  const lastRef = useRef(null);
  const timer = useRef(null);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (!typing && last?.openEvidence) lastRef.current?.scrollIntoView({ block: 'start' });
    else endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, typing]);

  useEffect(() => () => clearTimeout(timer.current), []);

  function send(text) {
    const t = text.trim();
    if (!t || typing) return;
    setMessages((m) => [...m, { id: Date.now(), role: 'user', text: t }]);
    setDraft('');
    setTyping(true);
    timer.current = setTimeout(() => {
      setMessages((m) => [...m, { id: Date.now() + 1, role: 'assistant', ...respond(t) }]);
      setTyping(false);
    }, 700);
  }

  const onlyGreeting = messages.length === 1;

  return (
    <div className="fade-in">
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 62,
          zIndex: 5,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 3,
          background: 'linear-gradient(180deg, #23272a 85%, transparent)',
        }}
      >
        <span className="label" style={{ fontSize: 13, letterSpacing: '0.14em' }}>WHOOP COACH</span>
        <span style={{ fontSize: 10.5, color: 'var(--dim)' }}>Your data + curated PubMed papers</span>
      </div>

      <div className="scroll" style={{ padding: '72px 16px 176px' }}>
        {messages.map((m, i) => (
          <Bubble key={m.id} m={m} ref={i === messages.length - 1 ? lastRef : null} />
        ))}
        {typing && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }} aria-label="WHOOP Coach is typing">
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#20242b', border: '1.5px solid #4d63d8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <WLogo size={15} color="#dfe8ff" sw={2.4} />
            </div>
            <div style={{ padding: '13px 16px', borderRadius: '18px 18px 18px 4px', background: 'rgba(255,255,255,0.09)', display: 'flex', gap: 5 }}>
              {[0, 1, 2].map((i) => (
                <span key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: '#9aa0a6', animation: `pulse-w 1s ${i * 0.15}s infinite` }} />
              ))}
            </div>
          </div>
        )}
        {onlyGreeting && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8, paddingLeft: 36 }}>
            {SUGGESTIONS.map((s) => (
              <button key={s} type="button" onClick={() => send(s)} style={{ border: '1px solid rgba(255,255,255,0.18)', background: 'rgba(255,255,255,0.05)', borderRadius: 18, padding: '8px 13px', fontSize: 12.5 }}>
                {s}
              </button>
            ))}
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(draft);
        }}
        style={{
          position: 'absolute',
          left: 12,
          right: 12,
          bottom: 96,
          zIndex: 9,
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          background: 'rgba(38,42,46,0.92)',
          backdropFilter: 'blur(18px)',
          WebkitBackdropFilter: 'blur(18px)',
          border: '1px solid rgba(255,255,255,0.09)',
          borderRadius: 28,
          padding: '6px 6px 6px 16px',
        }}
      >
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={'Ask about your recovery, sleep, strain…'}
          aria-label="Message WHOOP Coach"
          style={{ flex: 1, minWidth: 0, background: 'none', border: 'none', outline: 'none', color: '#fff', fontSize: 14, fontFamily: 'inherit' }}
        />
        <button
          type="submit"
          aria-label="Send"
          disabled={!draft.trim() || typing}
          style={{ width: 40, height: 40, borderRadius: '50%', border: 'none', background: 'linear-gradient(135deg,#4d63d8,#2f8df0)', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: !draft.trim() || typing ? 0.4 : 1 }}
        >
          <ArrowRight size={18} color="#fff" />
        </button>
      </form>
    </div>
  );
}
