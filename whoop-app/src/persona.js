import csv from './data/persona.csv?raw';

const coerce = (v) => (v !== '' && !Number.isNaN(Number(v)) ? Number(v) : v);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let quoted = false;
  const endRow = () => {
    row.push(cell);
    cell = '';
    if (row.some((v) => v !== '')) rows.push(row);
    row = [];
  };
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') {
        cell += '"';
        i++;
      } else if (c === '"') quoted = false;
      else cell += c;
    } else if (c === '"') quoted = true;
    else if (c === ',') {
      row.push(cell);
      cell = '';
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      endRow();
    } else cell += c;
  }
  if (cell !== '' || row.length) endRow();
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h.trim(), coerce(r[i] ?? '')])));
}

const fmtDate = (dt, opts) => dt.toLocaleDateString('en-US', opts);
const atNoon = (iso) => new Date(`${iso}T12:00:00`);

export const hm = (hours) => {
  const m = Math.round(hours * 60);
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;
};
const minsToHm = (m) => `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`;

// sleep_performance in the CSV (100) contradicts the row's own hours, efficiency and REM/debt z-scores.
// Use the optional sleep_score column when present; otherwise blend efficiency with hours vs an assumed 8h need.
const SLEEP_NEED_HOURS = 8;
export const sleepScore = (r) =>
  typeof r.sleep_score === 'number'
    ? r.sleep_score
    : Math.round((0.5 * r.sleep_efficiency + 0.5 * Math.min(100, (r.sleep_hours / SLEEP_NEED_HOURS) * 100)) * 10) / 10;

function toDay(r) {
  const dt = atNoon(r.date);
  return {
    raw: r,
    date: r.date,
    short: fmtDate(dt, { weekday: 'short' }),
    dom: dt.getDate(),
    long: fmtDate(dt, { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase(),
    sleep: sleepScore(r),
    cognitive: r.readiness_score,
    recovery: r.recovery_score,
    strain: r.day_strain,
  };
}

export const DAYS = parseCsv(csv)
  .filter((r) => r.date)
  .sort((a, b) => (a.date < b.date ? -1 : 1))
  .map(toDay);

export const PERSONA = (() => {
  const r = DAYS[DAYS.length - 1].raw;
  return {
    id: r.user_id,
    age: r.age,
    gender: r.gender,
    weightKg: r.weight_kg,
    heightCm: r.height_cm,
    fitness: r.fitness_level,
    sport: r.primary_sport,
  };
})();

const FACTOR_DEFS = [
  ['hrv_deviation', 'HRV deviation'],
  ['sleep_debt', 'Sleep debt'],
  ['rem_adequacy', 'REM sleep'],
  ['rhr_deviation', 'Resting heart rate'],
  ['deep_adequacy', 'Deep sleep'],
  ['sleep_continuity', 'Sleep continuity'],
];

export function cognitiveFor(day) {
  const r = day.raw;
  return {
    score: r.readiness_score,
    band: String(r.readiness_band),
    confidence: String(r.readiness_confidence),
    message: r.band_message,
    topDriver: (FACTOR_DEFS.find(([k]) => k === r.top_driver) || [null, r.top_driver])[1],
    factors: FACTOR_DEFS.map(([k, label]) => ({ key: k, label, z: r[`z_${k}`], pts: r[`pts_${k}`] })),
  };
}

export function sleepFor(day) {
  const r = day.raw;
  return {
    total: hm(r.sleep_hours),
    light: hm(r.light_sleep_hours),
    rem: hm(r.rem_sleep_hours),
    deep: hm(r.deep_sleep_hours),
    efficiency: r.sleep_efficiency,
    performance: sleepScore(r),
    wakeUps: r.wake_ups,
    latency: r.time_to_fall_asleep_min,
  };
}

export function activitiesFor(day) {
  const r = day.raw;
  const list = [{ kind: 'sleep', name: 'SLEEP', value: hm(r.sleep_hours) }];
  if (r.workout_completed) {
    const type = String(r.activity_type);
    list.push({
      kind: /weight|strength|lift/i.test(type) ? 'lift' : /walk/i.test(type) ? 'walk' : 'workout',
      name: type.toUpperCase(),
      value: Number(r.activity_strain).toFixed(1),
      detail: `${r.activity_duration_min} min`,
    });
  }
  return list;
}

export function dashboardFor(day) {
  const r = day.raw;
  const z13 = r.hr_zone_1_min + r.hr_zone_2_min + r.hr_zone_3_min;
  const z45 = r.hr_zone_4_min + r.hr_zone_5_min;
  return [
    { key: 'hrv', label: 'HEART RATE VARIABILITY', value: String(Math.round(r.hrv)), prev: String(r.hrv_baseline), trend: r.hrv < r.hrv_baseline ? 'down-orange' : 'up-green' },
    { key: 'rhr', label: 'RESTING HEART RATE', value: String(Math.round(r.resting_heart_rate)), prev: String(r.rhr_baseline), trend: r.resting_heart_rate > r.rhr_baseline ? 'up-orange' : 'down-green' },
    { key: 'resp', label: 'RESPIRATORY RATE', value: String(r.respiratory_rate) },
    { key: 'temp', label: 'SKIN TEMP DEVIATION', value: `${r.skin_temp_deviation > 0 ? '+' : ''}${r.skin_temp_deviation}°` },
    { key: 'z13', label: 'HR ZONES 1-3 (TODAY)', value: minsToHm(z13) },
    { key: 'z45', label: 'HR ZONES 4-5 (TODAY)', value: minsToHm(z45) },
    { key: 'cal', label: 'CALORIES', value: Math.round(r.calories_burned).toLocaleString('en-US') },
  ];
}

// The 7 calendar days ending on `endDate`, each holding its data row or null.
export function weekSlots(endDate) {
  const end = atNoon(endDate);
  return Array.from({ length: 7 }, (_, i) => {
    const dt = new Date(end);
    dt.setDate(end.getDate() - (6 - i));
    const iso = `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
    return { date: iso, short: fmtDate(dt, { weekday: 'short' }), dom: dt.getDate(), day: DAYS.find((d) => d.date === iso) || null };
  });
}
