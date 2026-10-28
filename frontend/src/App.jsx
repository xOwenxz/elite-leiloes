import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api, dateTime, localInputValue, money, parseMoney, shortHash } from "./api.js";

const DEMO_ACCOUNTS = [
  { label: "Leiloeiro", name: "Leiloeiro Verzel", email: "leiloeiro@demo.local", password: "verzel123", role: "seller", mark: "L" },
  { label: "Licitante Ana", name: "Ana Colecionadora", email: "ana@demo.local", password: "ana123", role: "bidder", mark: "A" },
  { label: "Licitante Bruno", name: "Bruno Colecionador", email: "bruno@demo.local", password: "bruno123", role: "bidder", mark: "B" },
];

const EVENT_LABELS = {
  lot_created: "Lote criado",
  lot_started: "Leilão iniciado",
  bid_placed: "Lance aceito",
  lot_closed: "Leilão encerrado",
  lot_closed_without_bids: "Encerrado sem lances",
  lot_cancelled: "Lote cancelado",
};

function statusLabel(status) {
  return ({ active: "Ao vivo", scheduled: "Agendado", closed: "Encerrado", cancelled: "Cancelado" })[status] || status;
}

function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [globalError, setGlobalError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await api("/bootstrap");
      setData(next);
      setGlobalError("");
    } catch (error) {
      setGlobalError(error.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const stream = new EventSource("/api/events");
    stream.onmessage = () => {
      setRevision((current) => current + 1);
      refresh();
    };
    return () => stream.close();
  }, [refresh]);

  useEffect(() => {
    const onPopState = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const navigate = useCallback((nextPath) => {
    window.history.pushState({}, "", nextPath);
    setPath(nextPath);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const signIn = async (account) => {
    await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email: account.email, password: account.password }),
    });
    await refresh();
  };

  const signOut = async () => {
    await api("/auth/logout", { method: "POST" });
    await refresh();
  };

  if (path.startsWith("/auditoria/")) {
    return <AuditPage lotId={decodeURIComponent(path.slice("/auditoria/".length))} navigate={navigate} />;
  }
  if (path.startsWith("/comprovante/")) {
    return <ReceiptPage token={decodeURIComponent(path.slice("/comprovante/".length))} navigate={navigate} />;
  }
  if (loading && !data) return <LoadingScreen />;
  if (!data?.me) return <LoginScreen onLogin={signIn} error={globalError} />;

  return (
    <Dashboard
      data={data}
      refresh={refresh}
      revision={revision}
      onSignOut={signOut}
      navigate={navigate}
    />
  );
}

function LoadingScreen() {
  return (
    <main className="loading-screen">
      <div className="brand-mark">V</div>
      <div className="spinner" />
      <p>Preparando o pregão...</p>
    </main>
  );
}

function Logo({ compact = false }) {
  return (
    <div className={"brand-lockup" + (compact ? " compact" : "")}>
      <span className="brand-mark">V</span>
      {!compact && <span className="brand-name">elite<span>leilões</span></span>}
    </div>
  );
}

function LoginScreen({ onLogin, error }) {
  const [active, setActive] = useState("");
  const [localError, setLocalError] = useState("");
  const enter = async (account) => {
    setActive(account.email);
    setLocalError("");
    try {
      await onLogin(account);
    } catch (e) {
      setLocalError(e.message);
    } finally {
      setActive("");
    }
  };

  return (
    <main className="login-layout">
      <section className="login-hero">
        <div className="login-brand"><Logo /></div>
        <div className="hero-copy">
          <span className="eyebrow"><span className="live-dot" /> CASA DE LEILÕES DIGITAL</span>
          <h1>Uma disputa.<br /><em>Um novo dono.</em></h1>
          <p>Explore lotes, acompanhe cada lance em tempo real e confira uma trilha pública de auditoria.</p>
          <div className="hero-stat-row">
            <div><strong>Ao vivo</strong><span>Lances atualizados sem recarregar</span></div>
            <div><strong>Verificável</strong><span>Histórico com assinatura de integridade</span></div>
          </div>
        </div>
        <div className="hero-orbit orbit-one" />
        <div className="hero-orbit orbit-two" />
        <span className="hero-index">01 — 03</span>
      </section>

      <section className="login-panel">
        <div className="login-heading">
          <span className="eyebrow muted">AMBIENTE DE DEMONSTRAÇÃO</span>
          <h2>Entre no pregão</h2>
          <p>Escolha um perfil para percorrer o fluxo completo.</p>
        </div>
        {(localError || error) && <div className="notice error">{localError || error}</div>}
        <div className="account-list">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              className="account-card"
              key={account.email}
              onClick={() => enter(account)}
              disabled={!!active}
            >
              <span className={"avatar avatar-" + account.role}>{account.mark}</span>
              <span className="account-copy">
                <strong>{account.label}</strong>
                <small>{account.name}</small>
                <small className="account-secret">{account.email} · senha: {account.password}</small>
              </span>
              <span className="account-arrow">{active === account.email ? "…" : "↗"}</span>
            </button>
          ))}
        </div>
        <div className="demo-note">
          <span className="note-icon">i</span>
          <p>Saldo e lances são simulados. Os perfis de demonstração estão descritos no README.</p>
        </div>
        <footer className="login-footer">ELITE DEV <span>·</span> VERZEL</footer>
      </section>
    </main>
  );
}

function Header({ user, onSignOut, navigate, tab, setTab }) {
  const bidderTabs = [
    ["lots", "Leilões", "◇"],
    ["wallet", "Carteira", "◈"],
    ["activity", "Meus arremates", "↗"],
  ];
  const sellerTabs = [
    ["lots", "Meus lotes", "◇"],
    ["create", "Criar lote", "+"],
    ["wallet", "Financeiro", "◈"],
  ];
  const tabs = user.role === "seller" ? sellerTabs : bidderTabs;
  return (
    <header className="app-header">
      <button className="header-logo" onClick={() => setTab("lots")} aria-label="Início"><Logo /></button>
      <nav className="main-nav">
        {tabs.map(([key, label, icon]) => (
          <button key={key} className={"nav-item" + (tab === key ? " selected" : "")} onClick={() => setTab(key)}>
            <span>{icon}</span>{label}
          </button>
        ))}
      </nav>
      <div className="header-user">
        <span className="role-pill">{user.role === "seller" ? "LEILOEIRO" : "LICITANTE"}</span>
        <span className="header-avatar">{user.name.slice(0, 1)}</span>
        <span className="header-user-name">{user.name}</span>
        <button className="icon-button logout" title="Sair" onClick={onSignOut}>↪</button>
      </div>
    </header>
  );
}

function Dashboard({ data, refresh, revision, onSignOut, navigate }) {
  const [tab, setTab] = useState("lots");
  const [detailId, setDetailId] = useState(null);
  const [toast, setToast] = useState(null);

  const notify = (message, kind = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), 4200);
  };

  const openReceipt = (url) => navigate(url);
  const selectedLot = data.lots.find((lot) => lot.id === detailId);

  return (
    <div className="app-shell">
      <Header user={data.me} onSignOut={onSignOut} navigate={navigate} tab={tab} setTab={setTab} />
      <main className="page-wrap">
        {tab === "lots" && (
          <LotsPage
            data={data}
            onOpen={(id) => setDetailId(id)}
            setTab={setTab}
            notify={notify}
          />
        )}
        {tab === "create" && data.me.role === "seller" && (
          <CreateLotPage
            refresh={refresh}
            notify={notify}
            onCreated={(id) => { setTab("lots"); setDetailId(id); }}
          />
        )}
        {tab === "wallet" && (
          <WalletPage data={data} refresh={refresh} notify={notify} />
        )}
        {tab === "activity" && data.me.role === "bidder" && (
          <ActivityPage data={data} openReceipt={openReceipt} onOpen={(id) => setDetailId(id)} />
        )}
      </main>
      <footer className="app-footer">
        <Logo compact />
        <span>Leilões com regras claras e histórico verificável.</span>
        <button onClick={() => navigate("/auditoria/" + (data.lots[0]?.id || ""))}>Ver auditoria pública <span>↗</span></button>
      </footer>
      {toast && <div className={"toast " + toast.kind}>{toast.message}</div>}
      {selectedLot && (
        <LotDialog
          lot={selectedLot}
          user={data.me}
          wallet={data.wallet}
          refresh={refresh}
          revision={revision}
          notify={notify}
          close={() => setDetailId(null)}
          navigate={navigate}
        />
      )}
    </div>
  );
}


function LotsPage({ data, onOpen, setTab, notify, navigate }) {
  const [filter, setFilter] = useState("active");
  const [query, setQuery] = useState("");
  const isSeller = data.me.role === "seller";
  const labels = [
    ["active", "Ao vivo"],
    ["scheduled", "Agendados"],
    ["closed", "Encerrados"],
    ["all", "Todos"],
  ];
  const filtered = data.lots.filter((lot) => {
    const matchesState = filter === "all" || lot.status === filter;
    const q = query.trim().toLocaleLowerCase("pt-BR");
    const matchesQuery = !q || (lot.title + " " + lot.authors).toLocaleLowerCase("pt-BR").includes(q);
    return matchesState && matchesQuery && (!isSeller || lot.seller_name === data.me.name);
  });

  return (
    <>
      <section className="page-intro">
        <div>
          <span className="eyebrow"><span className="live-dot" /> PREGÃO DIGITAL</span>
          <h1>{isSeller ? "Seus lotes" : "Encontre seu próximo arremate"}</h1>
          <p>{isSeller ? "Acompanhe a disputa e o resultado de cada lote." : "Acompanhe os lotes ao vivo e dispute com segurança."}</p>
        </div>
        {isSeller ? (
          <button className="button button-primary" onClick={() => setTab("create")}><span>＋</span> Criar novo lote</button>
        ) : (
          <div className="wallet-chip">
            <span className="wallet-chip-icon">◈</span>
            <span><small>Disponível</small><strong>{money(data.wallet?.available_cents)}</strong></span>
            <button onClick={() => setTab("wallet")} aria-label="Abrir carteira">+</button>
          </div>
        )}
      </section>

      {data.me.role === "seller" && data.seller_summary && (
        <section className="metric-strip">
          <Metric label="Lotes em andamento" value={data.seller_summary.active_lots} icon="◷" />
          <Metric label="Lotes encerrados" value={data.seller_summary.closed_lots} icon="✓" />
          <Metric label="Total recebido" value={money(data.seller_summary.received_cents)} icon="◈" />
        </section>
      )}

      <section className="catalog-section">
        <div className="section-toolbar">
          <div className="filter-tabs">
            {labels.map(([key, label]) => (
              <button key={key} className={filter === key ? "filter-tab active" : "filter-tab"} onClick={() => setFilter(key)}>
                {label}
                {key === "active" && <span className="tab-dot" />}
              </button>
            ))}
          </div>
          <label className="search-field"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Buscar um lote" /></label>
        </div>
        {filtered.length ? (
          <div className="lot-grid">
            {filtered.map((lot, index) => (
              <LotCard key={lot.id} lot={lot} index={index} onClick={() => onOpen(lot.id)} />
            ))}
          </div>
        ) : (
          <EmptyState
            icon="◇"
            title={isSeller ? "Você ainda não tem lotes nesta etapa" : "Nenhum lote encontrado"}
            detail={isSeller ? "Busque um item no catálogo e publique seu primeiro lote." : "Experimente outra busca ou volte em breve."}
            action={isSeller ? <button className="button button-secondary" onClick={() => setTab("create")}>Criar lote</button> : null}
          />
        )}
      </section>
      <section className="integrity-banner">
        <div className="integrity-icon">✓</div>
        <div><strong>Transparência em cada lance</strong><p>O histórico público é encadeado e conferido com um checkpoint assinado.</p></div>
        {data.lots[0] && <button disabled={!data.lots[0]} onClick={() => data.lots[0] && navigate("/auditoria/" + data.lots[0].id)}>Como verificar <span>↗</span></button>}
      </section>
    </>
  );
}

function Metric({ label, value, icon }) {
  return <div className="metric-card"><span className="metric-icon">{icon}</span><span className="metric-label">{label}</span><strong>{value}</strong></div>;
}

function LotCard({ lot, index = 0, onClick }) {
  const isLive = lot.status === "active";
  const current = lot.current_cents || lot.initial_cents;
  return (
    <button className={"lot-card" + (isLive ? " lot-live" : "")} onClick={onClick}>
      <div className="lot-card-visual">
        <BookVisual title={lot.title} cover={lot.cover_url} />
        <StatusPill status={lot.status} />
        {lot.is_leader && <span className="leading-badge">Você lidera</span>}
        <span className="lot-number">LOTE {String(index + 1).padStart(2, "0")}</span>
      </div>
      <div className="lot-card-body">
        <span className="lot-author">{lot.authors || "Livro de coleção"}</span>
        <h3>{lot.title}</h3>
        <div className="lot-price-row">
          <div><small>{lot.current_cents ? "Lance atual" : "Lance inicial"}</small><strong>{money(current)}</strong></div>
          <div className="lot-bids"><span>♧</span>{lot.bid_count} {lot.bid_count === 1 ? "lance" : "lances"}</div>
        </div>
        <div className="lot-card-bottom">
          {isLive ? <Countdown endAt={lot.end_at} compact /> : <span className="lot-date">{lot.status === "scheduled" ? "Início " + dateTime(lot.start_at) : statusLabel(lot.status)}</span>}
          <span className="card-arrow">↗</span>
        </div>
      </div>
    </button>
  );
}

function StatusPill({ status }) {
  return <span className={"status-pill status-" + status}><span />{statusLabel(status)}</span>;
}

function Countdown({ endAt, compact = false }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.floor((new Date(endAt).getTime() - now) / 1000));
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  const label = seconds === 0 ? "Finalizando" : hours > 0 ? String(hours).padStart(2, "0") + ":" + String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0") : String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
  return compact
    ? <span className="countdown compact-countdown"><span className="clock-icon">◷</span>{label}</span>
    : <div className="countdown-large"><span>ENCERRA EM</span><strong>{label}</strong></div>;
}

function BookVisual({ title, cover }) {
  const [failed, setFailed] = useState(false);
  const palettes = ["cover-terracotta", "cover-forest", "cover-lilac", "cover-ochre"];
  const palette = palettes[(title || "").length % palettes.length];
  if (cover && !failed) return <img className="book-cover-image" src={cover} alt={"Capa de " + title} onError={() => setFailed(true)} />;
  return (
    <div className={"book-cover " + palette}>
      <span className="cover-stamp">ELITE<br />LEILÕES</span>
      <strong>{title}</strong>
      <i />
      <small>EDIÇÃO DE COLEÇÃO</small>
    </div>
  );
}

function EmptyState({ icon, title, detail, action }) {
  return <div className="empty-state"><span className="empty-icon">{icon}</span><h3>{title}</h3><p>{detail}</p>{action}</div>;
}

function LotDialog({ lot, user, wallet, refresh, revision, notify, close, navigate }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [bidText, setBidText] = useState("");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");

  const minimum = lot.current_cents ? lot.current_cents + lot.increment_cents : lot.initial_cents;
  const load = useCallback(async () => {
    try {
      const result = await api("/lots/" + lot.id);
      setDetail(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [lot.id]);

  useEffect(() => { load(); }, [load, revision]);
  useEffect(() => { setBidText((minimum / 100).toFixed(2)); }, [minimum]);

  const sendBid = async (event) => {
    event.preventDefault();
    const amount = parseMoney(bidText);
    if (!amount) { setError("Digite um valor válido para o lance."); return; }
    setWorking(true);
    setError("");
    try {
      const result = await api("/lots/" + lot.id + "/bids", {
        method: "POST",
        body: JSON.stringify({ amount_cents: amount }),
      });
      await refresh();
      await load();
      notify(result.extended_to ? "Lance aceito. O lote ganhou mais dois minutos." : "Lance aceito. Você está na disputa.");
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };

  const canBid = user.role === "bidder" && lot.status === "active" && !lot.is_leader;
  const history = detail?.history || [];
  const copyAudit = () => navigate("/auditoria/" + lot.id);

  return (
    <div className="modal-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <section className="lot-dialog" role="dialog" aria-modal="true" aria-label={"Lote " + lot.title}>
        <button className="modal-close" onClick={close} aria-label="Fechar">×</button>
        <div className="dialog-grid">
          <div className="dialog-visual"><BookVisual title={lot.title} cover={lot.cover_url} /><span className="source-tag">Origem: {lot.source_label}</span></div>
          <div className="dialog-content">
            <div className="dialog-topline"><StatusPill status={lot.status} /><span>Leiloeiro · {lot.seller_name}</span></div>
            <span className="lot-author">{lot.authors || "Livro de coleção"}</span>
            <h2>{lot.title}</h2>
            <p className="dialog-description">{lot.description || "Item selecionado no catálogo externo."}</p>
            <div className="price-panel">
              <div><span>{lot.current_cents ? "LANCE ATUAL" : "LANCE INICIAL"}</span><strong>{money(lot.current_cents || lot.initial_cents)}</strong></div>
              {lot.status === "active" && <Countdown endAt={lot.end_at} />}
            </div>
            <div className="lot-rule-row"><span>Incremento mínimo</span><strong>{money(lot.increment_cents)}</strong></div>
            <div className="lot-rule-row"><span>Lances registrados</span><strong>{lot.bid_count}</strong></div>
            {lot.is_leader && <div className="notice success">Você está liderando. Seu saldo reservado neste lote é {money(lot.current_cents)}.</div>}
            {user.role === "bidder" && !lot.is_leader && lot.status === "active" && (
              <form className="bid-form" onSubmit={sendBid}>
                <label>Seu lance (mínimo {money(minimum)})</label>
                <div className="bid-input-wrap"><span>R$</span><input type="text" inputMode="decimal" value={bidText} onChange={(e) => setBidText(e.target.value)} aria-label="Valor do lance" /><button className="button button-primary" disabled={working}>{working ? "Enviando…" : "Dar lance"}</button></div>
                <small>Disponível na carteira: {money(wallet?.available_cents)}. O valor fica reservado enquanto você lidera.</small>
              </form>
            )}
            {user.role === "bidder" && lot.is_leader && <div className="self-bid-note">Você já lidera este lote e não pode cobrir seu próprio lance.</div>}
            {error && <div className="notice error">{error}</div>}
            <div className="dialog-links">
              {lot.source_url && <a href={lot.source_url} target="_blank" rel="noreferrer">Ver item de origem ↗</a>}
              <button onClick={copyAudit}>Auditoria pública ↗</button>
            </div>
          </div>
        </div>
        <div className="dialog-history">
          <div className="history-heading"><div><span className="eyebrow muted">TRILHA DO LOTE</span><h3>Últimos lances</h3></div><span className={"integrity-small " + (detail?.audit_valid ? "good" : "bad")}>{loading ? "Conferindo…" : detail?.audit_valid ? "✓ íntegro" : "!"}</span></div>
          {history.length ? (
            <div className="history-list">
              {history.slice(0, 6).map((event) => (
                <div className="history-row" key={event.sequence}>
                  <span className="history-index">{String(event.sequence).padStart(2, "0")}</span>
                  <span className="history-person">{event.actor}</span>
                  <span className="history-time">{dateTime(event.created_at)}</span>
                  <strong>{money(event.amount_cents)}</strong>
                </div>
              ))}
            </div>
          ) : <p className="muted-text">{loading ? "Carregando histórico…" : "Este lote ainda não recebeu lances."}</p>}
          <button className="text-link" onClick={copyAudit}>Abrir histórico completo <span>↗</span></button>
        </div>
      </section>
    </div>
  );
}


function CreateLotPage({ refresh, notify, onCreated }) {
  const [query, setQuery] = useState("Machado de Assis");
  const [catalog, setCatalog] = useState(null);
  const [selected, setSelected] = useState(null);
  const [searching, setSearching] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const [initial, setInitial] = useState("30,00");
  const [increment, setIncrement] = useState("5,00");
  const [startAt, setStartAt] = useState(() => localInputValue(new Date(Date.now() - 5_000)));
  const [endAt, setEndAt] = useState(() => localInputValue(new Date(Date.now() + 30 * 60_000)));

  const search = async (event) => {
    event?.preventDefault();
    if (query.trim().length < 2) { setError("Digite pelo menos duas letras para buscar."); return; }
    setSearching(true);
    setError("");
    setSelected(null);
    try {
      const result = await api("/catalog/search", { method: "POST", body: JSON.stringify({ query }) });
      setCatalog(result);
      if (!result.results.length) setError("A busca não retornou itens. Tente outro termo.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSearching(false);
    }
  };

  const create = async (event) => {
    event.preventDefault();
    if (!selected) { setError("Selecione um item do catálogo."); return; }
    const initialCents = parseMoney(initial);
    const incrementCents = parseMoney(increment);
    if (!initialCents || !incrementCents) { setError("Informe lance inicial e incremento válidos."); return; }
    setCreating(true);
    setError("");
    try {
      const result = await api("/lots", {
        method: "POST",
        body: JSON.stringify({
          catalog_item_id: selected.id,
          initial_cents: initialCents,
          increment_cents: incrementCents,
          start_at: new Date(startAt).toISOString(),
          end_at: new Date(endAt).toISOString(),
        }),
      });
      await refresh();
      notify("Lote publicado na vitrine.");
      onCreated(result.lot_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <>
      <section className="page-intro">
        <div><span className="eyebrow">PAINEL DO LEILOEIRO</span><h1>Publique um lote</h1><p>Escolha um item da API pública e defina as regras do pregão.</p></div>
        <div className="source-chip"><span className="source-dot" /> Open Library <small>API de livros</small></div>
      </section>
      <div className="create-layout">
        <section className="form-card catalog-picker">
          <div className="card-kicker"><span>01</span> CATÁLOGO EXTERNO</div>
          <h2>Encontre o item</h2>
          <p className="muted-text">Os dados selecionados ficam salvos no lote para o catálogo seguir funcionando mesmo se a API ficar indisponível.</p>
          <form className="catalog-search-form" onSubmit={search}>
            <label className="search-field large"><span>⌕</span><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Título ou autor" /><button type="submit" disabled={searching}>{searching ? "Buscando…" : "Buscar"}</button></label>
          </form>
          {catalog && <div className={"api-mode mode-" + catalog.mode}><span />{catalog.message}</div>}
          {error && <div className="notice error">{error}</div>}
          {catalog?.results?.length > 0 && (
            <div className="catalog-results">
              {catalog.results.map((item) => (
                <button key={item.id} className={"catalog-result" + (selected?.id === item.id ? " selected" : "")} onClick={() => setSelected(item)}>
                  <span className="mini-cover"><BookVisual title={item.title} cover={item.cover_url} /></span>
                  <span className="catalog-result-copy"><strong>{item.title}</strong><small>{item.authors || "Autor não informado"}</small><small>{item.source_label}</small></span>
                  <span className="select-mark">{selected?.id === item.id ? "✓" : "+"}</span>
                </button>
              ))}
            </div>
          )}
          {!catalog && <div className="catalog-empty"><span>↗</span><p>Busque um livro para carregar título, autor e capa do catálogo.</p></div>}
        </section>

        <form className="form-card lot-settings" onSubmit={create}>
          <div className="card-kicker"><span>02</span> REGRAS DO LOTE</div>
          <h2>Defina a disputa</h2>
          {selected ? (
            <div className="selected-item"><span className="selected-check">✓</span><span><strong>{selected.title}</strong><small>{selected.authors || "Item selecionado"}</small></span><button type="button" onClick={() => setSelected(null)}>Trocar</button></div>
          ) : (
            <div className="select-placeholder">Selecione um item do catálogo para continuar.</div>
          )}
          <div className="form-two">
            <label>Lance inicial <span className="input-money"><i>R$</i><input value={initial} onChange={(e) => setInitial(e.target.value)} inputMode="decimal" /></span></label>
            <label>Incremento mínimo <span className="input-money"><i>R$</i><input value={increment} onChange={(e) => setIncrement(e.target.value)} inputMode="decimal" /></span></label>
          </div>
          <label>Início do lote <input className="datetime-input" type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} /></label>
          <button type="button" className="text-link now-link" onClick={() => setStartAt(localInputValue(new Date(Date.now() - 5_000)))}>Começar agora</button>
          <label>Encerramento <input className="datetime-input" type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} /></label>
          <div className="rule-summary"><span>◷</span><p>Lance aceito nos dois minutos finais estende o encerramento para dois minutos após o lance.</p></div>
          <button className="button button-primary full-button" disabled={!selected || creating}>{creating ? "Publicando…" : "Publicar lote"} <span>↗</span></button>
        </form>
      </div>
    </>
  );
}

function WalletPage({ data, refresh, notify }) {
  const isBidder = data.me.role === "bidder";
  const [amount, setAmount] = useState("100,00");
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const movements = data.movements || [];

  const deposit = async (event) => {
    event.preventDefault();
    const cents = parseMoney(amount);
    if (!cents) { setError("Informe um valor válido."); return; }
    setWorking(true);
    setError("");
    try {
      await api("/wallet/deposit", { method: "POST", body: JSON.stringify({ amount_cents: cents }) });
      await refresh();
      notify("Depósito simulado adicionado à carteira.");
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  };

  return (
    <>
      <section className="page-intro">
        <div><span className="eyebrow">{isBidder ? "SUA CARTEIRA" : "REPASSE DO LEILOEIRO"}</span><h1>{isBidder ? "Saldo para disputar" : "Seu financeiro"}</h1><p>{isBidder ? "Os valores comprometidos ficam reservados enquanto você lidera um lote." : "Os valores dos arremates são creditados quando o lote é liquidado."}</p></div>
        <span className="wallet-page-mark">◈</span>
      </section>
      <section className="balance-grid">
        <div className="balance-card balance-total"><span>Saldo total</span><strong>{money(data.wallet?.total_cents)}</strong><small>Atualizado a cada operação</small></div>
        <div className="balance-card"><span>Comprometido</span><strong>{money(data.wallet?.committed_cents)}</strong><small>Reservado nos lotes que você lidera</small></div>
        <div className="balance-card balance-available"><span>Disponível</span><strong>{money(data.wallet?.available_cents)}</strong><small>Pronto para novos lances</small></div>
      </section>
      {isBidder && (
        <section className="deposit-card">
          <div><span className="eyebrow">RECARGA DE TESTE</span><h2>Adicionar saldo simulado</h2><p>Este depósito é fictício e fica registrado no extrato.</p></div>
          <form className="deposit-form" onSubmit={deposit}>
            <label className="input-money"><i>R$</i><input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" /></label>
            <button type="submit" className="button button-primary" disabled={working}>{working ? "Adicionando…" : "Depositar"}</button>
          </form>
          <div className="quick-amounts"><span>Sugestões:</span>{["50,00", "100,00", "250,00"].map((v) => <button key={v} onClick={() => setAmount(v)}>R$ {v}</button>)}</div>
          {error && <div className="notice error">{error}</div>}
        </section>
      )}
      <section className="table-card">
        <div className="table-heading"><div><span className="eyebrow muted">MOVIMENTAÇÕES</span><h2>Extrato da carteira</h2></div><span>{movements.length} registros</span></div>
        {movements.length ? (
          <div className="movement-list">
            {movements.map((movement) => (
              <div className="movement-row" key={movement.id}>
                <span className={"movement-icon " + movement.kind}>{movement.kind === "deposit" ? "↓" : movement.kind === "seller_credit" ? "↑" : "↗"}</span>
                <span className="movement-description"><strong>{movement.note}</strong><small>{dateTime(movement.created_at)}</small></span>
                <strong className={movement.kind === "auction_payment" ? "negative" : "positive"}>{movement.kind === "auction_payment" ? "−" : "+"}{money(movement.amount_cents)}</strong>
              </div>
            ))}
          </div>
        ) : <EmptyState icon="◈" title="Sem movimentações" detail="Seu extrato será atualizado quando houver depósitos ou arremates." />}
      </section>
    </>
  );
}

function ActivityPage({ data, openReceipt, onOpen }) {
  const activity = data.activity || [];
  return (
    <>
      <section className="page-intro">
        <div><span className="eyebrow">SEU HISTÓRICO</span><h1>Meus arremates</h1><p>Lotes em que você participou, seu maior lance e comprovantes disponíveis.</p></div>
        <span className="activity-mark">↗</span>
      </section>
      {activity.length ? (
        <div className="activity-list">
          {activity.map((lot) => (
            <article key={lot.id} className="activity-card">
              <div className="activity-cover"><BookVisual title={lot.title} cover={lot.cover_url} /></div>
              <div className="activity-content">
                <div className="activity-top"><StatusPill status={lot.status} />{lot.is_winner && <span className="winner-pill">✓ Arrematado por você</span>}</div>
                <h3>{lot.title}</h3><p>{lot.authors || "Livro de coleção"}</p>
                <div className="activity-facts"><span>Seu maior lance <strong>{money(lot.my_max_bid_cents)}</strong></span><span>{lot.status === "closed" ? "Resultado" : "Lance atual"} <strong>{money(lot.winning_cents || lot.current_cents)}</strong></span></div>
              </div>
              <div className="activity-actions">
                <button className="button button-secondary" onClick={() => onOpen(lot.id)}>Ver lote</button>
                {lot.receipt_url && <button className="button button-primary" onClick={() => openReceipt(lot.receipt_url)}>Comprovante ↗</button>}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState icon="↗" title="Sua próxima história começa com um lance" detail="Quando você participar de um leilão, ele aparecerá aqui." />
      )}
    </>
  );
}


function AuditPage({ lotId, navigate }) {
  const [audit, setAudit] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    api("/audit/" + encodeURIComponent(lotId))
      .then((data) => { if (alive) setAudit(data); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [lotId]);

  return (
    <main className="public-page">
      <header className="public-header"><button onClick={() => navigate("/")}><Logo /></button><span className="public-label">REGISTRO PÚBLICO</span><button className="text-link" onClick={() => navigate("/")}>Voltar ao leilão ↗</button></header>
      {error ? <EmptyState icon="!" title="Não foi possível carregar o registro" detail={error} /> : !audit ? <LoadingScreen /> : (
        <>
          <section className="public-hero">
            <span className="eyebrow">AUDITORIA DO LOTE</span>
            <h1>{audit.lot.title}</h1>
            <p>{audit.lot.authors || "Item de coleção"} · {statusLabel(audit.lot.status)}</p>
            <div className={"integrity-status " + (audit.integrity.valid ? "verified" : "tampered")}>
              <span>{audit.integrity.valid ? "✓" : "!"}</span>
              <div><strong>{audit.integrity.valid ? "Histórico íntegro" : "Divergência detectada"}</strong><small>{audit.integrity.valid ? "Eventos e checkpoint assinado conferem." : "A verificação encontrou diferenças nos dados persistidos."}</small></div>
              <em>{audit.integrity.checked_events} eventos conferidos</em>
            </div>
          </section>
          <section className="audit-proof-card">
            <div><span className="eyebrow muted">CHECKPOINT DO LOTE</span><h2>Hash final</h2><p>O encadeamento é conferido com uma assinatura mantida fora das tabelas de eventos.</p></div>
            <code>{audit.integrity.head_hash}</code>
          </section>
          {audit.integrity.problems.length > 0 && (
            <section className="notice error audit-errors"><strong>Problemas encontrados</strong><ul>{audit.integrity.problems.map((problem) => <li key={problem}>{problem}</li>)}</ul></section>
          )}
          <section className="audit-timeline">
            <div className="table-heading"><div><span className="eyebrow muted">HISTÓRICO IMUTÁVEL</span><h2>Eventos do lote</h2></div><span>Sequência · hash do evento</span></div>
            {audit.events.slice().reverse().map((event) => (
              <article className="audit-event" key={event.sequence}>
                <div className="event-marker">{event.type === "bid_placed" ? "↗" : event.type === "lot_closed" ? "✓" : "·"}</div>
                <div className="event-main"><div className="event-title"><strong>{EVENT_LABELS[event.type] || event.type}</strong><span>#{String(event.sequence).padStart(3, "0")}</span></div>
                  <p>{event.type === "bid_placed" ? event.actor + " ofereceu " + money(event.amount_cents) : event.type === "lot_created" ? "Lance inicial " + money(event.payload.initial_cents) + " · incremento mínimo " + money(event.payload.increment_cents) : event.type === "lot_closed" ? "Vencedor " + (event.payload.winner_alias || "Licitante") + " · " + money(event.amount_cents) : event.type === "lot_closed_without_bids" ? "Encerrado sem vencedor." : event.type === "lot_cancelled" ? "Cancelamento registrado." : "Registro operacional do leilão."}</p>
                  <small>{dateTime(event.created_at)}{event.payload.end_extended_to ? " · novo fim " + dateTime(event.payload.end_extended_to) : ""}</small>
                </div>
                <code className="event-hash">{shortHash(event.hash)}</code>
              </article>
            ))}
          </section>
          <footer className="public-footer"><Logo compact /><span>Dados pessoais dos participantes não são exibidos neste registro.</span><button onClick={() => navigate("/")}>Ir para a vitrine ↗</button></footer>
        </>
      )}
    </main>
  );
}

function ReceiptPage({ token, navigate }) {
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    api("/receipt/" + encodeURIComponent(token))
      .then((data) => { if (alive) setReceipt(data); })
      .catch((e) => { if (alive) setError(e.message); });
    return () => { alive = false; };
  }, [token]);

  const share = async () => {
    const link = window.location.href;
    try {
      if (navigator.share) await navigator.share({ title: "Comprovante de arremate", url: link });
      else {
        await navigator.clipboard.writeText(link);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 2500);
      }
    } catch {
      setError("Não foi possível compartilhar o link neste navegador.");
    }
  };

  return (
    <main className="public-page receipt-page">
      <header className="public-header"><button onClick={() => navigate("/")}><Logo /></button><span className="public-label">COMPROVANTE DIGITAL</span><button className="text-link" onClick={() => navigate("/")}>Vitrine ↗</button></header>
      {error ? <EmptyState icon="!" title="Comprovante indisponível" detail={error} /> : !receipt ? <LoadingScreen /> : (
        <section className="receipt-card">
          <div className="receipt-top"><span className="receipt-seal">✓</span><span className="eyebrow">RESULTADO DO PREGÃO</span><h1>{receipt.integrity_valid ? "Arremate confirmado" : "Integridade pendente"}</h1><p>{receipt.integrity_valid ? "Este comprovante corresponde ao registro auditável do lote." : "O registro do lote apresenta uma divergência de integridade."}</p></div>
          <div className="receipt-item"><BookVisual title={receipt.title} /><div><span className="eyebrow muted">ITEM ARREMATADO</span><h2>{receipt.title}</h2><p>{receipt.authors || "Item de coleção"}</p>{receipt.source_url && <a href={receipt.source_url} target="_blank" rel="noreferrer">Fonte do item ↗</a>}</div></div>
          <div className="receipt-price"><span>VALOR DO ARREMATE</span><strong>{money(receipt.winning_cents)}</strong></div>
          <div className="receipt-facts"><div><small>Arrematante</small><strong>{receipt.winner_alias}</strong></div><div><small>Leiloeiro</small><strong>{receipt.seller}</strong></div><div><small>Encerrado em</small><strong>{dateTime(receipt.closed_at)}</strong></div><div><small>Eventos conferidos</small><strong>{receipt.event_count}</strong></div></div>
          <div className={"receipt-integrity " + (receipt.integrity_valid ? "good" : "bad")}><span>{receipt.integrity_valid ? "✓" : "!"}</span><div><strong>{receipt.integrity_valid ? "Trilha conferida" : "Trilha com divergência"}</strong><code>{shortHash(receipt.head_hash)}</code></div><button onClick={() => navigate(receipt.audit_url)}>Ver auditoria ↗</button></div>
          <div className="receipt-actions"><button className="button button-secondary" onClick={() => window.print()}>Imprimir comprovante</button><button className="button button-primary" onClick={share}>{copied ? "Link copiado ✓" : "Compartilhar ↗"}</button></div>
          <p className="receipt-privacy">A identidade aparece por um apelido público do lote. Dados pessoais não são expostos.</p>
        </section>
      )}
    </main>
  );
}

export default App;
