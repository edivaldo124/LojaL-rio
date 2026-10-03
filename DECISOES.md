# Decisões do projeto

Registro das escolhas feitas onde o `REQUISITOS.md` e o `PROMPT_AGENTE.md` deixavam espaço,
ou onde a troca de stack exigiu adaptação. Cada item diz o que foi decidido e por quê.

## Stack: Flask no lugar de Next.js

A dona do projeto pediu Flask. Equivalências usadas:

| Roteiro (Next.js) | Neste projeto (Flask) | Observação |
|---|---|---|
| Next.js App Router | Flask 3 + blueprints + Jinja2 | páginas renderizadas no servidor; JS só para melhorar a experiência |
| TypeScript | Python 3.13 com anotações de tipo + `mypy` | `ruff` faz o papel do lint |
| Prisma + migrations | SQLAlchemy 2 + Flask-Migrate (Alembic) | pasta `migrations/` |
| Auth.js | Flask-Login + Authlib (Google) + argon2 | senhas com argon2id (RNF04) |
| Zod | WTForms (Flask-WTF) nos formulários; validação explícita no webhook | Flask-WTF também traz o CSRF |
| Tailwind | Tailwind v4 compilado pela CLI (npm só no build) | o CSS final é versionado em `static/css/app.css` |
| `src/config/store.ts` | `config_loja.py` | nome, logo, cores, textos, frete e regras ficam ali |
| Modelo de dados em inglês (`User`, `Order`…) | Classes em português (`Usuario`, `Pedido`…) | mesmo padrão dos outros projetos Flask da dona; os campos seguem o REQUISITOS.md |

Bibliotecas além da stack, com justificativa:

- **Flask-Limiter**: limita tentativas de login e cadastro (força bruta).
- **segno**: gera o QR Code do Pix no modo simulado (o Mercado Pago já devolve o QR pronto).
- **Pillow**: converte as fotos enviadas no admin para WebP e reduz o tamanho (RNF02).
- **requests**: chamadas à API do Mercado Pago (sem o SDK, para manter o código pequeno e testável).
- **@fontsource** (npm): Inter e Playfair Display servidas pela própria loja, sem Google Fonts (LGPD).

## Decisões tomadas com a dona (02/10/2026)

1. **CSS**: Tailwind compilado (segue o roteiro).
2. **Frete na Fase 1**: tabela fixa por região, definida pela UF do CEP. Valores em `config_loja.py`
   (são de exemplo e devem ser revistos pela loja). A API de frete fica para a Fase 2.
3. **Login com Google**: já na Fase 1; o botão só aparece quando `GOOGLE_CLIENT_ID` e
   `GOOGLE_CLIENT_SECRET` estão no `.env`.
4. **Contraste AA (RNF06)**: o rosé `#C97B84` (2,9:1) e o taupe `#8A8380` (3,5:1) reprovam como texto
   pequeno sobre o creme. Texto pequeno usa os tons escuros `rose-texto #A4545F` (4,9:1) e
   `taupe-texto #706966` (5,0:1); logo, ícones, bordas, barras e destaques grandes mantêm as cores originais.
5. **Cupom x Pix (RN06)**: quando o cupom não acumula com o Pix, vale o **maior** dos dois descontos,
   com aviso na revisão do pedido. Se o cupom estiver marcado como acumulável, o Pix incide sobre o
   subtotal já com o cupom.

## Decisões técnicas (sem impacto de produto)

- **UF a partir do CEP**: o frete usa a faixa oficial de CEPs por estado (sem depender do ViaCEP).
  O ViaCEP preenche o endereço no navegador; no servidor, o CEP precisa bater com a UF informada.
- **Sacola do visitante**: guardada no banco e ligada a um cookie assinado (`sacola`). No login,
  os itens do visitante são somados à sacola da cliente.
- **Reserva de estoque (RN02)**: ao confirmar o pedido as variações são travadas com
  `SELECT … FOR UPDATE` e o estoque é baixado na mesma transação. O Pix expira em
  `PIX_EXPIRACAO_MINUTOS` (padrão 30); pedidos vencidos são cancelados e o estoque volta
  (comando `flask pedidos expirar`, também executado ao abrir a lista de pedidos do admin).
  O campo `estoque_devolvido` impede devolver duas vezes.
- **Pago só via webhook (RN08)**: o admin não tem a opção "Pago". O webhook do Mercado Pago tem a
  assinatura `x-signature` conferida e o pagamento é consultado na API antes de marcar o pedido
  (status `approved`, referência e valor iguais).
- **Modo simulado do Pix**: sem `MP_ACCESS_TOKEN`, a loja usa um gateway simulado que gera um
  copia-e-cola e um QR de teste. Fora de produção, a tela do pedido mostra "Simular pagamento",
  que aprova a cobrança no gateway simulado e dispara o mesmo processamento do webhook.
  Em produção (`AMBIENTE=producao`) o modo simulado é recusado.
- **Desconto no pedido**: além de `desconto` (total), o pedido guarda `desconto_cupom`,
  `desconto_pix` e `subtotal`, para a revisão e o admin mostrarem a conta completa.
- **Status "expirado"**: não existe status próprio; o pedido vira `CANCELADO` com o motivo
  "Pagamento expirado".
- **Cupons na Fase 1**: modelo, validação e campo na sacola já funcionam (o roteiro pede testes de
  cupom). O CRUD de cupons no admin fica para a Fase 2; o seed cria `BEMVINDA10`.
- **Cartão e boleto**: aparecem no checkout como "em breve", desabilitados, até a Fase 2.
- **Favoritos**: o coração do produto e a aba Favoritos já funcionam (o modelo está no schema e os
  dois aparecem no protótipo da Fase 1).
- **Login com Google em conta já existente**: o cadastro por e-mail e senha não confirma o e-mail, então
  alguém poderia cadastrar o e-mail de outra pessoa antes dela. Quando o Google (com e-mail verificado)
  é ligado a uma conta que já tinha senha, a senha antiga é apagada e as sessões abertas caem; a dona
  do e-mail cria outra senha por "Esqueci minha senha", se quiser.
- **Destino após o login (`next`)**: só caminhos internos; `//host`, `/\host`, esquemas e caracteres
  de controle voltam para a página padrão.
- **Recuperação de senha**: link com token assinado válido por 1 hora. Sem SMTP configurado, o link
  é escrito no log do servidor (desenvolvimento).
- **Guia de medidas**: tabela em `config_loja.py` com medidas de exemplo, a revisar pela loja.
- **Fotos**: gravadas em `static/uploads/` como WebP (máx. 1600 px). A troca para S3/Cloudinary
  fica isolada em `servicos/armazenamento.py`.
- **Seed**: as fotos dos produtos são ilustrações geradas (silhueta da peça na cor da variação),
  porque não há fotos reais ainda. O admin padrão é `admin@exemplo.com`: domínios reservados como
  `.local` são recusados pelo validador de e-mail do login.
- **Galeria no celular em 4:5**: no protótipo a área da galeria é mais larga que alta (390×340), mas foto
  de roupa é vertical e ficaria cortada pela metade. No desktop a galeria é 3:4.
- **Botão da etapa Pagamento**: o protótipo mostra "Confirmar pedido" na tela de pagamento, mas o
  requisito tem a etapa Revisão depois dela. Ali o botão é "Revisar pedido" e o "Confirmar pedido"
  fica na Revisão.
- **Total do protótipo**: a tela de checkout do Figma mostra R$ 313,21, mas a regra RN03 dá
  R$ 309,80 − 5% (R$ 15,49) + R$ 19,90 = **R$ 314,21**, que é o que a loja calcula.

## Plano da Fase 1 (MVP)

Arquivos e pastas criados:

```
config.py, config_loja.py, extensoes.py, servidor.py, app.py, seed.py
modelos/      usuario, endereco, categoria, produto (+ imagem, variação), favorito,
              sacola (+ item), cupom, pedido (+ item), banner
servicos/     dinheiro, cep, frete, totais, cupons, estoque, sacola, pedidos,
              pagamentos (Mercado Pago + simulado), armazenamento, autorizacao, email, slugs
formularios/  conta, checkout, admin
blueprints/   loja (início, categoria, busca, produto, favoritos), sacola, checkout,
              conta (login, cadastro, Google, senha, pedidos), pagamentos (webhook), admin
templates/    base, componentes/ (button, input, chip, product_card, quantity_stepper,
              radio_option, header, bottom_tab_bar, price_tag), loja/, conta/, admin/
static/       css/entrada.css → css/app.css, js/app.js, fonts/, img/marca/
tests/        regras de negócio (dinheiro, frete, totais, cupom, estoque, webhook),
              proteção do admin e fluxo completo até "Pago"
README.md, .env.example, package.json, pyproject.toml
```

Ordem: base e modelos → design system → vitrine → sacola → conta → checkout e Pix → admin →
testes e verificação visual (390 px e 1440 px) → README.
