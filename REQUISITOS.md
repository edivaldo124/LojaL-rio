# Requisitos — Loja Virtual de Moda Feminina

> Nome provisório: **Lírio · moda feminina** (será trocado pelo nome definitivo).
> Protótipo visual: https://www.figma.com/design/4DvFD2JyizuZGf6g8QzOyi

## 1. Visão geral

Loja virtual *mobile-first* para venda de roupas femininas, com área da cliente (vitrine, sacola, checkout, conta) e painel administrativo para a dona da loja gerenciar produtos, estoque e pedidos.

**Perfis de usuário**

- **Visitante**: navega, busca e adiciona à sacola sem login.
- **Cliente**: tudo do visitante + finaliza compra, acompanha pedidos, salva favoritos e endereços.
- **Administrador(a)**: acessa o painel `/admin` e gerencia a loja.

## 2. Identidade visual

| Token | Valor | Uso |
|---|---|---|
| Rosé | `#C97B84` | destaques, links, aba ativa, símbolo da logo |
| Grafite | `#2B2B2B` | texto principal, botões primários |
| Creme | `#FAF7F5` | fundo das telas |
| Taupe | `#8A8380` | texto secundário, placeholders |
| Linha | `#E4DDD9` | bordas e divisores |
| Imagem | `#E8DFDA` | fundo de imagens carregando |

- Tipografia: **Playfair Display** (logo/títulos de destaque) e **Inter** (interface).
- Bordas arredondadas: 10px (botões/inputs), 12px (cards), 20px (chips).
- Layout base: 390px de largura (mobile); no desktop, grade de 3–4 colunas.

## 3. Requisitos funcionais — Área da cliente

### RF01 · Início
- Cabeçalho com menu, logo e ícone da sacola com contador de itens.
- Campo de busca.
- Banner principal configurável pelo admin (imagem, título, botão com link).
- Atalhos de categorias (Vestidos, Blusas, Saias, Calças, etc. — vindos do banco).
- Seção "Novidades" com os produtos mais recentes.
- Barra de navegação inferior: Início, Buscar, Favoritos, Sacola, Conta.

### RF02 · Catálogo / Categoria / Busca
- Listagem em grade (2 colunas no mobile) com foto, nome e preço.
- Filtros: tamanho, cor, faixa de preço.
- Ordenação: mais recentes, menor preço, maior preço, mais vendidos.
- Contador de resultados ("128 produtos").
- Paginação ou rolagem infinita.

### RF03 · Detalhe do produto
- Galeria de fotos com indicador de posição (swipe no mobile).
- Nome, preço, preço "de" riscado (quando em promoção) e parcelamento (até 3x sem juros).
- Seleção de cor (amostras) e tamanho (PP, P, M, G, GG); tamanhos sem estoque ficam desabilitados.
- Link "Guia de medidas" (modal com tabela).
- Descrição e composição do tecido.
- Botões "Adicionar à sacola" (exige cor + tamanho) e "Favoritar".

### RF04 · Sacola
- Lista de itens com foto, nome, tamanho, cor, preço, controle de quantidade e "Remover".
- Campo de cupom de desconto com validação.
- Resumo: subtotal, frete (cálculo por CEP), desconto e total.
- Sacola persiste para visitante (localStorage/cookie) e é unificada ao fazer login.
- Botão "Finalizar compra" (pede login se necessário).

### RF05 · Checkout
- Etapas: **Entrega → Pagamento → Revisão**.
- Endereço: selecionar salvo ou cadastrar novo (preenchimento automático por CEP via ViaCEP).
- Frete: entrega padrão (cálculo por CEP) ou **retirar na loja** (grátis).
- Pagamento: **Pix** (5% de desconto), **cartão de crédito** (até 3x sem juros), **boleto**.
- Revisão final e "Confirmar pedido".
- Tela de pedido confirmado (QR Code/copia-e-cola no Pix; linha digitável no boleto).

### RF06 · Conta
- Cadastro e login com e-mail/senha e com Google.
- Recuperação de senha por e-mail.
- Meus pedidos (lista + detalhe com status).
- Meus endereços, dados pessoais, favoritos.

## 4. Requisitos funcionais — Painel administrativo (`/admin`)

- **RF07 · Produtos**: CRUD com nome, descrição, categoria, preço, preço promocional, fotos (upload múltiplo, ordenáveis), ativo/inativo.
- **RF08 · Variações e estoque**: estoque por combinação cor + tamanho (SKU); alerta de estoque baixo.
- **RF09 · Categorias**: CRUD com ordem de exibição e imagem.
- **RF10 · Pedidos**: lista com filtros por status; detalhe; atualizar status (Aguardando pagamento → Pago → Em separação → Enviado/Pronto para retirada → Entregue / Cancelado); informar código de rastreio.
- **RF11 · Cupons**: código, tipo (% ou valor fixo), valor mínimo, validade, limite de uso.
- **RF12 · Banner da home**: editar imagem, título e link.
- **RF13 · Dashboard**: vendas do dia/mês, pedidos pendentes, produtos mais vendidos, estoque baixo.

## 5. Regras de negócio

- **RN01**: só é possível comprar variações com estoque > 0.
- **RN02**: o estoque é reservado ao criar o pedido e devolvido se o pagamento expirar ou o pedido for cancelado.
- **RN03**: o Pix aplica 5% de desconto sobre o subtotal dos produtos (não sobre o frete).
- **RN04**: o cartão permite até 3x sem juros (configurável no painel).
- **RN05**: "Retirar na loja" tem frete zero.
- **RN06**: um cupom por pedido; ele não acumula com o desconto do Pix, a menos que configurado.
- **RN07**: preços armazenados em centavos (inteiro) para evitar erro de arredondamento.
- **RN08**: o status do pedido muda para "Pago" somente via webhook confirmado do gateway.

## 6. Modelo de dados (resumo)

- `User` (id, nome, email, senha_hash, telefone, role: CLIENTE | ADMIN)
- `Address` (user_id, cep, rua, número, complemento, bairro, cidade, uf, apelido)
- `Category` (nome, slug, imagem, ordem)
- `Product` (nome, slug, descrição, composição, category_id, preço, preço_promocional, ativo, criado_em)
- `ProductImage` (product_id, url, ordem)
- `ProductVariant` (product_id, cor, cor_hex, tamanho, sku, estoque)
- `Favorite` (user_id, product_id)
- `Cart` / `CartItem` (variant_id, quantidade)
- `Coupon` (código, tipo, valor, mínimo, validade, limite_uso, usos)
- `Order` (user_id, status, endereço (snapshot), tipo_frete, valor_frete, desconto, total, forma_pagamento, id_pagamento_gateway, rastreio)
- `OrderItem` (order_id, variant_id, nome/cor/tamanho/preço — snapshot, quantidade)
- `Banner` (imagem, título, link, ativo)

## 7. Requisitos não funcionais

- **RNF01 · Responsivo**: mobile-first, funcionando bem de 360px a desktop.
- **RNF02 · Desempenho**: imagens otimizadas (WebP, lazy load); LCP < 2,5s em 4G.
- **RNF03 · SEO**: URLs amigáveis (`/produto/vestido-midi-floral`), meta tags, Open Graph, sitemap.
- **RNF04 · Segurança**: senhas com hash (bcrypt/argon2), rotas `/admin` protegidas por papel, validação de entrada no servidor, HTTPS, dados de cartão nunca passam pelo servidor (tokenização do gateway).
- **RNF05 · LGPD**: aviso de cookies, política de privacidade, opção de excluir conta.
- **RNF06 · Acessibilidade**: contraste AA, textos alternativos nas imagens, navegação por teclado.
- **RNF07 · Manutenção**: TypeScript, código organizado por módulos, variáveis de ambiente em `.env`, README com instruções de execução.

## 8. Stack sugerida (ajustável)

- **Front + back**: Next.js (App Router) + TypeScript + Tailwind CSS
- **Banco**: PostgreSQL + Prisma ORM
- **Autenticação**: Auth.js (NextAuth) — credenciais + Google
- **Pagamentos**: Mercado Pago (Pix, cartão, boleto) com webhooks
- **Frete**: Melhor Envio (API) ou tabela fixa por região na primeira versão
- **CEP**: ViaCEP
- **Imagens**: Cloudinary ou armazenamento S3 compatível
- **E-mails**: Resend ou SMTP
- **Deploy**: Vercel ou VPS com Docker

## 9. Entregas por fase (MVP primeiro)

1. **Fase 1 (MVP)**: catálogo, produto, sacola, checkout com Pix, login, painel de produtos/estoque/pedidos.
2. **Fase 2**: cartão e boleto, cupons, cálculo de frete por API, favoritos.
3. **Fase 3**: dashboard com métricas, e-mails transacionais, SEO avançado, melhorias de desempenho.
