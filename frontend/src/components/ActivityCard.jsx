import { LOT_STATUS } from "../constants.js";
import { money } from "../lib/format.js";
import BookVisual from "./BookVisual.jsx";
import StatusPill from "./StatusPill.jsx";

/** Card de um lote em que o licitante participou, com atalhos para o lote e o comprovante. */
export default function ActivityCard({ lot, onOpenLot, onOpenReceipt }) {
  const isClosed = lot.status === LOT_STATUS.closed;
  return (
    <article className="activity-card">
      <div className="activity-cover">
        <BookVisual title={lot.title} cover={lot.cover_url} />
      </div>
      <div className="activity-content">
        <div className="activity-top">
          <StatusPill status={lot.status} />
          {lot.is_winner && <span className="winner-pill">✓ Arrematado por você</span>}
        </div>
        <h3>{lot.title}</h3>
        <p>{lot.authors || "Livro de coleção"}</p>
        <div className="activity-facts">
          <span>Seu maior lance <strong>{money(lot.my_max_bid_cents)}</strong></span>
          <span>{isClosed ? "Resultado" : "Lance atual"} <strong>{money(lot.winning_cents || lot.current_cents)}</strong></span>
        </div>
      </div>
      <div className="activity-actions">
        <button className="button button-secondary" onClick={() => onOpenLot(lot.id)}>Ver lote</button>
        {lot.receipt_url && (
          <button className="button button-primary" onClick={() => onOpenReceipt(lot.receipt_url)}>Comprovante ↗</button>
        )}
      </div>
    </article>
  );
}
