/**
 * Botão de entrada com um perfil de demonstração.
 * `pending` indica que o login deste perfil está em andamento; `disabled` bloqueia todos durante qualquer login.
 */
export default function DemoAccountCard({ account, pending, disabled, onSelect }) {
  return (
    <button className="account-card" onClick={() => onSelect(account)} disabled={disabled}>
      <span className={"avatar avatar-" + account.role}>{account.mark}</span>
      <span className="account-copy">
        <strong>{account.label}</strong>
        <small>{account.name}</small>
        <small className="account-secret">{account.email} · senha: {account.password}</small>
      </span>
      <span className="account-arrow">{pending ? "…" : "↗"}</span>
    </button>
  );
}
