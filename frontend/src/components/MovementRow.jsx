import { dateTime, money } from "../lib/format.js";

/** Ícone de cada tipo de movimentação: entrada (depósito), crédito do leiloeiro ou pagamento. */
function movementIcon(kind) {
  if (kind === "deposit") return "↓";
  if (kind === "seller_credit") return "↑";
  return "↗";
}

/** Pagamento de arremate é a única movimentação que sai da carteira. */
function isDebit(kind) {
  return kind === "auction_payment";
}

/** Linha do extrato da carteira. */
export default function MovementRow({ movement }) {
  const debit = isDebit(movement.kind);
  return (
    <div className="movement-row">
      <span className={"movement-icon " + movement.kind}>{movementIcon(movement.kind)}</span>
      <span className="movement-description">
        <strong>{movement.note}</strong>
        <small>{dateTime(movement.created_at)}</small>
      </span>
      <strong className={debit ? "negative" : "positive"}>
        {debit ? "−" : "+"}
        {money(movement.amount_cents)}
      </strong>
    </div>
  );
}
