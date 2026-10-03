# Graph Report - lojaLirio  (2026-10-02)

## Corpus Check
- 75 files · ~70,519 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 767 nodes · 1718 edges · 37 communities (31 shown, 6 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 112 edges (avg confidence: 0.94)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2e0194e9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- admin_bp.py
- servicos/sacola.py
- checkout_bp.py
- pagamentos.py
- conta_bp.py
- servidor.py
- Pedido
- FormVazio
- Requisitos — Loja Virtual de Moda Feminina
- cupons.py
- What You Must Do When Invoked
- loja_bp.py
- _pedido_simples
- Writing apps with Prisma Composer
- Writing apps with Prisma Composer
- Writing apps with Prisma Composer
- Writing apps with Prisma Composer
- package.json
- graphify reference: extra exports and benchmark
- Prompt para o agente de IA
- env.py
- graphify reference: query, path, explain
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- CLAUDE.md
- .claude/CLAUDE.md
- extraction-spec.md
- lojalirio

## God Nodes (most connected - your core abstractions)
1. `Pedido` - 37 edges
2. `Produto` - 29 edges
3. `FormVazio` - 28 edges
4. `Variacao` - 26 edges
5. `Usuario` - 25 edges
6. `admin_obrigatorio()` - 21 edges
7. `criar_pedido()` - 20 edges
8. `Endereco` - 19 edges
9. `editar_produto()` - 18 edges
10. `Cupom` - 18 edges

## Surprising Connections (you probably didn't know these)
- `editar_produto()` --uses--> `FormVazio`  [INFERRED]
  blueprints/admin_bp.py → formularios/sacola.py
- `excluir_produto()` --uses--> `FormVazio`  [INFERRED]
  blueprints/admin_bp.py → formularios/sacola.py
- `mover_foto()` --uses--> `FormVazio`  [INFERRED]
  blueprints/admin_bp.py → formularios/sacola.py
- `excluir_foto()` --uses--> `FormVazio`  [INFERRED]
  blueprints/admin_bp.py → formularios/sacola.py
- `excluir_variacao()` --uses--> `FormVazio`  [INFERRED]
  blueprints/admin_bp.py → formularios/sacola.py

## Import Cycles
- None detected.

## Communities (37 total, 6 thin omitted)

### Community 0 - "admin_bp.py"
Cohesion: 0.07
Nodes (76): adicionar_cor(), alt_foto(), _aplicar_form_produto(), categorias(), editar_categoria(), editar_produto(), enviar_fotos(), excluir_categoria() (+68 more)

### Community 1 - "servicos/sacola.py"
Cohesion: 0.06
Nodes (56): DeclarativeBase, Base, Instâncias das extensões, criadas sem app e ligadas em servidor.create_app()., Image, Banner, Modelo, Categoria, Modelo (+48 more)

### Community 2 - "checkout_bp.py"
Cohesion: 0.07
Nodes (48): confirmar(), _endereco_escolhido(), entrega(), _estado(), exigir_login(), inicio(), _ir_para_sacola(), _montar_revisao() (+40 more)

### Community 3 - "pagamentos.py"
Cohesion: 0.08
Nodes (30): PagamentoSimulado, Modelo, Cobranças do gateway simulado (desenvolvimento e testes, sem Mercado Pago)., Protocol, assinar(), _centavos(), CobrancaPix, _conferir_assinatura() (+22 more)

### Community 4 - "conta_bp.py"
Cohesion: 0.08
Nodes (47): _buscar_por_email(), cadastrar(), _destino_seguro(), enderecos(), _entrar(), esqueci_senha(), excluir(), google() (+39 more)

### Community 5 - "servidor.py"
Cohesion: 0.08
Nodes (35): Ponto de entrada WSGI (gunicorn app:app) e do comando `flask`., Config, ConfigTeste, _inteiro(), Configuração da aplicação, lida do ambiente (arquivo .env na raiz)., _texto(), fixture, parametrize (+27 more)

### Community 6 - "Pedido"
Cohesion: 0.09
Nodes (33): ItemPedido, Pedido, Modelo, Cópia do produto no momento da compra (nome, cor, tamanho e preço não mudam…, StatusPedido, devolver(), EstoqueInsuficiente, Exception (+25 more)

### Community 7 - "FormVazio"
Cohesion: 0.12
Nodes (33): aprovar_simulado(), login_required, post, RespostaWerkzeug, Webhook do gateway (único caminho para "Pago", RN08) e o botão de pagamento…, Só fora de produção e sem Mercado Pago: aprova a cobrança no gateway simulado e…, webhook(), adicionar() (+25 more)

### Community 8 - "Requisitos — Loja Virtual de Moda Feminina"
Cohesion: 0.06
Nodes (31): Decisões do projeto, Decisões tomadas com a dona (02/10/2026), Decisões técnicas (sem impacto de produto), Plano da Fase 1 (MVP), Stack: Flask no lugar de Next.js, CSS (Tailwind), Deploy (VPS), Estrutura (+23 more)

### Community 9 - "cupons.py"
Cohesion: 0.12
Nodes (21): Cupom, Modelo, aplicado(), buscar_valido(), calcular_desconto(), CupomInvalido, descricao(), normalizar_codigo() (+13 more)

### Community 10 - "What You Must Do When Invoked"
Cohesion: 0.08
Nodes (24): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Part A - Structural extraction for code files (+16 more)

### Community 11 - "loja_bp.py"
Cohesion: 0.19
Nodes (20): busca(), _catalogo(), categoria(), _com_imagens(), favoritar(), favoritos(), _ids_favoritos(), inicio() (+12 more)

### Community 12 - "_pedido_simples"
Cohesion: 0.14
Nodes (5): _pedido_simples(), Estoque por variação, cupom e ciclo de vida do pedido (RN01, RN02, RN06, RN08)., TestCupom, TestEstoque, TestStatus

### Community 13 - "Writing apps with Prisma Composer"
Cohesion: 0.10
Nodes (19): Anatomy of a service, Builds are yours, Databases, Deploy config, Deploying, Driving deploys from code, Object Storage, Production pitfalls (+11 more)

### Community 14 - "Writing apps with Prisma Composer"
Cohesion: 0.10
Nodes (19): Anatomy of a service, Builds are yours, Databases, Deploy config, Deploying, Driving deploys from code, Object Storage, Production pitfalls (+11 more)

### Community 15 - "Writing apps with Prisma Composer"
Cohesion: 0.10
Nodes (19): Anatomy of a service, Builds are yours, Databases, Deploy config, Deploying, Driving deploys from code, Object Storage, Production pitfalls (+11 more)

### Community 16 - "Writing apps with Prisma Composer"
Cohesion: 0.10
Nodes (19): Anatomy of a service, Builds are yours, Databases, Deploy config, Deploying, Driving deploys from code, Object Storage, Production pitfalls (+11 more)

### Community 17 - "package.json"
Cohesion: 0.11
Nodes (18): @fontsource/playfair-display, @fontsource-variable/inter, description, devDependencies, @fontsource/playfair-display, @fontsource-variable/inter, tailwindcss, @tailwindcss/cli (+10 more)

### Community 18 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 19 - "Prompt para o agente de IA"
Cohesion: 0.22
Nodes (8): Como trabalhar, Critérios de pronto, Design system, Entregáveis da Fase 1, Fonte da verdade, Prompt para o agente de IA, Regras importantes, Stack

### Community 20 - "env.py"
Cohesion: 0.39
Nodes (7): get_engine(), get_engine_url(), get_metadata(), Run migrations in 'offline' mode. This configures the context with just a URL…, Run migrations in 'online' mode. In this scenario we need to create an Engine…, run_migrations_offline(), run_migrations_online()

### Community 21 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 22 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 23 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 24 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

## Knowledge Gaps
- **153 isolated node(s):** `name`, `version`, `description`, `css`, `css:watch` (+148 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Pedido` connect `Pedido` to `admin_bp.py`, `servicos/sacola.py`, `checkout_bp.py`, `pagamentos.py`, `conta_bp.py`, `FormVazio`, `loja_bp.py`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Why does `FormVazio` connect `FormVazio` to `admin_bp.py`, `checkout_bp.py`, `loja_bp.py`, `conta_bp.py`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **Why does `Produto` connect `servicos/sacola.py` to `admin_bp.py`, `pagamentos.py`, `loja_bp.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Are the 14 inferred relationships involving `Pedido` (e.g. with `Usuario` and `devolver()`) actually correct?**
  _`Pedido` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `Produto` (e.g. with `Favorito` and `Categoria`) actually correct?**
  _`Produto` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `FormVazio` (e.g. with `categorias()` and `editar_produto()`) actually correct?**
  _`FormVazio` has 19 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `Variacao` (e.g. with `ItemSacola` and `EstoqueInsuficiente`) actually correct?**
  _`Variacao` has 7 INFERRED edges - model-reasoned connections that need verification._