## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## Git: sem assinatura do Claude

- Nunca adicione `Co-Authored-By: Claude`, `Claude-Session:`, "🤖 Generated with Claude Code" ou qualquer outra assinatura do Claude em mensagens de commit ou descrições de PR. Os commits ficam só no nome do Edivaldo (edivaldo124).
- Não crie branches com o prefixo `claude/`. Use nomes que descrevam a mudança (ex.: `corrige-login`, `nova-tela-pedidos`).
- Relatórios de auditoria de segurança não vão para o repositório: este repositório é público.
