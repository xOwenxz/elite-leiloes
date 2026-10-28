import { useNow } from "../hooks/useNow.js";
import { padNumber } from "../lib/format.js";

/** Segundos restantes até `endAt`, nunca negativos. */
function secondsUntil(endAt, now) {
  return Math.max(0, Math.floor((new Date(endAt).getTime() - now) / 1000));
}

/**
 * Formata o tempo restante como "MM:SS" ou "HH:MM:SS" (quando há horas)
 * e mostra "Finalizando" quando o prazo já se esgotou.
 */
function formatRemaining(totalSeconds) {
  if (totalSeconds === 0) return "Finalizando";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const minutesAndSeconds = padNumber(minutes) + ":" + padNumber(seconds);
  return hours > 0 ? padNumber(hours) + ":" + minutesAndSeconds : minutesAndSeconds;
}

/**
 * Contagem regressiva até o encerramento do lote, atualizada a cada segundo.
 * `compact` é usado nos cards; a versão grande aparece no modal do lote.
 */
export default function Countdown({ endAt, compact = false }) {
  const now = useNow();
  const label = formatRemaining(secondsUntil(endAt, now));

  if (compact) {
    return (
      <span className="countdown compact-countdown">
        <span className="clock-icon">◷</span>
        {label}
      </span>
    );
  }

  return (
    <div className="countdown-large">
      <span>ENCERRA EM</span>
      <strong>{label}</strong>
    </div>
  );
}
