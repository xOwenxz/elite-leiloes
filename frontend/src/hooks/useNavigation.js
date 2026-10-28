import { useCallback, useEffect, useState } from "react";

/**
 * Roteamento mínimo baseado na History API.
 * Mantém o caminho atual em estado e o sincroniza com os botões voltar/avançar do navegador.
 *
 * @returns {{ path: string, navigate: (nextPath: string) => void }}
 */
export function useNavigation() {
  const [path, setPath] = useState(window.location.pathname);

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

  return { path, navigate };
}
