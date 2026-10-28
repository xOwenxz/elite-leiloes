import { HOME_PATH } from "../lib/routes.js";
import Logo from "./Logo.jsx";

/**
 * Cabeçalho das páginas públicas (auditoria e comprovante).
 * Tanto a marca quanto o link de retorno levam à vitrine.
 */
export default function PublicHeader({ label, backLabel, navigate }) {
  const goHome = () => navigate(HOME_PATH);
  return (
    <header className="public-header">
      <button onClick={goHome}>
        <Logo />
      </button>
      <span className="public-label">{label}</span>
      <button className="text-link" onClick={goHome}>{backLabel}</button>
    </header>
  );
}
