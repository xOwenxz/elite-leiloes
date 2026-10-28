/** Tela de carregamento exibida enquanto os dados iniciais chegam. */
export default function LoadingScreen() {
  return (
    <main className="loading-screen">
      <div className="brand-mark">V</div>
      <div className="spinner" />
      <p>Preparando o pregão...</p>
    </main>
  );
}
