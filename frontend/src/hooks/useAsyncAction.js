import { useCallback, useState } from "react";

/**
 * Padroniza o ciclo de uma ação assíncrona disparada pelo usuário:
 * marca "em andamento", limpa o erro anterior, executa e, se falhar, grava a mensagem do erro.
 *
 * O estado de erro fica no componente (recebido via `setError`) para que várias ações
 * possam compartilhar a mesma mensagem — como a busca e a publicação na criação de lote.
 *
 * @param {(message: string) => void} setError Setter do erro exibido na tela.
 * @returns {[boolean, (action: () => Promise<void>) => Promise<void>]} `[working, run]`
 */
export function useAsyncAction(setError) {
  const [working, setWorking] = useState(false);

  const run = useCallback(
    async (action) => {
      setWorking(true);
      setError("");
      try {
        await action();
      } catch (actionError) {
        setError(actionError.message);
      } finally {
        setWorking(false);
      }
    },
    [setError]
  );

  return [working, run];
}
