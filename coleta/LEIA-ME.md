# Coleta de leilões da Receita Federal

Coleta o portal de leilões (SLE Sociedade) com Python + Playwright, guarda o histórico
e gera uma página HTML.

- **Filtros:** edite `coleta/config.json` (estados, tipos de lote, quando baixar o PDF do edital).
- **Rodar no GitHub:** aba *Actions* → *Coleta de leilões* → *Run workflow*. Só roda manualmente (sem agendamento).
- **Resultado:** `docs/index.html` (página), `data/historico.json` (histórico), `docs/editais/` (PDFs dos editais).
- **Ver a página:** *Settings* → *Pages* → *Deploy from a branch* → escolha a branch e a pasta `/docs`.
  Também dá para baixar `pagina-leiloes` na tela de cada execução (aba Actions).
- **Rodar no computador:** `pip install -r coleta/requirements.txt && playwright install chromium && python coleta/receita_leiloes.py`
  (`--sem-pdf` pula o download dos editais; `--so-html` regenera a página sem acessar o portal).
