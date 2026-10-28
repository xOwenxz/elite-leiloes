import { LOT_HISTORY_PREVIEW_SIZE } from "../constants.js";
import { dateTime, money, padNumber } from "../lib/format.js";

/** Selo de integridade da trilha: em verificação, íntegro ou com problema. */
function integrityBadgeLabel(loading, auditValid) {
  if (loading) return "Conferindo…";
  return auditValid ? "✓ íntegro" : "!";
}

/**
 * Prévia dos últimos lances do lote, exibida na parte inferior do modal,
 * com atalho para o histórico completo na auditoria pública.
 */
export default function LotHistoryPreview({ history, loading, auditValid, onOpenAudit }) {
  return (
    <div className="dialog-history">
      <div className="history-heading">
        <div>
          <span className="eyebrow muted">TRILHA DO LOTE</span>
          <h3>Últimos lances</h3>
        </div>
        <span className={"integrity-small " + (auditValid ? "good" : "bad")}>
          {integrityBadgeLabel(loading, auditValid)}
        </span>
      </div>
      {history.length ? (
        <div className="history-list">
          {history.slice(0, LOT_HISTORY_PREVIEW_SIZE).map((event) => (
            <div className="history-row" key={event.sequence}>
              <span className="history-index">{padNumber(event.sequence)}</span>
              <span className="history-person">{event.actor}</span>
              <span className="history-time">{dateTime(event.created_at)}</span>
              <strong>{money(event.amount_cents)}</strong>
            </div>
          ))}
        </div>
      ) : (
        <p className="muted-text">{loading ? "Carregando histórico…" : "Este lote ainda não recebeu lances."}</p>
      )}
      <button className="text-link" onClick={onOpenAudit}>Abrir histórico completo <span>↗</span></button>
    </div>
  );
}
