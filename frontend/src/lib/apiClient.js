const API_PREFIX = "/api";
const NETWORK_ERROR_MESSAGE = "Não foi possível conectar ao servidor. Confira se o back-end está ativo.";
const DEFAULT_ERROR_MESSAGE = "A operação não foi concluída.";
const INVALID_DATA_MESSAGE = "Confira os dados e tente novamente.";

/**
 * Faz uma requisição ao back-end e devolve o corpo JSON da resposta.
 * Aceita caminhos com ou sem o prefixo "/api" e sempre envia os cookies de sessão.
 *
 * @param {string} path Caminho do recurso, ex.: "/lots" ou "/api/lots".
 * @param {RequestInit} [options] Opções repassadas ao fetch.
 * @returns {Promise<any>} Corpo JSON da resposta, ou null quando não houver JSON.
 * @throws {Error} Com mensagem amigável em português em caso de falha de rede ou HTTP.
 */
export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const response = await sendRequest(resolveApiUrl(path), {
    ...options,
    headers,
    credentials: "same-origin",
  });

  const payload = await readJsonPayload(response);
  if (!response.ok) throw new Error(errorMessageFrom(payload));
  return payload;
}

/**
 * Atalho para POST com corpo JSON. Sem `body`, envia a requisição sem corpo.
 *
 * @param {string} path Caminho do recurso.
 * @param {object} [body] Objeto serializado como JSON.
 */
export function postJson(path, body) {
  const options = { method: "POST" };
  if (body !== undefined) options.body = JSON.stringify(body);
  return api(path, options);
}

function resolveApiUrl(path) {
  return path.startsWith(API_PREFIX) ? path : API_PREFIX + path;
}

/** Executa o fetch convertendo falhas de rede em uma mensagem compreensível. */
async function sendRequest(url, init) {
  try {
    return await fetch(url, init);
  } catch {
    throw new Error(NETWORK_ERROR_MESSAGE);
  }
}

async function readJsonPayload(response) {
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? await response.json() : null;
}

/** O back-end devolve `detail` como texto ou, em erros de validação, como lista de objetos. */
function errorMessageFrom(payload) {
  const message = payload?.detail || DEFAULT_ERROR_MESSAGE;
  return typeof message === "string" ? message : INVALID_DATA_MESSAGE;
}
