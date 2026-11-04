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

## Base de lotes (fixa)
O servidor usa **uma planilha fixa**: `leilaoia/data/base_leiloes.xlsx` (ou o caminho em `BASE_XLSX`). Sem ela, usa `base_exemplo.xlsx`.
Para atualizar a base, substitua o arquivo e faça commit/redeploy. Colunas aceitas: ver `leilaoia/excel_db.py` (`COLUNAS`).

## Histórico de análises (planilha + espelho em HTML)
Cada análise recebe um **número de ID sequencial** (`AN-0001`, `AN-0002`…, controlado por `analises/contador.txt`; números apagados não são reutilizados). O ID aparece na tela, no PDF, na planilha e no espelho HTML.

A cada análise o app grava em `analises/`:
- `historico.xlsx` — abas **Analises** (1 linha por edital), **Custos** (com trecho literal e página), **Pontos**, **Valores_edital**, **Prazos**;
- `index.html` — espelho para consulta (filtros + dossiê completo); no app: `/historico/`;
- aba **Objetivo_perguntas** — as 11 perguntas do Agente 1 com as respostas de cada análise;
- `json/` — dossiê completo de cada análise (fonte da verdade; planilha e HTML são regenerados dele com `python -m leilaoia.storage`).

Para enviar ao GitHub automaticamente após cada análise: `AUTO_COMMIT=1` (usa o git/credenciais do ambiente, ex.: Codespaces). Sem isso, faça `git add analises && git commit && git push`.
Pasta alternativa: `DADOS_DIR`. **Atenção:** são dados reais — mantenha o repositório privado e não publique `analises/` no GitHub Pages.

## Fidelidade na leitura do edital
- Cada custo traz o **trecho literal** do edital e a **página**.
- A seção "Valores citados no edital" lista **toda** passagem com R$ ou %, na ordem do PDF, mesmo as não classificadas.
- O total separa: custos do edital · estimativas (não constam no edital) · valores informados por você.

## Onde rodar
- **GitHub Codespaces** (teste pelo tablet): Code → Codespaces → Create; o servidor sobe sozinho na porta 8000 (privada) e o navegador abre a URL encaminhada.
- **Render** (permanente): ver abaixo.
- **Tablet Android como servidor**: instale o Termux (F-Droid) e rode `bash scripts/termux_setup.sh`.

## Nuvem (privado)
Defina `APP_PASSWORD` para exigir login (o navegador pede usuário/senha; o usuário pode ser qualquer um).

### Render em 5 passos
1. render.com → **New → Blueprint** → conecte este repositório e o branch.
2. Ele lê o `render.yaml` e cria o serviço.
3. Em **Environment**, preencha `APP_PASSWORD` e, se quiser leitura por IA, `ANTHROPIC_API_KEY`.
4. Aguarde o build e abra a URL `https://leilaoia-xxxx.onrender.com`.
5. Informe qualquer usuário e a senha definida.

## Nuvem (detalhes)
`Dockerfile` e `render.yaml` prontos (Render, Fly, Cloud Run…). Defina `ANTHROPIC_API_KEY` (e opcionalmente `CLAUDE_MODEL`).

## Planilha
Baixe o modelo em `/api/base/modelo`. Obrigatórios: Descrição e Lance mínimo. Sinônimos de colunas são aceitos; linhas inválidas viram avisos.

## Testes
`pytest` (editais de exemplo fictícios em `leilaoia/samples`; regenere com `python scripts/make_samples.py`).

> Análise automatizada de apoio; não substitui a leitura do edital nem assessoria jurídica. Valores "estimados" são premissas ajustáveis.
