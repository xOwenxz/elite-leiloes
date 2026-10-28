/** Notificação flutuante; não renderiza nada quando não há mensagem. */
export default function Toast({ toast }) {
  if (!toast) return null;
  return <div className={"toast " + toast.kind}>{toast.message}</div>;
}
