import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import AuthLayout from "../components/AuthLayout.jsx";

export default function Register() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ display_name: "", email: "", phone: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.register({ ...form, phone: form.phone.trim() || null });
      await login(form.email, form.password);
      navigate("/");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout>
      <form className="form auth-card" onSubmit={submit}>
        <div>
          <h2 className="auth-card-title">Create your account</h2>
          <p className="muted">It takes less than a minute.</p>
        </div>
        <label>
          Your name
          <input
            value={form.display_name}
            onChange={set("display_name")}
            required
            minLength={2}
            maxLength={50}
            placeholder="So co-travellers can find you"
          />
        </label>
        <label>
          Email
          <input type="email" value={form.email} onChange={set("email")} required autoComplete="email" />
        </label>
        <label>
          <span>
            Phone <span className="muted-inline">(optional)</span>
          </span>
          <input
            type="tel"
            value={form.phone}
            onChange={set("phone")}
            placeholder="Shown only to your accepted co-travellers"
            pattern="\+?[0-9]{10,15}"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={form.password}
            onChange={set("password")}
            required
            minLength={8}
            autoComplete="new-password"
            placeholder="At least 8 characters"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button className="cta" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
        <p className="muted center">
          Already registered? <Link to="/login">Log in</Link>
        </p>
      </form>
    </AuthLayout>
  );
}
