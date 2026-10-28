import BookVisual from "./BookVisual.jsx";

/** Item retornado pela busca no catálogo externo, selecionável para virar um lote. */
export default function CatalogResult({ item, selected, onSelect }) {
  return (
    <button className={"catalog-result" + (selected ? " selected" : "")} onClick={() => onSelect(item)}>
      <span className="mini-cover">
        <BookVisual title={item.title} cover={item.cover_url} />
      </span>
      <span className="catalog-result-copy">
        <strong>{item.title}</strong>
        <small>{item.authors || "Autor não informado"}</small>
        <small>{item.source_label}</small>
      </span>
      <span className="select-mark">{selected ? "✓" : "+"}</span>
    </button>
  );
}
