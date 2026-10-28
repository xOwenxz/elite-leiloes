/** Marca da Elite Leilões. A versão compacta exibe apenas o monograma. */
export default function Logo({ compact = false }) {
  return (
    <div className={"brand-lockup" + (compact ? " compact" : "")}>
      <span className="brand-mark">V</span>
      {!compact && <span className="brand-name">elite<span>leilões</span></span>}
    </div>
  );
}
