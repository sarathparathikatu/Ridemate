// The layout ride apps use: the map is the whole screen and the content sits in a sheet
// over it. On a phone the sheet slides up from the bottom as you scroll; on a laptop it
// is a floating panel on the left.
export default function MapShell({ map, children }) {
  return (
    <div className="shell">
      <div className="map-stage">{map}</div>
      <section className="sheet">
        <span className="sheet-handle" aria-hidden="true" />
        {children}
      </section>
    </div>
  );
}
