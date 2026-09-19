import data from './data/evidence.json';

export const ATTRIBUTION = data.attribution;

// Which curated papers speak to which topic. Only papers with a hand-written
// supports / does_not_support note exist in evidence.json, so nothing uncurated can be cited.
// Topics that include a paper reporting a weak or null relationship keep it in: that is the point.
const TOPICS = {
  hrv: ['37754967', '35344471', '30300066'],
  rhr: ['37754967', '31642195'],
  sleep: ['35409591'],
  stress: ['35409591'],
  strain: ['33202732', '35344471', '14965189'],
  recovery: ['37754967', '35344471'],
  cognitive: ['35409591', '37754967', '35344471'],
};

export const TOPIC_LABEL = {
  hrv: 'HRV',
  rhr: 'resting heart rate',
  sleep: 'sleep',
  stress: 'stress',
  strain: 'training load',
  recovery: 'recovery',
  cognitive: 'cognitive readiness',
};

export const evidenceFor = (topic) => (TOPICS[topic] || []).map((id) => data.papers[id]).filter(Boolean);

const TOPIC_TESTS = [
  ['hrv', /\bhrv\b|heart rate variab/],
  ['rhr', /\brhr\b|resting heart/],
  ['stress', /stress|anxi|pressure/],
  ['sleep', /\bsleep|\brem\b|\bdeep\b/],
  ['strain', /strain|train|workout|exercise|\bload\b/],
  ['recovery', /recover/],
  ['cognitive', /cognitive|focus|readiness|mental|fatigue|brain/],
];

export const topicOf = (q) => (TOPIC_TESTS.find(([, re]) => re.test(q)) || [null])[0];
