import { money } from "../lib/format.js";

/**
 * Formulário de lance do modal do lote.
 * Componente controlado: o valor digitado e o envio ficam a cargo do LotDialog.
 */
export default function BidForm({ minimumCents, availableCents, bidText, onBidTextChange, working, onSubmit }) {
  return (
    <form className="bid-form" onSubmit={onSubmit}>
      <label>Seu lance (mínimo {money(minimumCents)})</label>
      <div className="bid-input-wrap">
        <span>R$</span>
        <input
          type="text"
          inputMode="decimal"
          value={bidText}
          onChange={(event) => onBidTextChange(event.target.value)}
          aria-label="Valor do lance"
        />
        <button className="button button-primary" disabled={working}>
          {working ? "Enviando…" : "Dar lance"}
        </button>
      </div>
      <small>Disponível na carteira: {money(availableCents)}. O valor fica reservado enquanto você lidera.</small>
    </form>
  );
}
