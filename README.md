# Lírio · moda feminina

Loja virtual *mobile-first* de moda feminina, com área da cliente (vitrine, sacola, checkout com Pix,
conta) e painel administrativo (produtos, fotos, estoque por variação, categorias e pedidos).

- Requisitos do produto: [REQUISITOS.md](REQUISITOS.md)
- Decisões tomadas na implementação: [DECISOES.md](DECISOES.md)
- O nome "Lírio" é provisório. Marca, cores, textos, frete e regras ficam em
  [config_loja.py](config_loja.py); os logos em `static/img/marca/`.

**Fase 1 (MVP) entregue:** catálogo, busca e filtros, produto, sacola (visitante e cliente), checkout
Entrega → Pagamento → Revisão com Pix (Mercado Pago ou simulado), login com e-mail/senha e Google,
recuperação de senha, meus pedidos, favoritos e o painel `/admin`.

## Stack

Flask 3 · SQLAlchemy 2 + Flask-Migrate · PostgreSQL · Flask-Login + Authlib (Google) + argon2 ·
Flask-WTF (validação e CSRF) · Tailwind CSS v4 (compilado) · Mercado Pago (API REST) · pytest, ruff e mypy.

## Requisitos para rodar

- Python 3.12 ou mais novo
- PostgreSQL 14 ou mais novo
- Node.js 20+ — **só** para recompilar o CSS quando mudar templates ou classes (o `static/css/app.css`
  compilado já está no repositório)

## Rodar localmente

```bash
# 1. Ambiente Python
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. Bancos (o de teste é apagado e recriado pelos testes)
createdb lojalirio
createdb lojalirio_test

# 3. Variáveis de ambiente
cp .env.example .env
# edite o .env: no mínimo SECRET_KEY e, se quiser, ADMIN_SENHA

# 4. Tabelas e dados iniciais
flask db upgrade
flask seed

# 5. Servidor
flask run --debug        # http://127.0.0.1:5000
```

O `flask seed` cria 2 categorias, 8 produtos com cores, tamanhos e estoque, o banner da home,
o cupom `BEMVINDA10` (10% acima de R$ 100) e a usuária admin (`ADMIN_EMAIL`). Sem `ADMIN_SENHA` no
`.env`, ele gera uma senha e mostra no terminal. Pode rodar de novo sem duplicar nada.

O painel fica em `/admin` (entre com a conta admin).

### CSS (Tailwind)

```bash
npm install
npm run css          # compila static/css/entrada.css -> static/css/app.css
npm run css:watch    # recompila a cada mudança, durante o desenvolvimento
```

Os tokens de cor (rosé, grafite, creme, taupe, linha, imagem) estão no `@theme` de `entrada.css`, mas
quem manda é `config_loja.CORES`: o `base.html` injeta essas cores em tempo de execução, então trocar
a paleta não exige recompilar.

## Qualidade

```bash
ruff check .            # lint
ruff format --check .   # formatação
mypy                    # tipos
pytest                  # 87 testes: valores, frete, Pix, cupom, estoque, webhook, admin, segurança, fotos e fluxo completo
```

## Variáveis de ambiente

Todas estão documentadas em [.env.example](.env.example). As principais:

| Variável | Para quê |
|---|---|
| `AMBIENTE` | `desenvolvimento` ou `producao` (cookies seguros, HSTS e Mercado Pago obrigatório) |
| `SECRET_KEY` | sessão, CSRF e links de senha. Obrigatória em produção |
| `DATABASE_URL` / `DATABASE_URL_TESTE` | PostgreSQL da loja e dos testes |
| `URL_BASE` | endereço público (webhook, sitemap, Open Graph) |
| `MP_ACCESS_TOKEN` / `MP_WEBHOOK_SECRET` | Mercado Pago. Sem token, o Pix é simulado (só fora de produção) |
| `PIX_EXPIRACAO_MINUTOS` | tempo para pagar antes de o pedido ser cancelado e o estoque voltar (padrão 30) |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` | fotos no Supabase Storage; sem elas, ficam em `static/uploads/` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | login com Google; sem elas o botão não aparece |
| `SMTP_*` / `EMAIL_REMETENTE` | e-mail de recuperação de senha; sem SMTP o link vai para o log |
| `RATELIMIT_STORAGE_URI` | limite de tentativas de login; use Redis com vários workers |
| `ADMIN_EMAIL` / `ADMIN_SENHA` | conta admin criada pelo seed |

## Pagamento Pix

**Sem credenciais (desenvolvimento):** o gateway simulado gera um QR e um copia-e-cola de teste (que
nenhum banco aceita). Na tela do pedido aparece "Simular pagamento aprovado": ele aprova a cobrança no
simulador e envia o webhook assinado para `/pagamentos/webhook`, o mesmo caminho do Mercado Pago.
O pedido vira **Pago** só por esse webhook (RN08); o admin não tem essa opção.

**Mercado Pago sandbox:**

1. Crie uma aplicação em <https://www.mercadopago.com.br/developers/panel/app> e copie o
   *Access Token* de teste (`TEST-…`) para `MP_ACCESS_TOKEN`.
2. O webhook precisa de um endereço público HTTPS. Localmente, use um túnel
   (`cloudflared tunnel --url http://127.0.0.1:5000` ou `ngrok http 5000`) e coloque a URL em `URL_BASE`.
3. Em *Webhooks*, cadastre `{URL_BASE}/pagamentos/webhook` com o evento **Pagamentos** e copie a
   *assinatura secreta* para `MP_WEBHOOK_SECRET`.
4. Faça uma compra e pague o Pix com a conta de teste compradora. O Mercado Pago chama o webhook, a loja
   confere a assinatura, consulta o pagamento na API (status, número do pedido e valor) e marca o pedido
   como **Pago**, que aparece em `/admin/pedidos`.

## Deploy no Render + Supabase

O banco e as fotos ficam no Supabase; o app roda no Render (região **Virginia**, junto do banco).

1. **Supabase**: projeto em us-east-1 com um papel próprio para a loja e o schema `loja` (ver
   DECISOES.md), e o bucket público `loja` no Storage. A `DATABASE_URL` usa o *pooler de sessão*:
   `postgresql://<papel>.<ref>:<senha>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require`.
2. **Render** → New → Web Service, apontando para o repositório:
   - Build: `pip install -r requirements.txt`
   - Start: `flask db upgrade && gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
   - Python: o `.python-version` fixa a 3.13.5.
3. **Variáveis no Render**: `DATABASE_URL`, `SECRET_KEY`, `URL_BASE` (o endereço `https://…onrender.com`),
   `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `AMBIENTE`, `ADMIN_EMAIL`, `ADMIN_SENHA` e, para cobrar de
   verdade, `MP_ACCESS_TOKEN` e `MP_WEBHOOK_SECRET`.
   - Com `AMBIENTE=producao`, o checkout exige o Mercado Pago (o Pix simulado é recusado).
   - Com `AMBIENTE=desenvolvimento`, o Pix simulado e o botão "Simular pagamento" ficam ligados:
     **não divulgue o endereço** nesse modo, porque qualquer pessoa poderia "pagar" um pedido.
4. **Dados iniciais**, uma vez, do seu computador, com as mesmas variáveis do Render:
   `DATABASE_URL=... SUPABASE_URL=... SUPABASE_SECRET_KEY=... ADMIN_SENHA=... flask seed`
5. **Expiração dos Pix**: o plano gratuito do Render não tem cron. A lista de pedidos do admin já expira
   os vencidos ao abrir; para rodar sozinho, crie um *Cron Job* no Render (pago) com `flask pedidos expirar`
   a cada 5 minutos.
6. **Mercado Pago**: cadastre o webhook `{URL_BASE}/pagamentos/webhook`.

## Deploy (VPS)

1. Servidor com Python 3.12+, PostgreSQL e um proxy com HTTPS (Caddy ou Nginx + Let's Encrypt).
2. Clone o repositório, crie o `.venv` e rode `pip install -r requirements.txt`.
3. Crie o `.env` de produção: `AMBIENTE=producao`, `SECRET_KEY` forte, `DATABASE_URL`, `URL_BASE` com
   https, Mercado Pago de produção, SMTP e, com mais de um worker, `RATELIMIT_STORAGE_URI=redis://…`.
4. `flask db upgrade` e, só na primeira vez, `flask seed` (com `ADMIN_SENHA` definida).
5. Rode com Gunicorn atrás do proxy:
   ```bash
   gunicorn app:app --workers 3 --bind 127.0.0.1:8000
   ```
   e aponte o proxy para `127.0.0.1:8000`. Sirva `/static` direto pelo proxy, se preferir.
6. Sem Supabase Storage, `static/uploads/` guarda as fotos enviadas pelo admin: mantenha essa pasta
   em disco persistente e no backup.
7. Agende a expiração dos Pix vencidos (devolve o estoque) a cada 5 minutos:
   ```cron
   */5 * * * * cd /caminho/lojaLirio && .venv/bin/flask pedidos expirar
   ```
8. No Mercado Pago de produção, cadastre o webhook `{URL_BASE}/pagamentos/webhook`.

## Estrutura

```
servidor.py        fábrica da aplicação (create_app) e comandos flask seed / flask pedidos expirar
app.py             entrada WSGI (gunicorn app:app)
config.py          configuração lida do .env
config_loja.py     marca, cores, textos, frete, Pix, parcelas, tamanhos, guia de medidas
modelos/           tabelas (SQLAlchemy)
servicos/          regras de negócio: dinheiro, CEP, frete, totais, cupons, estoque, sacola, pedidos, pagamentos
formularios/       validação de entrada (WTForms)
blueprints/        rotas: loja, sacola, checkout, conta, pagamentos (webhook), admin
templates/         páginas Jinja; componentes/ tem o design system (botão, campo, chip, card, preço…)
static/            CSS compilado, JS, fontes e logos
migrations/        migrations do banco (Alembic)
tests/             pytest
```
