import { HEADER_TABS, ROLES, TABS } from "../constants.js";
import Logo from "./Logo.jsx";

/**
 * Cabeçalho do painel logado: marca, abas de navegação (que variam por papel)
 * e dados do usuário com o botão de sair.
 */
export default function Header({ user, activeTab, onSelectTab, onSignOut }) {
  const isSeller = user.role === ROLES.seller;
  const tabs = isSeller ? HEADER_TABS.seller : HEADER_TABS.bidder;

  return (
    <header className="app-header">
      <button className="header-logo" onClick={() => onSelectTab(TABS.lots)} aria-label="Início">
        <Logo />
      </button>
      <nav className="main-nav">
        {tabs.map(({ key, label, icon }) => (
          <button
            key={key}
            className={"nav-item" + (activeTab === key ? " selected" : "")}
            onClick={() => onSelectTab(key)}
          >
            <span>{icon}</span>
            {label}
          </button>
        ))}
      </nav>
      <div className="header-user">
        <span className="role-pill">{isSeller ? "LEILOEIRO" : "LICITANTE"}</span>
        <span className="header-avatar">{user.name.slice(0, 1)}</span>
        <span className="header-user-name">{user.name}</span>
        <button className="icon-button logout" title="Sair" onClick={onSignOut}>↪</button>
      </div>
    </header>
  );
}
