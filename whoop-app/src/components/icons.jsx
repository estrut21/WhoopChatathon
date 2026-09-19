function make(children, { fill = 'none', sw = 1.8 } = {}) {
  return function Icon({ size = 22, color = 'currentColor', ...rest }) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill={fill === 'none' ? 'none' : color}
        stroke={color}
        strokeWidth={sw}
        strokeLinecap="round"
        strokeLinejoin="round"
        {...rest}
      >
        {children}
      </svg>
    );
  };
}

export const UserCircle = make(
  <>
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="10" r="3" />
    <path d="M6.5 18.5c1-3 3-4 5.5-4s4.5 1 5.5 4" />
  </>,
);
export const Flame = make(<path d="M12 2c1 4.5 6 6 6 11.5a6 6 0 01-12 0c0-2.5 1.2-4 2.5-5 0 2 1 3 2 3 .5-3-.5-6 1.5-9.5z" />, { fill: 'solid', sw: 0.5 });
export const FlameOutline = make(<path d="M12 3c1 4 5 5 5 10a5 5 0 01-10 0c0-2 1-3 2-4 0 2 1 3 2 3 0-3-1-6 1-9z" />);
export const ChevL = make(<path d="M15 5l-7 7 7 7" />, { sw: 2.6 });
export const ChevR = make(<path d="M9 5l7 7-7 7" />, { sw: 2.4 });
export const ChevDown = make(<path d="M5 9l7 7 7-7" />, { sw: 2.2 });
export const Check = make(<path d="M5 12.5l4.5 4.5L19 7.5" />, { sw: 2.6 });
export const Plus = make(<path d="M12 4v16M4 12h16" />, { sw: 2.6 });
export const ArrowRight = make(<path d="M4 12h16M14 6l6 6-6 6" />, { sw: 1.8 });
export const Expand = make(<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" />, { sw: 1.6 });
export const Sun = make(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1" />
  </>,
);
export const Sunrise = make(
  <>
    <path d="M3 18h18M6.5 18a5.5 5.5 0 0111 0M12 7V4M5 11l-1.5-1.5M19 11l1.5-1.5" />
  </>,
);
export const Moon = make(<path d="M20 14.5A8 8 0 019.5 4 8 8 0 1020 14.5z" />, { fill: 'solid', sw: 1 });
export const Walk = make(
  <>
    <circle cx="13" cy="4.5" r="1.8" />
    <path d="M9 21l2-7-2.5-2 1.5-5 4 2 2 3M11 14l3 2 1 5M8.5 12l-2 3" />
  </>,
);
export const Dumbbell = make(<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11" />, { sw: 2 });
export const Stopwatch = make(
  <>
    <circle cx="12" cy="13.5" r="7" />
    <path d="M12 10v4l2 1.5M9.5 3h5M12 3v3.5" />
  </>,
);
export const Alarm = make(
  <>
    <circle cx="12" cy="13" r="7" />
    <path d="M12 9v4l2.5 2M4.5 4.5L2 7M19.5 4.5L22 7" />
  </>,
);
export const Bulb = make(<path d="M9 18h6M10 21h4M12 3a6 6 0 00-3.5 10.9c.6.5 1 1.2 1 2.1h5c0-.9.4-1.6 1-2.1A6 6 0 0012 3z" />);
export const Pulse = make(<path d="M2 12h4l2-5 3.5 10 2.5-7 1.5 2H22" />);
export const HeartDown = make(
  <>
    <path d="M12 20.5s-8-4.6-8-10.5a4.6 4.6 0 018-3 4.6 4.6 0 018 3c0 5.9-8 10.5-8 10.5z" />
    <path d="M12 9v5M10 12.2l2 2 2-2" />
  </>,
);
export const HeartZones = make(
  <>
    <path d="M12 20.5s-8-4.6-8-10.5a4.6 4.6 0 018-3 4.6 4.6 0 018 3c0 5.9-8 10.5-8 10.5z" />
    <path d="M8 12h8M9 15h6" />
  </>,
);
export const Shoe = make(<path d="M4 16V6l4 2c1 2 3 3 5 3l7 3v4a1 1 0 01-1 1H5a1 1 0 01-1-1z" />);
export const Lungs = make(
  <>
    <path d="M12 4v9M12 8c-2-2-6 0-6 5v5a2 2 0 002 2c2 0 3-1 4-3M12 8c2-2 6 0 6 5v5a2 2 0 01-2 2c-2 0-3-1-4-3" />
  </>,
);
export const Drop = make(<path d="M12 3s6 6.5 6 11a6 6 0 01-12 0c0-4.5 6-11 6-11z" />);
export const Thermo = make(<path d="M10 4a2 2 0 014 0v9a4 4 0 11-4 0z" />);
export const Info = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 7.6v.4" />
  </>,
);
export const Pencil = make(<path d="M4 20l4-1 11-11-3-3L5 16z" />, { sw: 2 });
export const Gear = make(
  <>
    <circle cx="12" cy="12" r="3" />
    <circle cx="12" cy="12" r="7.5" />
    <path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M5 5l1.8 1.8M17.2 17.2L19 19M5 19l1.8-1.8M17.2 6.8L19 5" />
  </>,
  { sw: 1.7 },
);
export const Cart = make(
  <>
    <circle cx="9" cy="20" r="1.3" />
    <circle cx="18" cy="20" r="1.3" />
    <path d="M2 3h3l2.5 12h11L21 7H6" />
  </>,
);
export const Ellipsis = make(
  <>
    <circle cx="5" cy="12" r="1.3" />
    <circle cx="12" cy="12" r="1.3" />
    <circle cx="19" cy="12" r="1.3" />
  </>,
);
export const Gift = make(
  <>
    <rect x="3" y="8" width="18" height="4" rx="1" />
    <path d="M12 8v13M5 12v9h14v-9M12 8c-2 0-4-1-4-3a2 2 0 014 0M12 8c2 0 4-1 4-3a2 2 0 00-4 0" />
  </>,
);
export const HandCoin = make(
  <>
    <circle cx="15" cy="7" r="3.5" />
    <path d="M2 16l4-1 4 1.5h4a1.5 1.5 0 010 3H9M10 16.5l5.5-1.5L20 13" />
  </>,
);
export const PersonSearch = make(
  <>
    <circle cx="9" cy="8" r="3" />
    <path d="M3 19c0-3 2.5-5 6-5M15 18a3 3 0 106 0 3 3 0 00-6 0M20 20l2 2" />
  </>,
);
export const Band = make(
  <>
    <rect x="8" y="2" width="8" height="20" rx="3" />
    <rect x="10" y="9" width="4" height="6" rx="1" />
  </>,
);

export const TabHome = make(
  <>
    <path d="M3 11.5L12 3l9 8.5V21H3z" />
    <path d="M7 16l3-3 2 2 4-4" />
  </>,
);
export const TabHealth = make(
  <>
    <path d="M12 20.5s-8-4.6-8-10.5a4.6 4.6 0 018-3 4.6 4.6 0 018 3c0 5.9-8 10.5-8 10.5z" />
    <path d="M7 12h2.5l1.5-3 2 6 1.5-3H17" />
  </>,
);
export const TabCommunity = make(
  <>
    <circle cx="12" cy="6.5" r="2.4" />
    <circle cx="5.5" cy="9.5" r="2" />
    <circle cx="18.5" cy="9.5" r="2" />
    <path d="M7.5 20v-3.5a4.5 4.5 0 019 0V20M1.5 18v-2.5a3 3 0 014-2.8M22.5 18v-2.5a3 3 0 00-4-2.8" />
  </>,
);
export const TabMore = make(<path d="M3 6h18M3 12h18M3 18h18" />, { sw: 2 });

export function WLogo({ size = 26, color = 'currentColor', sw = 2.4 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 5l4 14M8 19l3.5-9M12.5 10L16 19M17 19l4-14" />
    </svg>
  );
}
