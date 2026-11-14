// Only rendered with data the API sends after a request is accepted.
export default function Contact({ person, extra }) {
  return (
    <div className="contact">
      <div>
        <strong>{person.display_name}</strong>
        {extra && <span className="muted"> · {extra}</span>}
      </div>
      <div className="contact-links">
        {person.phone && (
          <a className="button small" href={`tel:${person.phone}`}>
            Call {person.phone}
          </a>
        )}
        <a className="small-link" href={`mailto:${person.email}`}>
          {person.email}
        </a>
      </div>
    </div>
  );
}
