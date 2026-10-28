import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/apiClient.js";

/**
 * Carrega o estado inicial da aplicação (/api/bootstrap) e o mantém atualizado
 * via Server-Sent Events (/api/events).
 *
 * `revision` é incrementado a cada evento recebido, permitindo que componentes
 * (ex.: o modal do lote) recarreguem seus próprios dados.
 *
 * @returns {{ data: object|null, loading: boolean, revision: number, error: string, refresh: () => Promise<void> }}
 */
export function useBootstrap() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const next = await api("/bootstrap");
      setData(next);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
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

  return { data, loading, revision, error, refresh };
}
