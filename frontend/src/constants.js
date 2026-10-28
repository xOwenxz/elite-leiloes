/**
 * Constantes de domínio e de interface compartilhadas entre telas.
 * Os textos aqui são exibidos ao usuário e, por isso, ficam em português.
 */

/** Perfis de demonstração apresentados na tela de entrada (também descritos no README). */
export const DEMO_ACCOUNTS = [
  { label: "Leiloeiro", name: "Leiloeiro Verzel", email: "leiloeiro@demo.local", password: "verzel123", role: "seller", mark: "L" },
  { label: "Licitante Ana", name: "Ana Colecionadora", email: "ana@demo.local", password: "ana123", role: "bidder", mark: "A" },
  { label: "Licitante Bruno", name: "Bruno Colecionador", email: "bruno@demo.local", password: "bruno123", role: "bidder", mark: "B" },
];

/** Papéis de usuário retornados pela API. */
export const ROLES = {
  seller: "seller",
  bidder: "bidder",
};

/** Status possíveis de um lote. */
export const LOT_STATUS = {
  active: "active",
  scheduled: "scheduled",
  closed: "closed",
  cancelled: "cancelled",
};

/** Rótulos dos status de lote. */
export const STATUS_LABELS = {
  active: "Ao vivo",
  scheduled: "Agendado",
  closed: "Encerrado",
  cancelled: "Cancelado",
};

/** Rótulos dos tipos de evento da trilha de auditoria. */
export const EVENT_LABELS = {
  lot_created: "Lote criado",
  lot_started: "Leilão iniciado",
  bid_placed: "Lance aceito",
  lot_closed: "Leilão encerrado",
  lot_closed_without_bids: "Encerrado sem lances",
  lot_cancelled: "Lote cancelado",
};

/** Abas do painel logado. */
export const TABS = {
  lots: "lots",
  create: "create",
  wallet: "wallet",
  activity: "activity",
};

/** Abas do cabeçalho, por papel do usuário. */
export const HEADER_TABS = {
  bidder: [
    { key: TABS.lots, label: "Leilões", icon: "◇" },
    { key: TABS.wallet, label: "Carteira", icon: "◈" },
    { key: TABS.activity, label: "Meus arremates", icon: "↗" },
  ],
  seller: [
    { key: TABS.lots, label: "Meus lotes", icon: "◇" },
    { key: TABS.create, label: "Criar lote", icon: "+" },
    { key: TABS.wallet, label: "Financeiro", icon: "◈" },
  ],
};

/** Valor do filtro que mostra lotes de qualquer status. */
export const ALL_LOTS_FILTER = "all";

/** Filtros da vitrine de lotes. */
export const LOT_FILTERS = [
  { key: LOT_STATUS.active, label: "Ao vivo" },
  { key: LOT_STATUS.scheduled, label: "Agendados" },
  { key: LOT_STATUS.closed, label: "Encerrados" },
  { key: ALL_LOTS_FILTER, label: "Todos" },
];

/** Valores sugeridos para o depósito simulado na carteira. */
export const DEPOSIT_SUGGESTIONS = ["50,00", "100,00", "250,00"];

/** Valor inicial do campo de depósito. */
export const DEFAULT_DEPOSIT_AMOUNT = "100,00";

/** Valores iniciais do formulário de criação de lote. */
export const CREATE_LOT_DEFAULTS = {
  catalogQuery: "Machado de Assis",
  initialBid: "30,00",
  increment: "5,00",
  /** Recuo aplicado ao "começar agora" para o lote já nascer ativo. */
  startOffsetMs: -5_000,
  /** Duração padrão do pregão. */
  durationMs: 30 * 60_000,
};

/** Tamanho mínimo do termo de busca no catálogo externo. */
export const MIN_CATALOG_QUERY_LENGTH = 2;

/** Paletas usadas na capa ilustrada quando o livro não tem imagem. */
export const BOOK_COVER_PALETTES = ["cover-terracotta", "cover-forest", "cover-lilac", "cover-ochre"];

/** Quantidade de lances exibidos na prévia do histórico dentro do modal do lote. */
export const LOT_HISTORY_PREVIEW_SIZE = 6;

/** Tempo de exibição das notificações (toast). */
export const TOAST_DURATION_MS = 4200;

/** Tempo de exibição do aviso "Link copiado". */
export const COPIED_FEEDBACK_MS = 2500;

/** Locale usado em buscas sem diferenciar maiúsculas/minúsculas. */
export const SEARCH_LOCALE = "pt-BR";
