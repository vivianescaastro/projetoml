# LeilãoIA — cadeia de 10 agentes para decidir compra em leilão

App web (FastAPI + front-end estático) que orquestra os agentes do fluxo planejado:

| Agente | Papel |
|---|---|
| 1 Objetivo da compra | perfil: objetivo, orçamento, risco, margem-alvo |
| 2 Banco de dados | lê/valida a planilha Excel e ranqueia lotes pelo desconto sobre o mercado |
| 2 → Veículos / Bens Diversos / Imóvel | ramo de categoria (do lote, do perfil ou detectado no edital); os outros dois são desviados |
| 3 Tipo de leilão | decide Judicial / Receita Federal / Extrajudicial (planilha × texto do edital; alerta divergência) |
| 4 / 5 / 6 | especialistas: lê o edital PDF com checklist e fundamento legal do tipo escolhido (os outros ramos são desviados) |
| 7 Análise de edital | consolida ficha + riscos, cruza com a base |
| 8 Prazos | cronograma de praças, pagamento, retirada, armazenamento |
| 9 Custos | lance + comissão + armazenamento + depósito/caução + taxas + ITBI/registro + débitos…; a quem e como pagar; lance máximo p/ a margem-alvo |
| 9 → A quem pagar / Como pagar | beneficiários, valores, prazo e forma de pagamento |
| 10 Dossiê | veredito COMPRAR / ATENÇÃO / NÃO COMPRAR + PDF |

## Rodar localmente
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...   # opcional: leitura de PDF por Claude (inclui PDF escaneado)
uvicorn leilaoia.main:app --reload
```
Sem a chave, usa um extrator por regras (o dossiê avisa para revisar os valores).

## Nuvem
`Dockerfile` e `render.yaml` prontos (Render, Fly, Cloud Run…). Defina `ANTHROPIC_API_KEY` (e opcionalmente `CLAUDE_MODEL`).

## Planilha
Baixe o modelo em `/api/base/modelo`. Obrigatórios: Descrição e Lance mínimo. Sinônimos de colunas são aceitos; linhas inválidas viram avisos.

## Testes
`pytest` (editais de exemplo fictícios em `leilaoia/samples`; regenere com `python scripts/make_samples.py`).

> Análise automatizada de apoio; não substitui a leitura do edital nem assessoria jurídica. Valores "estimados" são premissas ajustáveis.
