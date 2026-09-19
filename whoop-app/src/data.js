export function recoveryColor(pct) {
  if (pct >= 67) return 'var(--rec-green)';
  if (pct >= 34) return 'var(--yellow)';
  return 'var(--red)';
}

export const DISCOVER = [
  {
    title: 'Test with Performance Health Panel',
    body: 'Explore your body’s resilience, recovery, and performance.',
    cta: 'GET YOUR TEST',
    tint: ['#7b2fbf', '#2c6ed8'],
  },
  {
    title: 'Explore the WHOOP shop',
    body: 'New bands, smart apparel, batteries and accessories',
    cta: 'GO TO SHOP',
    tint: ['#0f8f7a', '#a8672a'],
  },
  {
    title: 'Get your friend on WHOOP',
    body: 'Get a 1 month credit for each friend you refer',
    cta: 'REFER A FRIEND',
    tint: ['#c2513a', '#3a5fa8'],
  },
  {
    title: 'Give the gift of WHOOP',
    body: 'Give a friend or family member a membership',
    cta: 'CHOOSE A GIFT',
    tint: ['#c23a52', '#5a2fbf'],
  },
];

export const SHOP = [
  {
    title: 'LeatherLuxe Bands',
    items: [
      { name: 'MG LeatherLuxe Tapered Band | Black with Gold', price: '$129', tone: '#1b1b1b', accent: '#c8a24a' },
      { name: 'MG LeatherLuxe Straight Band | Black/Cream with…', price: '$129', tone: '#3a3128', accent: '#d9cdb4' },
    ],
  },
  {
    title: 'CloudKnit Bands',
    items: [
      { name: 'MG CloudKnit Band | Fawn', price: '$59', tone: '#b9a595', accent: '#8a6b5a' },
      { name: 'MG CloudKnit Band | Storm', price: '$59', tone: '#23262a', accent: '#5a6068' },
    ],
  },
  {
    title: 'SportFlex Bands',
    items: [
      { name: 'MG SportFlex Band | Gravity', price: '$59', tone: '#262626', accent: '#c9ccd0' },
      { name: 'MG Navigator Band | Ridgeline', price: '$79', tone: '#2f3236', accent: '#6b7076' },
      { name: '5.0/MG Band', price: '$49', tone: '#1c1c1c', accent: '#555' },
    ],
  },
  {
    title: 'SuperKnit Bands',
    items: [
      { name: 'WHOOP Your Way MG', price: '$49+', tone: null },
      { name: 'MG SuperKnit Band | Blush', price: '$49', tone: '#d99aa8', accent: '#8b8e94' },
    ],
  },
  {
    title: 'Navigator Bands',
    items: [
      { name: 'MG Navigator Band | Onyx', price: '$79', tone: '#222', accent: '#666' },
      { name: 'MG Navigator Band', price: '$79', tone: '#b3532a', accent: '#3f4a3a' },
    ],
  },
];

export const SHOP_CATEGORIES = [
  { name: 'Batteries', tint: ['#5a5245', '#2a2a2a'] },
  { name: 'Men’s Apparel', tint: ['#3f5f5a', '#2c3033'] },
  { name: 'Women’s Apparel', tint: ['#3a3a3f', '#5a4a3a'] },
  { name: 'Shop All', tint: ['#6a5f52', '#3a3530'] },
];

export const TEAMS = [
  { name: 'MASSACHUSETTS', members: '19388', tint: ['#2a4a7a', '#1a2a44'] },
  { name: 'MEN 20-30', members: '262806', tint: ['#4a3f3a', '#1f2a3a'] },
];
