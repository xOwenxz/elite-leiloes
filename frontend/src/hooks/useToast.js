import { useCallback, useState } from "react";
import { TOAST_DURATION_MS } from "../constants.js";

/**
 * Notificação temporária (toast) exibida no rodapé da tela.
 *
 * @returns {{ toast: {message: string, kind: string}|null, notify: (message: string, kind?: string) => void }}
 */
export function useToast() {
  const [toast, setToast] = useState(null);

  const notify = useCallback((message, kind = "success") => {
    setToast({ message, kind });
    window.setTimeout(() => setToast(null), TOAST_DURATION_MS);
  }, []);

  return { toast, notify };
}
