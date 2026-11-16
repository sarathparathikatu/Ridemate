import { HeroArt } from "./Art.jsx";
import Icon, { Logo } from "./Icon.jsx";

const POINTS = [
  { icon: "train", text: "Find people from your train going the same way" },
  { icon: "wallet", text: "One auto or cab, one fare, split between you" },
  { icon: "lock", text: "Contacts stay private until the host accepts" },
];

// Login and Register: a dark hero with the pitch, and the form in a sheet over it
// (phone) or beside it (laptop).
export default function AuthLayout({ children }) {
  return (
    <div className="auth">
      <section className="auth-hero">
        <HeroArt />
        <div className="auth-brand">
          <Logo size={36} />
          <span>RideMate</span>
        </div>
        <div className="auth-pitch">
          <h1 className="auth-title">
            The train's in.
            <br />
            Cabs are gone.
            <br />
            <em>Ride together.</em>
          </h1>
          <ul className="auth-points">
            {POINTS.map((point) => (
              <li key={point.text}>
                <span className="auth-point-icon">
                  <Icon name={point.icon} size={18} />
                </span>
                {point.text}
              </li>
            ))}
          </ul>
        </div>
      </section>
      <div className="auth-sheet">{children}</div>
    </div>
  );
}
