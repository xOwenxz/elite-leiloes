import { statusLabel } from "../lib/format.js";

/** Etiqueta colorida com o status do lote (ao vivo, agendado, encerrado...). */
export default function StatusPill({ status }) {
  return (
    <span className={"status-pill status-" + status}>
      <span />
      {statusLabel(status)}
    </span>
  );
}
