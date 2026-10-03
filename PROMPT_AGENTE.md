# Prompt para o agente de IA

Copie o texto abaixo e cole no seu agente. Coloque o arquivo `REQUISITOS.md` na raiz do projeto antes de começar.

---

Você é um desenvolvedor full-stack sênior. Vai construir uma **loja virtual de moda feminina** completa, mobile-first, com área da cliente e painel administrativo.

## Fonte da verdade
- Leia **`REQUISITOS.md`** (na raiz do projeto) antes de escrever qualquer código. Ele define telas, regras de negócio, modelo de dados e stack.
- O design de referência está no Figma: https://www.figma.com/design/4DvFD2JyizuZGf6g8QzOyi. Siga a paleta, a tipografia, os espaçamentos e a ordem dos elementos de cada tela (Início, Catálogo, Produto, Sacola, Checkout, Login).
- O nome da loja é **provisório ("Lírio")**. Centralize nome, logo, cores e textos institucionais em um único arquivo de configuração (ex.: `src/config/store.ts`) para que a troca seja feita em um só lugar.

## Stack
Next.js (App Router) + TypeScript + Tailwind CSS + PostgreSQL + Prisma + Auth.js + Mercado Pago. Use Zod para validação. Se precisar de outra biblioteca, justifique antes de instalar.

## Design system
Configure no Tailwind os tokens: `rose #C97B84`, `ink #2B2B2B`, `cream #FAF7F5`, `taupe #8A8380`, `line #E4DDD9`, `placeholder #E8DFDA`. Fontes: Playfair Display (logo/destaques) e Inter (interface). Crie componentes reutilizáveis antes das páginas: Button (primário/contorno), Input, Chip, ProductCard, QuantityStepper, RadioOption, Header, BottomTabBar, PriceTag (com preço riscado e parcelamento).

## Como trabalhar
1. Trabalhe **em fases**, na ordem da seção 9 do `REQUISITOS.md`. Comece pela Fase 1 (MVP).
2. Antes de cada fase, escreva um plano curto (arquivos que vai criar/alterar) e só então implemente.
3. Ao final de cada etapa, rode `lint`, `typecheck` e os testes; corrija os erros antes de seguir.
4. Faça commits pequenos e descritivos, em português.
5. Não invente requisitos. Se algo estiver ambíguo, pergunte ou registre a decisão em `DECISOES.md`.

## Regras importantes
- Preços sempre em **centavos (inteiro)**; formate em BRL só na interface (`R$ 189,90`).
- Estoque por **variação (cor + tamanho)**; reserve ao criar o pedido e devolva se expirar ou for cancelado.
- Pedido só vira "Pago" via **webhook** do gateway, nunca pelo front.
- Pix com 5% de desconto sobre os produtos; cartão até 3x sem juros; "Retirar na loja" com frete grátis.
- Rotas `/admin` protegidas por papel `ADMIN` no servidor (middleware + checagem nas actions/rotas).
- Nunca exponha chaves no front; use `.env` e crie um `.env.example` documentado.
- Valide toda entrada no servidor com Zod.
- Interface 100% em português do Brasil.

## Entregáveis da Fase 1
- Schema Prisma completo + migrations + **seed** com 2 categorias, 8 produtos com variações e um usuário admin.
- Páginas: Início, Categoria/Busca, Produto, Sacola, Checkout (com Pix), Login/Cadastro, Meus pedidos.
- Painel admin: produtos (com upload de fotos e estoque por variação), categorias e pedidos (com mudança de status).
- `README.md` com: requisitos, como rodar localmente, variáveis de ambiente, como rodar o seed e como fazer deploy.

## Critérios de pronto
- Funciona bem em 390px e no desktop.
- Fluxo completo: escolher produto → sacola → checkout → pagamento Pix (sandbox) → pedido aparece no admin como "Pago" após o webhook.
- Sem erros de lint/tipos; testes das regras de negócio (estoque, cupom, desconto do Pix, cálculo do total) passando.

Comece lendo o `REQUISITOS.md` e me apresentando o plano da Fase 1.
