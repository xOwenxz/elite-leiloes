import { useState } from "react";
import { BOOK_COVER_PALETTES } from "../constants.js";

/** Escolhe uma paleta de forma determinística a partir do título. */
function paletteFor(title) {
  return BOOK_COVER_PALETTES[(title || "").length % BOOK_COVER_PALETTES.length];
}

/**
 * Capa do livro. Usa a imagem do catálogo quando existe e carrega;
 * caso contrário, desenha uma capa ilustrada com o título.
 */
export default function BookVisual({ title, cover }) {
  const [imageFailed, setImageFailed] = useState(false);

  if (cover && !imageFailed) {
    return (
      <img
        className="book-cover-image"
        src={cover}
        alt={"Capa de " + title}
        onError={() => setImageFailed(true)}
      />
    );
  }

  return (
    <div className={"book-cover " + paletteFor(title)}>
      <span className="cover-stamp">ELITE<br />LEILÕES</span>
      <strong>{title}</strong>
      <i />
      <small>EDIÇÃO DE COLEÇÃO</small>
    </div>
  );
}
