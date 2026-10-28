import { useEffect, useState } from "react";

/** Devolve o horário atual (em ms) atualizado a cada `intervalMs`. */
export function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs]);

  return now;
}
