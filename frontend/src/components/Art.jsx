// Illustrations drawn in SVG: vehicles for ride rows, and map-style artwork for cards and
// the welcome screen. They are decoration, never real map data.

function AutoArt() {
  return (
    <>
      <ellipse cx="48" cy="55" rx="38" ry="3.5" fill="#000" opacity="0.12" />
      {/* canopy */}
      <path d="M16 27V17q0-7 7-7h31q6 0 9 5l7 12z" fill="#ffc83d" />
      {/* open passenger side and windshield */}
      <path d="M22 16.5h23V27H22z" fill="#2c2c2e" />
      <path d="M50 14.5h5q2 0 3.4 2.4L64 27H50z" fill="#bfe3f8" />
      {/* body */}
      <path d="M12 45V31q0-4 4-4h51l11 9q4 3 4 7v2z" fill="#1c1c1e" />
      <path d="M12 35h57v3H12z" fill="#c6f135" />
      <circle cx="80" cy="40.5" r="2.2" fill="#ffe08a" />
      {/* wheels */}
      <circle cx="26" cy="47" r="8" fill="#0b0b0c" />
      <circle cx="26" cy="47" r="3" fill="#d4d4d8" />
      <circle cx="72" cy="47" r="8" fill="#0b0b0c" />
      <circle cx="72" cy="47" r="3" fill="#d4d4d8" />
    </>
  );
}

function CabArt() {
  return (
    <>
      <ellipse cx="48" cy="55" rx="40" ry="3.5" fill="#000" opacity="0.12" />
      {/* body */}
      <path
        d="M8 45v-9q0-5 5-6l11-2 12-12q2-2 6-2h18q4 0 7 3l10 11q11 1 12 8v9z"
        fill="#fafafa"
        stroke="#d4d4d8"
        strokeWidth="1.5"
      />
      {/* windows */}
      <path d="M30 28l9-9.5h11V28z" fill="#bfe3f8" />
      <path d="M53 18.5h7q2 0 3.5 1.5l7 8H53z" fill="#bfe3f8" />
      <path d="M51.5 18.5V44" stroke="#d4d4d8" strokeWidth="1.2" />
      <path d="M8.8 36H89v3.2H8.8z" fill="#c6f135" />
      <rect x="84.5" y="31.5" width="4" height="3" rx="1" fill="#ffe08a" />
      <rect x="8.6" y="31.5" width="3" height="3" rx="1" fill="#f87171" />
      {/* wheels */}
      <circle cx="26" cy="47" r="8" fill="#0b0b0c" />
      <circle cx="26" cy="47" r="3" fill="#d4d4d8" />
      <circle cx="72" cy="47" r="8" fill="#0b0b0c" />
      <circle cx="72" cy="47" r="3" fill="#d4d4d8" />
    </>
  );
}

export function VehicleArt({ vehicle = "auto", width = 72 }) {
  return (
    <svg
      className="vehicle-art"
      width={width}
      height={(width * 60) / 96}
      viewBox="0 0 96 60"
      aria-hidden="true"
      focusable="false"
    >
      {vehicle === "cab" ? <CabArt /> : <AutoArt />}
    </svg>
  );
}

// Three route shapes so neighbouring cards don't look identical.
// The status pill sits top-left, and wide cards crop the top and bottom of the drawing, so
// every route starts low on the left and stays in the middle band.
const ROUTES = [
  { d: "M40 58C92 58 100 34 152 36S232 58 284 38", from: [40, 58], to: [284, 38] },
  { d: "M40 56C98 56 112 62 162 50S238 30 284 44", from: [40, 56], to: [284, 44] },
  { d: "M40 60C80 38 130 62 172 46S246 34 284 36", from: [40, 60], to: [284, 36] },
];

// A strip of stylised streets with a route across it: the header of a ride card.
export function RouteArt({ seed = 0 }) {
  const { d, from: [x1, y1], to: [x2, y2] } = ROUTES[Math.abs(seed) % ROUTES.length];
  return (
    <svg className="route-art" viewBox="0 0 320 88" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <rect width="320" height="88" className="art-bg" />
      <g className="art-street">
        <path d="M-10 18H330M-10 52H330M-10 78H330" />
        <path d="M40-10V98M112-10V98M196-10V98M262-10V98" />
        <path d="M-10 96 120-10M180 98 330 8" />
      </g>
      <path d="M210-10q18 40-6 108" className="art-water" />
      <path d={d} className="art-route-case" />
      <path d={d} className="art-route" />
      <circle cx={x1} cy={y1} r="7" className="art-pin" />
      <circle cx={x1} cy={y1} r="2.6" className="art-pin-dot" />
      <rect x={x2 - 6.5} y={y2 - 6.5} width="13" height="13" rx="3" className="art-pin" />
      <rect x={x2 - 2.2} y={y2 - 2.2} width="4.4" height="4.4" rx="1" className="art-pin-dot" />
    </svg>
  );
}

// The welcome screen's backdrop: a night map with the route in lime.
export function HeroArt() {
  return (
    <svg className="hero-art" viewBox="0 0 600 420" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false">
      <g stroke="#232326" strokeWidth="10" fill="none" strokeLinecap="round">
        <path d="M-20 70H620M-20 190H620M-20 320H620" />
        <path d="M80-20V440M230-20V440M390-20V440M520-20V440" />
        <path d="M-20 430 250-20M330 440 620 120" />
      </g>
      <path d="M440-20q40 180-30 460" stroke="#12202b" strokeWidth="46" fill="none" />
      {/* the railway line, with sleepers */}
      <path d="M-20 262C140 250 300 300 620 250" stroke="#3a3a3d" strokeWidth="5" fill="none" strokeDasharray="2 9" />
      <path d="M-20 262C140 250 300 300 620 250" stroke="#2c2c2e" strokeWidth="2" fill="none" />
      {/* The route stays in the upper middle: the headline sits over the lower half, and a
          tall laptop hero crops the left and right edges. */}
      <path
        d="M190 180C252 180 250 120 312 114S382 70 412 60"
        stroke="#c6f135"
        strokeWidth="7"
        fill="none"
        strokeLinecap="round"
      />
      <circle cx="190" cy="180" r="15" fill="#c6f135" />
      <circle cx="190" cy="180" r="5.5" fill="#0b0b0c" />
      <rect x="398" y="46" width="28" height="28" rx="7" fill="#fafafa" />
      <rect x="407" y="55" width="10" height="10" rx="2.5" fill="#0b0b0c" />
      {/* three co-travellers gathering at the pickup */}
      <circle cx="158" cy="192" r="6.5" fill="#fafafa" opacity="0.9" />
      <circle cx="222" cy="196" r="6.5" fill="#fafafa" opacity="0.7" />
      <circle cx="152" cy="158" r="6.5" fill="#fafafa" opacity="0.5" />
    </svg>
  );
}
