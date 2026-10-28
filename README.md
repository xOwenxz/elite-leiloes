# Elite Leilões

Aplicação demonstrativa para o desafio Elite Dev da Verzel. O projeto usa React + Vite no front-end, Python + FastAPI no back-end, PostgreSQL no Compose/implantação e SQLite como opção leve para desenvolvimento local. O back-end também serve a versão compilada do front-end em produção.

## Fluxo demonstrável

1. Entre com um dos perfis de exemplo.
2. No perfil de leiloeiro, busque um livro no catálogo Open Library e publique um lote com lance inicial, incremento e horário de encerramento.
3. No perfil de licitante, faça um depósito simulado e dê lances. O sistema reserva o saldo do líder, libera a reserva quando ele é superado e envia atualizações ao vivo por Server-Sent Events.
4. Quando o lote termina, o serviço fecha o lote automaticamente, debita o vencedor, credita o leiloeiro e libera um comprovante compartilhável.
5. Abra a auditoria pública para conferir a sequência de eventos, os hashes e o checkpoint assinado. O apelido público substitui os dados pessoais do licitante.

Para disputar um lote entre duas contas ao mesmo tempo, use uma janela normal e outra janela privada ou outro perfil do navegador. A sessão é isolada por cookie.

## Contas de demonstração

| Perfil | E-mail | Senha |
|---|---|---|
| Leiloeiro | leiloeiro@demo.local | verzel123 |
| Licitante Ana | ana@demo.local | ana123 |
| Licitante Bruno | bruno@demo.local | bruno123 |

O banco cria essas contas, carteiras e um lote ativo com lances na primeira inicialização. O estado permanece no banco local nas próximas inicializações. O dinheiro e os depósitos são fictícios.

## Executar localmente no Windows

Requisitos para desenvolvimento local: Python 3.10 ou superior e Node.js 22.12 ou superior. A execução local usa SQLite por padrão; o Compose sobe PostgreSQL, a opção de banco usada na implantação.

Abra dois terminais na pasta do projeto.

Terminal 1 — back-end:

~~~powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
backend/.venv/Scripts/python -m uvicorn main:app --app-dir backend --reload --port 8000
~~~

Terminal 2 — front-end:

~~~powershell
cd frontend
npm install
npm run dev
~~~

Abra http://localhost:5173. O Vite encaminha /api ao back-end local. A documentação interativa do back-end fica em http://localhost:8000/docs.

O SQLite é criado em backend/data/auction.db; a chave de auditoria local fica em backend/data/audit.secret. Para reiniciar a demonstração do zero, pare os dois processos e remova esses arquivos locais. A chave deve ser preservada junto com o banco para que checkpoints já emitidos continuem verificáveis.

## Executar em um contêiner

Com Docker Compose:

~~~powershell
Copy-Item .env.example .env
docker compose up --build
~~~

Abra http://localhost:8000. O PostgreSQL fica no volume postgres-data; a chave de auditoria fica no volume auction-data. O arquivo .env define usuário, senha e nome do banco. Antes de expor a aplicação, troque a senha padrão e defina AUCTION_AUDIT_SECRET com um valor aleatório forte de pelo menos 32 bytes. Preserve a chave junto com o backup do banco. O Compose usa um processo de aplicação para manter o agendador e o stream SSE simples; PostgreSQL permite bloqueio transacional por lote e carteira.

## Regras implementadas

- Só licitantes autenticados podem dar lances; o leiloeiro não pode disputar seus lotes.
- O primeiro lance deve atingir o inicial; os seguintes devem atingir o lance atual mais o incremento.
- O licitante líder não pode cobrir o próprio lance.
- Lance aceito nos dois minutos finais empurra o encerramento para dois minutos após esse lance.
- Saldo total menos comprometido é igual ao disponível. O lance atual do líder fica reservado em uma transação; quando outro licitante assume a liderança, a reserva anterior é liberada na mesma transação.
- O fechamento automático liquida cada lote uma única vez. Lotes sem lances terminam sem vencedor.
- O back-end usa transações SQL para gravar lances, reservas e liquidações em conjunto. PostgreSQL bloqueia a linha do lote e as carteiras envolvidas; a opção local SQLite serializa as escritas.
- Cada evento tem sequência, hash anterior e hash próprio. O lote mantém a quantidade e o hash final assinados por HMAC com uma chave guardada fora das tabelas de eventos. A auditoria recalcula a cadeia, compara os lances com seus eventos e confere o checkpoint. Isso detecta edição, remoção ou inserção de eventos por alguém que só tenha acesso ao banco. Quem também controla o processo e a chave de assinatura está fora desse modelo de ameaça.
- A interface pública usa apelidos por lote e não mostra e-mail ou ID interno de participantes.

## API externa e resiliência

O catálogo busca livros em https://openlibrary.org/search.json. As respostas ficam em cache local; se a API falhar, o painel usa os itens previamente salvos e uma pequena amostra de demonstração. Os lotes guardam um snapshot do item e não dependem da API para a vitrine, sala, comprovante ou auditoria.

## Estrutura

- frontend/ — React, Vite e interface.
- backend/main.py — API, autenticação, regras do leilão e servidor SSE.
- backend/db.py — esquema SQL, suporte SQLite/PostgreSQL, transações e bloqueios.
- backend/domain.py — eventos encadeados, seed da demonstração e verificação de auditoria.
- backend/crypto.py — senhas, chave HMAC e links de comprovante.
- compose.yaml e Dockerfile — build e execução em contêiner.
