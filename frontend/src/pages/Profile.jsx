import { useEffect, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { TrustBadges } from "../components/Trust.jsx";

export default function Profile() {
  const { user, refreshUser } = useAuth();
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
      setMessage({ text: "Phone verified. Co-travellers now see your ✓ badge.", error: false });
    } catch (err) {
      setMessage({ text: err.message, error: true });
    }
  }

  async function unblock(id) {
    await api.unblock(id);
    setBlocked((all) => all.filter((b) => b.id !== id));
  }

  return (
    <>
      <section className="card trip">
        <h1>{user.display_name}</h1>
        <p className="muted">{user.email}</p>
        <TrustBadges person={user} />
      </section>

      <section className="card form">
        <h2>Phone number</h2>
        {user.phone_verified && !sent && <p className="muted">✓ {user.phone} is verified.</p>}
        {!sent ? (
          <form className="form" onSubmit={sendCode}>
            <label>
              Mobile number
              <input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required pattern="\+?[0-9]{10,15}" placeholder="e.g. 9876543210" />
            </label>
            <button className="primary">{user.phone_verified ? "Change and verify" : "Send code"}</button>
          </form>
        ) : (
          <form className="form" onSubmit={verify}>
            <label>
              6-digit code
              <input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} required pattern="[0-9]{6}" />
            </label>
            {sent.dev_code && (
              <p className="muted">
                Development mode (no SMS service yet): your code is <strong>{sent.dev_code}</strong>
              </p>
            )}
            <button className="primary">Verify</button>
            <button type="button" className="link" onClick={() => setSent(null)}>
              Use a different number
            </button>
          </form>
        )}
        {message.text && <p className={message.error ? "error" : "muted"}>{message.text}</p>}
      </section>

      <section className="card trip">
        <h2>Blocked people</h2>
        {blocked.length === 0 ? (
          <p className="muted">Nobody. Block someone from a ride's contact card if you need to.</p>
        ) : (
          blocked.map((b) => (
            <div key={b.id} className="request-row">
              <span>{b.display_name}</span>
              <button className="small" onClick={() => unblock(b.id)}>Unblock</button>
            </div>
          ))
        )}
      </section>
    </>
  );
}
