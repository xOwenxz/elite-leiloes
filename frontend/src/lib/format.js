import { STATUS_LABELS } from "../constants.js";

const LOCALE = "pt-BR";
const EMPTY_VALUE = "—";
const SHORT_HASH_LENGTH = 18;

const currencyFormatter = new Intl.NumberFormat(LOCALE, { style: "currency", currency: "BRL" });
const dateTimeFormatter = new Intl.DateTimeFormat(LOCALE, { dateStyle: "short", timeStyle: "short" });

/** Formata um valor em centavos como moeda brasileira (ex.: 1500 → "R$ 15,00"). */
export function money(cents = 0) {
  return currencyFormatter.format((Number(cents) || 0) / 100);
}

/**
 * Converte o texto digitado pelo usuário em centavos.
 * Aceita "1.234,56" (formato brasileiro) e "1234.56". Retorna 0 para valores inválidos ou não positivos.
 */
export function parseMoney(value) {
  let normalized = String(value ?? "").trim();
  if (normalized.includes(",")) normalized = normalized.replace(/\./g, "").replace(",", ".");
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount <= 0) return 0;
  return Math.round(amount * 100);
}

/** Converte uma data para o formato aceito por `<input type="datetime-local">`, no fuso local. */
export function localInputValue(date) {
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return shifted.toISOString().slice(0, 16);
}

/** Formata data e hora curtas em pt-BR; devolve "—" para valores ausentes ou inválidos. */
export function dateTime(value) {
  if (!value) return EMPTY_VALUE;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return EMPTY_VALUE;
  return dateTimeFormatter.format(date);
}

/** Abrevia um hash para exibição (primeiros caracteres seguidos de reticências). */
export function shortHash(value = "") {
  return value ? value.slice(0, SHORT_HASH_LENGTH) + "…" : EMPTY_VALUE;
}

/** Completa um número com zeros à esquerda (ex.: padNumber(7, 3) → "007"). */
export function padNumber(value, length = 2) {
  return String(value).padStart(length, "0");
}

/** Rótulo em português do status de um lote; devolve o próprio código se for desconhecido. */
export function statusLabel(status) {
  return STATUS_LABELS[status] || status;
}
