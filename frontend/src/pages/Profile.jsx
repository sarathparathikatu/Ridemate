import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import Icon from "../components/Icon.jsx";
import { TrustBadges } from "../components/Trust.jsx";
import { Avatar, Notice } from "../components/ui.jsx";

export default function Profile() {
  const { user, refreshUser, logout } = useAuth();
  const [phone, setPhone] = useState(user.phone ?? "");
  const [sent, setSent] = useState(null); // response of send-code while we wait for the code
  const [code, setCode] = useState("");
  const [message, setMessage] = useState({ text: "", error: false });
  const [blocked, setBlocked] = useState([]);

  useEffect(() => {
    // The profile in memory is from login time; ratings may have arrived since.
    refreshUser().catch(() => {});
    api.blocked().then(setBlocked).catch(() => {});
  }, [refreshUser]);

  async function sendCode(event) {
    event.preventDefault();
    try {
      setSent(await api.sendPhoneCode(phone.trim()));
      setMessage({ text: `We sent a 6-digit code to ${phone.trim()}.`, error: false });
    } catch (err) {
      setMessage({ text: err.message, error: true });
    }
  }

  async function verify(event) {
    event.preventDefault();
    try {
      await api.verifyPhone(code.trim());
      await refreshUser();
      setSent(null);
      setCode("");
      setMessage({ text: "Phone verified. Co-travellers now see your Verified badge.", error: false });
    } catch (err) {
      setMessage({ text: err.message, error: true });
    }
  }

  async function unblock(id) {
    await api.unblock(id);
    setBlocked((all) => all.filter((b) => b.id !== id));
  }

  return (
    <div className="page narrow">
      <header className="account-head">
        <div className="person-text">
          <h1>{user.display_name}</h1>
          <p className="muted">{user.email}</p>
          <TrustBadges person={user} />
        </div>
        <Avatar name={user.display_name} size="xl" />
      </header>

      <div className="tiles">
        <div className="tile">
          <Icon name="star" size={20} filled={user.rating_avg != null} />
          <strong>{user.rating_avg != null ? user.rating_avg.toFixed(1) : "New"}</strong>
          <span>{user.rating_avg != null ? `${user.rating_count} ratings` : "No ratings yet"}</span>
        </div>
        <div className="tile">
          <Icon name="shield" size={20} />
          <strong>{user.phone_verified ? "Verified" : "Unverified"}</strong>
          <span>Phone number</span>
        </div>
        <div className="tile">
          <Icon name="ban" size={20} />
          <strong>{blocked.length}</strong>
          <span>Blocked</span>
        </div>
      </div>

      <section className="card form">
        <h2 className="card-title">
          <Icon name="phone" size={18} /> Phone number
        </h2>
        <p className="muted small-text">
          A verified phone earns you the Verified badge, so hosts and riders trust you faster.
        </p>
        {user.phone_verified && !sent && <Notice kind="success">{user.phone} is verified.</Notice>}
        {!sent ? (
          <form className="form" onSubmit={sendCode}>
            <label>
              Mobile number
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                pattern="\+?[0-9]{10,15}"
                placeholder="e.g. 9876543210"
              />
            </label>
            <button className="primary">{user.phone_verified ? "Change and verify" : "Send code"}</button>
          </form>
        ) : (
          <form className="form" onSubmit={verify}>
            <label>
              6-digit code
              <input
                className="code-input"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                required
                pattern="[0-9]{6}"
                maxLength={6}
              />
            </label>
            {sent.dev_code && (
              <Notice kind="info">
                Development mode (no SMS service yet): your code is <strong>{sent.dev_code}</strong>
              </Notice>
            )}
            <button className="primary">Verify</button>
            <button type="button" className="link" onClick={() => setSent(null)}>
              Use a different number
            </button>
          </form>
        )}
        {message.text && <p className={message.error ? "error" : "muted"}>{message.text}</p>}
      </section>

      <section className="card">
        <h2 className="card-title">
          <Icon name="ban" size={18} /> Blocked people
        </h2>
        {blocked.length === 0 ? (
          <p className="muted">Nobody. You can block someone from a ride's contact card.</p>
        ) : (
          <div className="list">
            {blocked.map((b) => (
              <div key={b.id} className="request-row">
                <div className="person-row">
                  <Avatar name={b.display_name} size="sm" />
                  <span>{b.display_name}</span>
                </div>
                <button className="small" onClick={() => unblock(b.id)}>
                  Unblock
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="card-title">
          <Icon name="lock" size={18} /> Your privacy
        </h2>
        <ul className="privacy-list">
          <li>
            <Icon name="users" size={16} />
            Your phone and email are shown only to people in a ride you've accepted or joined.
          </li>
          <li>
            <Icon name="wallet" size={16} />
            No payments in the app: you pay the driver directly.
          </li>
          <li>
            <Icon name="user" size={16} />
            No ID documents are ever asked for or stored.
          </li>
        </ul>
      </section>

      <button className="danger block logout" onClick={logout}>
        <Icon name="logout" size={18} />
        Log out
      </button>
    </div>
  );
}
