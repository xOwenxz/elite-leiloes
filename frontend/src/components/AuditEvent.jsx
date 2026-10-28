import { EVENT_LABELS } from "../constants.js";
import { dateTime, money, padNumber, shortHash } from "../lib/format.js";

/** Marcador visual do evento na linha do tempo. */
function eventMarker(type) {
  if (type === "bid_placed") return "↗";
  if (type === "lot_closed") return "✓";
  return "·";
}

/** Descrição legível de um evento da trilha de auditoria. */
function describeEvent(event) {
  switch (event.type) {
    case "bid_placed":
      return event.actor + " ofereceu " + money(event.amount_cents);
    case "lot_created":
      return "Lance inicial " + money(event.payload.initial_cents) + " · incremento mínimo " + money(event.payload.increment_cents);
    case "lot_closed":
      return "Vencedor " + (event.payload.winner_alias || "Licitante") + " · " + money(event.amount_cents);
    case "lot_closed_without_bids":
      return "Encerrado sem vencedor.";
    case "lot_cancelled":
      return "Cancelamento registrado.";
    default:
      return "Registro operacional do leilão.";
  }
}

/** Data do evento, acrescida do novo horário de encerramento quando o lance prorrogou o pregão. */
function eventTimestamp(event) {
  const extension = event.payload.end_extended_to ? " · novo fim " + dateTime(event.payload.end_extended_to) : "";
  return dateTime(event.created_at) + extension;
}

/** Item da linha do tempo pública de auditoria. */
export default function AuditEvent({ event }) {
  return (
    <article className="audit-event">
      <div className="event-marker">{eventMarker(event.type)}</div>
      <div className="event-main">
        <div className="event-title">
          <strong>{EVENT_LABELS[event.type] || event.type}</strong>
          <span>#{padNumber(event.sequence, 3)}</span>
        </div>
        <p>{describeEvent(event)}</p>
        <small>{eventTimestamp(event)}</small>
      </div>
      <code className="event-hash">{shortHash(event.hash)}</code>
    </article>
  );
}
