import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { useLive } from "./live.jsx";
import FindRide from "./pages/FindRide.jsx";
import Login from "./pages/Login.jsx";
import MyRides from "./pages/MyRides.jsx";
import OfferRide from "./pages/OfferRide.jsx";
import Profile from "./pages/Profile.jsx";
import Register from "./pages/Register.jsx";
import SharedRide from "./pages/SharedRide.jsx";

// Client-side guard for UX only. The real protection is the API's get_current_user:
// anyone can bypass React code, nobody can bypass the server.
function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted center">Loading…</p>;
  return user ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const { user, logout } = useAuth();
  const { connected } = useLive();

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">RideMate</span>
        {user && (
          <span className="who">
            <span className={`live-dot ${connected ? "on" : ""}`} title={connected ? "Live" : "Reconnecting…"} />
            {user.display_name}
            <button className="link" onClick={logout}>
              Log out
            </button>
          </span>
        )}
      </header>

      <main className="content">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/share/:token" element={<SharedRide />} />
          <Route path="/" element={<RequireAuth><FindRide /></RequireAuth>} />
          <Route path="/offer" element={<RequireAuth><OfferRide /></RequireAuth>} />
          <Route path="/rides" element={<RequireAuth><MyRides /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {user && (
        <nav className="tabbar">
          <NavLink to="/" end>Find a ride</NavLink>
          <NavLink to="/offer">Offer a ride</NavLink>
          <NavLink to="/rides">My rides</NavLink>
          <NavLink to="/profile">Profile</NavLink>
        </nav>
      )}
    </div>
  );
}
