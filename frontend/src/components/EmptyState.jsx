/** Estado vazio genérico: ícone, título, explicação e uma ação opcional. */
export default function EmptyState({ icon, title, detail, action }) {
  return (
    <div className="empty-state">
      <span className="empty-icon">{icon}</span>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  );
}
