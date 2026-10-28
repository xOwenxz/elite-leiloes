import { LOT_STATUS } from "../constants.js";
import { dateTime, money, padNumber, statusLabel } from "../lib/format.js";
import BookVisual from "./BookVisual.jsx";
import Countdown from "./Countdown.jsx";
import StatusPill from "./StatusPill.jsx";

/** Texto de rodapé para lotes que não estão ao vivo: data de início ou status final. */
function inactiveLotCaption(lot) {
  return lot.status === LOT_STATUS.scheduled ? "Início " + dateTime(lot.start_at) : statusLabel(lot.status);
}

/** Card de um lote na vitrine. `index` define o número exibido ("LOTE 01"). */
export default function LotCard({ lot, index = 0, onClick }) {
  const isLive = lot.status === LOT_STATUS.active;
  const currentPrice = lot.current_cents || lot.initial_cents;

  return (
    <button className={"lot-card" + (isLive ? " lot-live" : "")} onClick={onClick}>
      <div className="lot-card-visual">
        <BookVisual title={lot.title} cover={lot.cover_url} />
        <StatusPill status={lot.status} />
        {lot.is_leader && <span className="leading-badge">Você lidera</span>}
        <span className="lot-number">LOTE {padNumber(index + 1)}</span>
      </div>
      <div className="lot-card-body">
        <span className="lot-author">{lot.authors || "Livro de coleção"}</span>
        <h3>{lot.title}</h3>
        <div className="lot-price-row">
          <div>
            <small>{lot.current_cents ? "Lance atual" : "Lance inicial"}</small>
            <strong>{money(currentPrice)}</strong>
          </div>
          <div className="lot-bids">
            <span>♧</span>
            {lot.bid_count} {lot.bid_count === 1 ? "lance" : "lances"}
          </div>
        </div>
        <div className="lot-card-bottom">
          {isLive
            ? <Countdown endAt={lot.end_at} compact />
            : <span className="lot-date">{inactiveLotCaption(lot)}</span>}
          <span className="card-arrow">↗</span>
        </div>
      </div>
    </button>
  );
}
