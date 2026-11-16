import Icon from "./Icon.jsx";

// Small building blocks shared by every page, so the look stays consistent.

const AVATAR_HUES = [78, 168, 200, 260, 330, 20, 45];

// Initials on a colour picked from the name: the same person always gets the same colour.
export function Avatar({ name = "?", size = "md" }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0].toUpperCase())
    .join("");
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  const hue = AVATAR_HUES[hash % AVATAR_HUES.length];
  return (
    <span className={`avatar avatar-${size}`} style={{ "--hue": hue }} aria-hidden="true">
      {initials || "?"}
    </span>
  );
}

// Pickup and drop-off joined by a line: the shape people know from ride apps.
export function RouteLine({ from, to }) {
  return (
    <div className="route-line">
      <div className="route-stop">
        <span className="stop-dot from" />
        <span className="stop-label">{from}</span>
      </div>
      <div className="route-stop">
        <span className="stop-dot to" />
        <span className="stop-label">{to}</span>
      </div>
    </div>
  );
}

const STATUS_TEXT = {
  open: "Open",
  full: "Full",
  cancelled: "Cancelled",
  completed: "Completed",
  pending: "Requested",
  accepted: "Accepted",
  declined: "Declined",
};

export function StatusPill({ status }) {
  return (
    <span className={`pill status-${status}`}>
      <span className="pill-dot" />
      {STATUS_TEXT[status] ?? status}
    </span>
  );
}

// Where a join request stands: Requested → Accepted → Ride done.
export function Timeline({ step }) {
  const steps = ["Requested", "Accepted", "Ride done"];
  return (
    <ol className="timeline" aria-label="Progress">
      {steps.map((label, i) => (
        <li
          key={label}
          className={`timeline-step ${i < step ? "done" : ""} ${i === step ? "current" : ""}`}
          aria-current={i === step ? "step" : undefined}
        >
          {label}
        </li>
      ))}
    </ol>
  );
}

export function EmptyState({ icon, art, title, text, children }) {
  return (
    <div className="empty-state">
      {art ?? (
        <span className="empty-icon">
          <Icon name={icon} size={26} />
        </span>
      )}
      <strong>{title}</strong>
      {text && <p className="muted">{text}</p>}
      {children}
    </div>
  );
}

// Grey placeholder cards while data loads, so the page doesn't jump around.
export function SkeletonCards({ count = 2 }) {
  return Array.from({ length: count }, (_, i) => (
    <div key={i} className="skeleton-card" aria-hidden="true">
      <span className="skeleton w-40" />
      <span className="skeleton w-80" />
      <span className="skeleton w-60" />
    </div>
  ));
}

// Notices inside a card: success (lime), error (red) or info (neutral).
export function Notice({ kind = "info", children }) {
  const icon = { success: "check", error: "info", info: "info" }[kind];
  return (
    <p className={`notice notice-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon name={icon} size={18} />
      <span>{children}</span>
    </p>
  );
}
