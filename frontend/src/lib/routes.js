/** Rota da vitrine (página inicial). */
export const HOME_PATH = "/";

/** Prefixo da página pública de auditoria de um lote: /auditoria/:id */
export const AUDIT_PATH_PREFIX = "/auditoria/";

/** Prefixo da página pública de comprovante: /comprovante/:token */
export const RECEIPT_PATH_PREFIX = "/comprovante/";

/** Monta o caminho da auditoria pública de um lote. */
export function auditPath(lotId) {
  return AUDIT_PATH_PREFIX + lotId;
}

/**
 * Extrai o parâmetro (já decodificado) de um caminho que começa com `prefix`.
 * Devolve null quando o caminho não pertence à rota.
 */
export function readPathParam(path, prefix) {
  if (!path.startsWith(prefix)) return null;
  return decodeURIComponent(path.slice(prefix.length));
}
