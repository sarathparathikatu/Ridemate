import { Link, NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Icon, { Logo } from "./components/Icon.jsx";
import { Avatar } from "./components/ui.jsx";
import { useLive } from "./live.jsx";
import Admin from "./pages/Admin.jsx";
import FindRide from "./pages/FindRide.jsx";
import Login from "./pages/Login.jsx";
import MyRides from "./pages/MyRides.jsx";
import OfferRide from "./pages/OfferRide.jsx";
import Profile from "./pages/Profile.jsx";
import Register from "./pages/Register.jsx";
import SharedRide from "./pages/SharedRide.jsx";

// Client-side guard for UX only. The real protection is the API's get_current_user:
// anyone can bypass React code, nobody can bypass the server.
function RequireAuth({ children, admin = false }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="muted center loading-line">Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (admin && !user.is_admin) return <Navigate to="/" replace />;
  return children;
}

const NAV = [
  { to: "/", label: "Ride", icon: "search", end: true },
  { to: "/offer", label: "Offer", icon: "plus" },
  { to: "/rides", label: "Activity", icon: "rides" },
  { to: "/profile", label: "Account", icon: "user" },
];
const ADMIN_NAV = { to: "/admin", label: "Admin", icon: "shield" };

// Screens where the map fills the page and the content floats over it.
const MAP_ROUTES = ["/", "/offer"];
// Screens with their own full-page layout and no header.
const AUTH_ROUTES = ["/login", "/register"];

// The same links twice: across the top on a laptop, as a tab bar at the bottom on a phone.
function NavLinks({ className, admin }) {
  const items = admin ? [...NAV, ADMIN_NAV] : NAV;
  return (
    <nav className={className} aria-label="Main">
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} end={item.end}>
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  );
}

export default function App() {
  const { user } = useAuth();
  const { connected } = useLive();
  const { pathname } = useLocation();
  let mode = "page";
  if (AUTH_ROUTES.includes(pathname)) mode = "auth";
  else if (user && MAP_ROUTES.includes(pathname)) mode = "map";

  return (
    <div className={`app mode-${mode}`}>
      {mode !== "auth" && (
        <header className="topbar">
          <div className="topbar-inner">
            <Link to="/" className="brand" aria-label="RideMate home">
              <Logo size={32} />
              <span>RideMate</span>
            </Link>
            {user && <NavLinks className="topnav" admin={user.is_admin} />}
            {user && (
              <div className="topbar-right">
                <span
                  className={`live-chip ${connected ? "on" : ""}`}
                  title={connected ? "Live updates on" : "Reconnecting…"}
                >
                  <span className="live-dot" />
                  {connected ? "Live" : "Offline"}
                </span>
                <Link to="/profile" className="avatar-link" aria-label="Your account">
                  <Avatar name={user.display_name} size="sm" />
                </Link>
              </div>
            )}
          </div>
        </header>
      )}

      <main className="main">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/share/:token" element={<SharedRide />} />
          <Route path="/" element={<RequireAuth><FindRide /></RequireAuth>} />
          <Route path="/offer" element={<RequireAuth><OfferRide /></RequireAuth>} />
          <Route path="/rides" element={<RequireAuth><MyRides /></RequireAuth>} />
          <Route path="/profile" element={<RequireAuth><Profile /></RequireAuth>} />
          <Route path="/admin" element={<RequireAuth admin><Admin /></RequireAuth>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      {user && mode !== "auth" && <NavLinks className="tabbar" admin={user.is_admin} />}
    </div>
  );
}
