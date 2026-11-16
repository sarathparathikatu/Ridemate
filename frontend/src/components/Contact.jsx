import Icon from "./Icon.jsx";
import { TrustBadges } from "./Trust.jsx";
import { Avatar } from "./ui.jsx";

// Only rendered with data the API sends after a request is accepted.
export default function Contact({ person, extra }) {
  return (
    <div className="contact">
      <div className="host-card">
        <Avatar name={person.display_name} size="lg" />
        <div className="person-text">
          <strong>{person.display_name}</strong>
          {extra && <span className="muted small-text">{extra}</span>}
          <TrustBadges person={person} />
        </div>
        <div className="host-actions">
          {person.phone && (
            <a className="round-button call" href={`tel:${person.phone}`} aria-label={`Call ${person.display_name}`} title={`Call ${person.phone}`}>
              <Icon name="phone" />
            </a>
          )}
          <a className="round-button" href={`mailto:${person.email}`} aria-label={`Email ${person.display_name}`} title={person.email}>
            <Icon name="mail" />
          </a>
        </div>
      </div>
      <p className="contact-lines">
        {person.phone && <a href={`tel:${person.phone}`}>{person.phone}</a>}
        <a href={`mailto:${person.email}`}>{person.email}</a>
      </p>
    </div>
  );
}
