import { useEffect, useState } from "react";
import { api } from "../lib/apiClient.js";

/**
 * Busca um recurso da API uma vez por caminho, ignorando respostas que chegarem
 * depois que o componente for desmontado ou o caminho mudar.
 *
 * @param {string} path Caminho do recurso (ex.: "/audit/123").
 * @returns {{ data: any, error: string, setError: (message: string) => void }}
 */
export function useApiResource(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    api(path)
      .then((result) => {
        if (alive) setData(result);
      })
      .catch((requestError) => {
        if (alive) setError(requestError.message);
      });
    return () => {
      alive = false;
    };
  }, [path]);

  return { data, error, setError };
}
