import { useState } from "react";
import { api } from "../api.js";
import Icon from "./Icon.jsx";
import { Avatar, Notice } from "./ui.jsx";

// "✓ Verified · ★ 4.8 (12)": the signals that help you decide whether to share a ride.
export function TrustBadges({ person }) {
  return (
    <span className="trust">
      {person.phone_verified && (
        <span className="trust-badge verified">
          <Icon name="shield" size={14} />
          Verified
        </span>
      )}
      {person.rating_avg != null ? (
        <span className="trust-badge rating">
          <Icon name="star" size={14} filled />
          {person.rating_avg.toFixed(1)}
          <span className="muted-inline">({person.rating_count})</span>
        </span>
      ) : (
        <span className="trust-badge new">New member</span>
      )}
    </span>
  );
}

const TAGS = { on_time: "On time", friendly: "Friendly", easy_to_find: "Easy to find", felt_safe: "Felt safe" };

export function RatePerson({ tripId, person }) {
  const [stars, setStars] = useState(0);
  const [tags, setTags] = useState([]);
  const [state, setState] = useState({ done: false, error: "" });

  if (state.done) return <Notice kind="success">Thanks for rating {person.display_name}.</Notice>;

  const toggle = (tag) => setTags((t) => (t.includes(tag) ? t.filter((x) => x !== tag) : [...t, tag]));

  async function submit() {
    try {
      await api.rate(tripId, { rated_user_id: person.id, stars, tags });
      setState({ done: true, error: "" });
    } catch (err) {
      setState({ done: false, error: err.message });
    }
  }

  return (
    <div className="rate">
      <div className="person-row">
        <Avatar name={person.display_name} />
        <strong>How was riding with {person.display_name}?</strong>
      </div>
      <div className="stars" role="radiogroup" aria-label={`Rate ${person.display_name}`}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={stars === n}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            className={n <= stars ? "star on" : "star"}
            onClick={() => setStars(n)}
          >
            <Icon name="star" size={30} filled />
          </button>
        ))}
      </div>
      <div className="chips">
        {Object.entries(TAGS).map(([tag, label]) => (
          <button
            key={tag}
            type="button"
            aria-pressed={tags.includes(tag)}
            className={tags.includes(tag) ? "chip on" : "chip"}
            onClick={() => toggle(tag)}
          >
            {label}
          </button>
        ))}
      </div>
      {state.error && <p className="error">{state.error}</p>}
      <button className="primary small" disabled={!stars} onClick={submit}>
        Submit rating
      </button>
    </div>
  );
}

const REASONS = {
  no_show: "Didn't show up",
  unsafe: "Felt unsafe",
  harassment: "Harassment",
  fake_profile: "Fake profile",
  other: "Something else",
};

// Report / Block, shown next to a co-traveller's contact details.
export function SafetyActions({ userId, tripId }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("no_show");
  const [details, setDetails] = useState("");
  const [message, setMessage] = useState("");

  async function sendReport() {
    try {
      await api.report(userId, { reason, trip_id: tripId, details: details.trim() || null });
      setOpen(false);
      setMessage("Report sent. Our team will review it.");
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function block() {
    if (!window.confirm("Block this person? You won't see each other's rides.")) return;
    try {
      await api.block(userId);
      setMessage("Blocked. You won't see each other's rides.");
    } catch (err) {
      setMessage(err.message);
    }
  }

  return (
    <div className="safety">
      <div className="safety-links">
        <span className="safety-label">
          <Icon name="shield" size={16} />
          Safety
        </span>
        <button type="button" className="small" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <Icon name="flag" size={16} />
          Report
        </button>
        <button type="button" className="small" onClick={block}>
          <Icon name="ban" size={16} />
          Block
        </button>
      </div>
      {open && (
        <div className="report-form">
          <label>
            What happened?
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              {Object.entries(REASONS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </label>
          <label>
            <span>
              Details <span className="muted-inline">(optional)</span>
            </span>
            <input value={details} onChange={(e) => setDetails(e.target.value)} maxLength={1000} />
          </label>
          <button type="button" className="small" onClick={sendReport}>
            Send report
          </button>
        </div>
      )}
      {message && <p className="muted small-text">{message}</p>}
    </div>
  );
}

// Uses the phone's own share sheet when there is one, otherwise copies the link.
export function ShareButton({ tripId }) {
  const [message, setMessage] = useState("");

  async function copy(url) {
    try {
      await navigator.clipboard.writeText(url);
      setMessage("Link copied. Send it to family on WhatsApp or SMS.");
    } catch {
      setMessage(`Send this link to family: ${url}`); // clipboard blocked: show it instead
    }
  }

  async function share() {
    let url;
    try {
      const { token } = await api.shareTrip(tripId);
      url = `${window.location.origin}/share/${token}`;
    } catch (err) {
      setMessage(err.message);
      return;
    }
    if (!navigator.share) return copy(url);
    try {
      await navigator.share({ title: "My RideMate ride", url });
      setMessage("");
    } catch (err) {
      // AbortError = the user closed the share sheet on purpose. Anything else (sheet not
      // allowed, not supported here...) falls back to copying the link.
      if (err.name !== "AbortError") await copy(url);
    }
  }

  return (
    <>
      <button type="button" className="small" onClick={share}>
        <Icon name="share" size={16} />
        Share with family
      </button>
      {message && <p className="muted small-text share-message">{message}</p>}
    </>
  );
}
