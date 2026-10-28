import { useCallback, useEffect, useState } from "react";
import { LOT_STATUS, ROLES } from "../constants.js";
import { useAsyncAction } from "../hooks/useAsyncAction.js";
import { api, postJson } from "../lib/apiClient.js";
import { money, parseMoney } from "../lib/format.js";
import { auditPath } from "../lib/routes.js";
import BidForm from "./BidForm.jsx";
import BookVisual from "./BookVisual.jsx";
import Countdown from "./Countdown.jsx";
import LotHistoryPreview from "./LotHistoryPreview.jsx";
import StatusPill from "./StatusPill.jsx";

/** Menor lance aceito: lance atual + incremento, ou o lance inicial se ainda não houver lances. */
function minimumBidCents(lot) {
  return lot.current_cents ? lot.current_cents + lot.increment_cents : lot.initial_cents;
}

/** Mensagem de sucesso do lance; avisa quando o lance prorrogou o encerramento. */
function bidSuccessMessage(result) {
  return result.extended_to
    ? "Lance aceito. O lote ganhou mais dois minutos."
    : "Lance aceito. Você está na disputa.";
}

/**
 * Modal com os detalhes de um lote: preço, regras, formulário de lance e prévia do histórico.
 * Recarrega o detalhe (/api/lots/:id) sempre que `revision` muda, isto é, a cada evento em tempo real.
 */
export default function LotDialog({ lot, user, wallet, refresh, revision, notify, close, navigate }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidText, setBidText] = useState("");
  const [error, setError] = useState("");
  const [working, placeBid] = useAsyncAction(setError);

  const isBidder = user.role === ROLES.bidder;
  const isActive = lot.status === LOT_STATUS.active;
  const canBid = isBidder && isActive && !lot.is_leader;
  const minimum = minimumBidCents(lot);

  const load = useCallback(async () => {
    try {
      const result = await api("/lots/" + lot.id);
      setDetail(result);
    } catch (loadError) {
      setError(loadError.message);
    } finally {
      setLoading(false);
    }
  }, [lot.id]);

  useEffect(() => { load(); }, [load, revision]);

  // Sempre que o mínimo muda (novo lance de alguém), sugere o novo valor mínimo no campo.
  useEffect(() => { setBidText((minimum / 100).toFixed(2)); }, [minimum]);

  const sendBid = async (event) => {
    event.preventDefault();
    const amountCents = parseMoney(bidText);
    if (!amountCents) {
      setError("Digite um valor válido para o lance.");
      return;
    }
    await placeBid(async () => {
      const result = await postJson("/lots/" + lot.id + "/bids", { amount_cents: amountCents });
      await refresh();
      await load();
      notify(bidSuccessMessage(result));
    });
  };

  const openAudit = () => navigate(auditPath(lot.id));

  const closeOnBackdrop = (event) => {
    if (event.target === event.currentTarget) close();
  };

  return (
    <div className="modal-scrim" onMouseDown={closeOnBackdrop}>
      <section className="lot-dialog" role="dialog" aria-modal="true" aria-label={"Lote " + lot.title}>
        <button className="modal-close" onClick={close} aria-label="Fechar">×</button>
        <div className="dialog-grid">
          <div className="dialog-visual">
            <BookVisual title={lot.title} cover={lot.cover_url} />
            <span className="source-tag">Origem: {lot.source_label}</span>
          </div>
          <div className="dialog-content">
            <div className="dialog-topline">
              <StatusPill status={lot.status} />
              <span>Leiloeiro · {lot.seller_name}</span>
            </div>
            <span className="lot-author">{lot.authors || "Livro de coleção"}</span>
            <h2>{lot.title}</h2>
            <p className="dialog-description">{lot.description || "Item selecionado no catálogo externo."}</p>
            <div className="price-panel">
              <div>
                <span>{lot.current_cents ? "LANCE ATUAL" : "LANCE INICIAL"}</span>
                <strong>{money(lot.current_cents || lot.initial_cents)}</strong>
              </div>
              {isActive && <Countdown endAt={lot.end_at} />}
            </div>
            <div className="lot-rule-row">
              <span>Incremento mínimo</span>
              <strong>{money(lot.increment_cents)}</strong>
            </div>
            <div className="lot-rule-row">
              <span>Lances registrados</span>
              <strong>{lot.bid_count}</strong>
            </div>
            {lot.is_leader && (
              <div className="notice success">Você está liderando. Seu saldo reservado neste lote é {money(lot.current_cents)}.</div>
            )}
            {canBid && (
              <BidForm
                minimumCents={minimum}
                availableCents={wallet?.available_cents}
                bidText={bidText}
                onBidTextChange={setBidText}
                working={working}
                onSubmit={sendBid}
              />
            )}
            {isBidder && lot.is_leader && (
              <div className="self-bid-note">Você já lidera este lote e não pode cobrir seu próprio lance.</div>
            )}
            {error && <div className="notice error">{error}</div>}
            <div className="dialog-links">
              {lot.source_url && <a href={lot.source_url} target="_blank" rel="noreferrer">Ver item de origem ↗</a>}
              <button onClick={openAudit}>Auditoria pública ↗</button>
            </div>
          </div>
        </div>
        <LotHistoryPreview
          history={detail?.history || []}
          loading={loading}
          auditValid={detail?.audit_valid}
          onOpenAudit={openAudit}
        />
      </section>
    </div>
  );
}
