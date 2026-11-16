import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import Icon from "../components/Icon.jsx";
import { REASONS } from "../components/Trust.jsx";
import { Avatar, EmptyState, Notice, SkeletonCards } from "../components/ui.jsx";
import { formatClock, formatDay, plural } from "../format.js";

const when = (iso) => `${formatDay(iso)}, ${formatClock(iso)}`;
const SERIOUS = new Set(["unsafe", "harassment"]);

function Person({ person, role }) {
  return (
    <div className="person-row">
      <Avatar name={person.display_name} />
      <div className="person-text">
        <span className="muted small-text">{role}</span>
        <strong>{person.display_name}</strong>
        <a className="muted small-text" href={`mailto:${person.email}`}>
          {person.email}
        </a>
      </div>
    </div>
  );
}

// The signals that help decide: has this happened before, and how established is the account?
function Facts({ person }) {
  return (
    <div className="facts">
      {person.is_suspended && <span className="pill status-cancelled">Suspended</span>}
      <span className={person.reports_received > 1 ? "pill status-cancelled" : "pill"}>
        {plural(person.reports_received, "report")} received
      </span>
      <span className="pill">{person.phone_verified ? "Phone verified" : "Phone not verified"}</span>
      <span className="pill">
        {person.rating_avg != null ? `★ ${person.rating_avg.toFixed(1)} (${person.rating_count})` : "No ratings yet"}
      </span>
      <span className="pill">Joined {formatDay(person.created_at)}</span>
    </div>
  );
}

function ReportCard({ report, onDone }) {
  const [note, setNote] = useState("");
  const [state, setState] = useState({ busy: false, error: "" });

  async function decide(action) {
    const warning =
      `Suspend ${report.reported.display_name}?\n\n` +
      "They are logged out, their rides are cancelled and their seats in other rides are freed. " +
      "You can lift the suspension later.";
    if (action === "suspend" && !window.confirm(warning)) return;
    setState({ busy: true, error: "" });
    try {
      await api.resolveReport(report.id, action, note.trim());
      onDone();
    } catch (err) {
      setState({ busy: false, error: err.message });
    }
  }

  return (
    <article className="card report-card">
      <div className="report-top">
        <span className={SERIOUS.has(report.reason) ? "pill status-cancelled" : "pill status-pending"}>
          {REASONS[report.reason]}
        </span>
        <span className="muted small-text">
          #{report.id} · {when(report.created_at)}
        </span>
      </div>

      <Person person={report.reported} role="Reported" />
      <Facts person={report.reported} />

      {report.details ? (
        <p className="report-quote">“{report.details}”</p>
      ) : (
        <p className="muted small-text">No details were given.</p>
      )}
      {report.trip && (
        <p className="meta">
          <span>
            <Icon name="rides" size={16} />
            {report.trip.start_label} to {report.trip.end_label} · {when(report.trip.depart_at)} · {report.trip.status}
          </span>
        </p>
      )}

      <div className="people">
        <Person person={report.reporter} role="Reported by" />
      </div>

      {report.status === "open" ? (
        <div className="report-actions">
          <label>
            <span>
              Note for the record <span className="muted-inline">(optional)</span>
            </span>
            <input value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} placeholder="Why you decided this" />
          </label>
          {state.error && <p className="error">{state.error}</p>}
          <div className="actions">
            <button className="small" disabled={state.busy} onClick={() => decide("dismiss")}>
              Dismiss
            </button>
            <button className="small danger-solid" disabled={state.busy} onClick={() => decide("suspend")}>
              <Icon name="ban" size={16} />
              Suspend account
            </button>
          </div>
        </div>
      ) : (
        <Notice kind={report.resolution === "suspended" ? "error" : "info"}>
          {report.resolution === "suspended" ? "Account suspended" : "Dismissed"} by{" "}
          {report.reviewed_by_name ?? "a former admin"} · {when(report.reviewed_at)}
          {report.admin_note && ` · “${report.admin_note}”`}
        </Notice>
      )}
    </article>
  );
}

function SuspendedCard({ person, onDone }) {
  const [error, setError] = useState("");

  async function lift() {
    if (!window.confirm(`Let ${person.display_name} use RideMate again?`)) return;
    try {
      await api.unsuspend(person.id);
      onDone();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <article className="card report-card">
      <Person person={person} role={`Suspended ${when(person.suspended_at)}`} />
      <Facts person={person} />
      {error && <p className="error">{error}</p>}
      <div className="actions">
        <button className="small" onClick={lift}>
          Lift suspension
        </button>
      </div>
    </article>
  );
}

const TABS = [
  { id: "open", label: "Open" },
  { id: "reviewed", label: "Reviewed" },
  { id: "suspended", label: "Suspended" },
];

// Only reachable by admins. Hiding the page is a courtesy; the API checks every call itself.
export default function Admin() {
  const [tab, setTab] = useState("open");
  const [summary, setSummary] = useState(null);
  const [items, setItems] = useState(null); // reports, or suspended people, for the current tab
  const [next, setNext] = useState(null);
  const [error, setError] = useState("");

  const shown = useRef(tab);
  shown.current = tab;

  const load = useCallback(async () => {
    try {
      const [counts, list] = await Promise.all([
        api.adminSummary(),
        tab === "suspended" ? api.suspendedUsers() : api.adminReports(tab),
      ]);
      // The person may have switched tabs while this was loading: a late answer for the
      // old tab must not land in the new one (the two lists hold different things).
      if (shown.current !== tab) return;
      setSummary(counts);
      setItems(tab === "suspended" ? list : list.items);
      setNext(tab === "suspended" ? null : list.next_cursor);
      setError("");
    } catch (err) {
      setError(err.message);
    }
  }, [tab]);

  useEffect(() => {
    setItems(null); // show placeholders while the other tab loads
    load();
  }, [load]);

  async function showOlder() {
    try {
      const more = await api.adminReports(tab, next);
      setItems((all) => [...all, ...more.items]);
      setNext(more.next_cursor);
    } catch (err) {
      setError(err.message);
    }
  }

  const counts = { open: summary?.open_reports, suspended: summary?.suspended_users };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <p className="eyebrow">Moderation</p>
          <h1>Reports</h1>
        </div>
        <button className="round-button" onClick={load} aria-label="Refresh" title="Refresh">
          <Icon name="refresh" />
        </button>
      </header>

      <div className="tabs three" role="tablist" aria-label="Moderation lists">
        {TABS.map((t) => (
          <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "on" : ""} onClick={() => setTab(t.id)}>
            {t.label} {counts[t.id] > 0 && <span className="count-badge">{counts[t.id]}</span>}
          </button>
        ))}
      </div>

      {error && <Notice kind="error">{error}</Notice>}
      {!items && !error && <SkeletonCards count={2} />}

      {items?.length === 0 && tab === "open" && (
        <EmptyState icon="shield" title="Nothing waiting" text="Every report has been reviewed." />
      )}
      {items?.length === 0 && tab === "reviewed" && (
        <EmptyState icon="check" title="No reviewed reports yet" text="Reports you decide show up here, with who decided and why." />
      )}
      {items?.length === 0 && tab === "suspended" && (
        <EmptyState icon="users" title="Nobody is suspended" text="Suspended accounts are listed here, and can be reinstated." />
      )}

      <div className="admin-grid">
        {tab === "suspended"
          ? items?.map((person) => <SuspendedCard key={person.id} person={person} onDone={load} />)
          : items?.map((report) => <ReportCard key={report.id} report={report} onDone={load} />)}
      </div>
      {next && (
        <button className="more" onClick={showOlder}>
          Show older reports
        </button>
      )}
    </div>
  );
}
