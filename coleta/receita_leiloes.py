#!/usr/bin/env python3
"""Coleta de leilões da Receita Federal (SLE Sociedade) com Playwright.

Fluxo: abre o portal, marca UF e Tipo de Lote conforme coleta/config.json,
aplica o filtro, extrai editais e lotes, baixa o PDF dos editais abertos que
têm o tipo de interesse, atualiza o histórico (data/historico.json) e gera a
página docs/index.html.

Uso: python coleta/receita_leiloes.py [--sem-pdf]
Variável opcional PW_EXECUTABLE: caminho de um Chromium já instalado.
"""
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "coleta" / "config.json").read_text(encoding="utf-8"))
HISTORICO = RAIZ / "data" / "historico.json"
PDFS = RAIZ / "docs" / "editais"
BASE = "https://www25.receita.fazenda.gov.br"
# OBS: o link com ";t=..." (parâmetro de matriz) é rejeitado com 403; sem ele a página abre.

JS_EXTRAI = r"""
() => {
  const tx = (e) => (e ? e.textContent.replace(/\s+/g, ' ').trim() : '');
  const num = (v) => { const m = /R\$\s*([\d.]+,\d{2})/.exec(v || ''); return m ? parseFloat(m[1].replace(/\./g, '').replace(',', '.')) : null; };
  const lista = []; let atual = null; const vistos = new Set();
  for (const tr of document.querySelectorAll('table.table-edital tr')) {
    const ed = tr.querySelector(':scope > td.col-edital a');
    if (ed) {
      const c = [...tr.children].map(tx);
      atual = { edital: tx(ed), href: ed.getAttribute('href'), orgao: c[2] || '', propostas_ate: c[3] || '',
                lances: c[4] || '', total_lotes_edital: Number(c[5]) || null, lotes: [] };
      lista.push(atual); continue;
    }
    const a = tr.querySelector(':scope > td a');
    const c = [...tr.children].map(tx);
    if (atual && a && /^Lote \d+$/.test(tx(a)) && c.length >= 4) {
      const k = atual.edital + '|' + tx(a);
      if (vistos.has(k)) continue; vistos.add(k);
      atual.lotes.push({ lote: tx(a), href: a.getAttribute('href'), tipo: c[1], situacao: c[2], preco_minimo: num(c[3]) });
    }
  }
  return lista;
}
"""


def agora():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")


def _marcar_uf(page, uf):
    """Marca a UF pelo nome exato (evita 'MATO GROSSO' pegar 'MATO GROSSO DO SUL')."""
    rotulo = page.locator("label").filter(has_text=re.compile(rf"^\s*{re.escape(uf)}\s*\d*\s*$", re.I))
    rotulo.locator("input[type=checkbox]").first.check()


def _painel(page, titulo):
    return (page.locator("div,section")
            .filter(has=page.get_by_text(titulo, exact=True))
            .filter(has=page.locator("label:has(input[type=checkbox])")).last)


def _abrir_portal(page):
    page.goto(CONFIG["url"], wait_until="load", timeout=60000)
    page.locator("label:has(input[type=checkbox])").first.wait_for(timeout=60000)


def descobrir_ufs(page):
    """Lê no portal a lista de estados que têm leilão no momento."""
    _abrir_portal(page)
    _painel(page, "UF").locator("button:has(.glyphicon-plus)").first.click()
    nomes = _painel(page, "UF").locator("label").all_inner_texts()
    ufs = [re.sub(r"\s*\d+\s*$", "", n).strip() for n in nomes]
    return sorted(u for u in ufs if u)


def filtrar_uf(page, uf, tipos_re):
    """Aplica o filtro (um estado + tipos de lote) e devolve os editais com lotes."""
    _abrir_portal(page)
    _painel(page, "UF").locator("button:has(.glyphicon-plus)").first.click()
    _marcar_uf(page, uf)
    _painel(page, "Tipo de Lote").locator("button:has(.glyphicon-plus)").first.click()
    marcas = page.locator("label", has_text=tipos_re).locator("input[type=checkbox]")
    for i in range(marcas.count()):
        marcas.nth(i).check()
    for b in page.get_by_role("button", name=re.compile("Aplicar Filtro")).filter(visible=True).all():
        b.click()
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(1500)
    bruto = page.evaluate(JS_EXTRAI)
    # a página repete o cabeçalho do edital (tabela-resumo e tabela de lotes): junta por número
    mapa = {}
    for e in bruto:
        if e["edital"] in mapa:
            mapa[e["edital"]]["lotes"].extend(e["lotes"])
        else:
            mapa[e["edital"]] = e
    for e in mapa.values():
        e["uf"] = uf
    print(f"  {uf}: {len(mapa)} editais, {sum(len(e['lotes']) for e in mapa.values())} lotes (tipos marcados: {marcas.count()})")
    return list(mapa.values())


def coletar(baixar_pdf=True):
    """Roda o navegador e devolve a lista de editais (com lotes e UF) e os PDFs baixados."""
    tipos_re = re.compile(CONFIG["tipos_regex"], re.I)
    pdf_re = re.compile(CONFIG["baixar_edital_se_tipo_regex"], re.I)
    with sync_playwright() as p:
        opts = {}
        if os.environ.get("PW_EXECUTABLE"):
            opts["executable_path"] = os.environ["PW_EXECUTABLE"]
        browser = p.chromium.launch(**opts)
        ctx = browser.new_context(viewport={"width": 1280, "height": 1000}, accept_downloads=True)

        ufs = CONFIG["ufs"]
        if any(u.upper() in ("TODOS", "TODOS OS ESTADOS") for u in ufs):
            pg = ctx.new_page()
            ufs = descobrir_ufs(pg)
            pg.close()
            print("Estados com leilão no portal:", ", ".join(ufs))
        editais_por_nome = {}
        for uf in ufs:
            pg = ctx.new_page()
            try:
                for e in filtrar_uf(pg, uf, tipos_re):
                    editais_por_nome.setdefault(e["edital"], e)
            finally:
                pg.close()
        editais = list(editais_por_nome.values())
        if not editais:
            raise RuntimeError("Nenhum edital extraído: o portal mudou ou o filtro não retornou nada.")

        PDFS.mkdir(parents=True, exist_ok=True)
        for e in editais:
            abertos = [l for l in e["lotes"] if pdf_re.search(l["tipo"]) and l["situacao"] == "Aberto para Proposta"]
            interesse = abertos if CONFIG.get("so_editais_abertos_para_pdf") else [l for l in e["lotes"] if pdf_re.search(l["tipo"])]
            e["lotes_interesse"] = len(interesse)
            e["pdf"] = None
            if not interesse or not baixar_pdf:
                continue
            m = re.search(r"/edital/(\d+)/(\d+)/(\d{4})", e["href"])
            esperado = PDFS / f"Edital_Completo_{m.group(3)}_{m.group(1)}_{m.group(2)}.pdf" if m else None
            if esperado and esperado.exists():  # já baixado em coleta anterior
                e["pdf"] = f"editais/{esperado.name}"
                continue
            aba = ctx.new_page()
            try:
                aba.goto(BASE + e["href"], wait_until="load", timeout=60000)
                link = aba.get_by_text("Arquivo Texto do Edital").first
                link.wait_for(timeout=30000)
                with aba.expect_download(timeout=60000) as dl:
                    link.click()
                d = dl.value
                destino = PDFS / d.suggested_filename
                d.save_as(destino)
                e["pdf"] = f"editais/{destino.name}"
                print(f"Edital baixado: {e['edital']} -> {e['pdf']}")
            except Exception as ex:  # um PDF que falha não derruba a coleta
                print(f"AVISO: não baixou o PDF de {e['edital']}: {ex}", file=sys.stderr)
            finally:
                aba.close()
        browser.close()
    return editais


def atualizar_historico(editais):
    """Compara a coleta atual com o histórico e marca novos, alterados e que saíram."""
    h = json.loads(HISTORICO.read_text(encoding="utf-8")) if HISTORICO.exists() else {"lotes": {}, "editais": {}, "execucoes": []}
    ts = agora()
    filtro_atual = {"ufs": CONFIG["ufs"], "tipos_regex": CONFIG["tipos_regex"]}
    antigo = h.get("filtros")
    if antigo and {"ufs": antigo.get("ufs"), "tipos_regex": antigo.get("tipos_regex")} != filtro_atual:
        # filtro mudou: arquiva o histórico anterior e começa um novo (senão os lotes antigos viram "saiu")
        arq = HISTORICO.parent / "arquivo"
        arq.mkdir(exist_ok=True)
        (arq / f"historico_{ts.replace(':', '').replace(' ', '_')}.json").write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Filtro mudou: histórico anterior arquivado em data/arquivo/.")
        h = {"lotes": {}, "editais": {}, "execucoes": []}
    visto = set()
    novos = alterados = 0
    for e in editais:
        h["editais"][e["edital"]] = {k: e[k] for k in ("edital", "href", "uf", "orgao", "propostas_ate", "lances", "total_lotes_edital", "pdf", "lotes_interesse")} | {
            "ultima_vez": ts, "ativo": True}
        for l in e["lotes"]:
            chave = f"{e['edital']}|{l['lote']}"
            visto.add(chave)
            r = h["lotes"].get(chave)
            if r is None:
                h["lotes"][chave] = {"edital": e["edital"], "lote": l["lote"], "href": l["href"], "tipo": l["tipo"],
                                     "preco_minimo": l["preco_minimo"], "situacao": l["situacao"], "primeira_vez": ts,
                                     "ultima_vez": ts, "ativo": True, "novo_na_execucao": ts, "alterado_na_execucao": None,
                                     "variacoes": []}
                novos += 1
            else:
                if r["preco_minimo"] != l["preco_minimo"] or r["situacao"] != l["situacao"]:
                    r["variacoes"].append({"data": ts, "preco_antes": r["preco_minimo"], "preco_depois": l["preco_minimo"],
                                           "situacao_antes": r["situacao"], "situacao_depois": l["situacao"]})
                    r["alterado_na_execucao"] = ts
                    alterados += 1
                r.update(tipo=l["tipo"], href=l["href"], preco_minimo=l["preco_minimo"], situacao=l["situacao"],
                         ultima_vez=ts, ativo=True)
    saiu = 0
    for chave, r in h["lotes"].items():
        if chave not in visto and r["ativo"]:
            r["ativo"] = False
            r["saiu_em"] = ts
            saiu += 1
    for nome, ed in h["editais"].items():
        if nome not in {e["edital"] for e in editais}:
            ed["ativo"] = False
    h["execucoes"].append({"data": ts, "editais": len(editais), "lotes": sum(len(e["lotes"]) for e in editais),
                           "novos": novos, "alterados": alterados, "saiu": saiu})
    h["execucoes"] = h["execucoes"][-200:]
    h["ultima_execucao"] = ts
    h["filtros"] = {"ufs": CONFIG["ufs"], "tipos_regex": CONFIG["tipos_regex"], "tipos": CONFIG.get("tipos_descricao", CONFIG["tipos_regex"])}
    HISTORICO.parent.mkdir(parents=True, exist_ok=True)
    HISTORICO.write_text(json.dumps(h, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Histórico: {novos} novos, {alterados} alterados, {saiu} saíram.")
    return h


def gerar_html(h):
    """Gera docs/index.html (página única, sem dependências) a partir do histórico."""
    modelo = (RAIZ / "coleta" / "template.html").read_text(encoding="utf-8")
    dados = json.dumps(h, ensure_ascii=False).replace("</", "<\\/")
    (RAIZ / "docs").mkdir(exist_ok=True)
    (RAIZ / "docs" / "index.html").write_text(modelo.replace("__DATA__", dados), encoding="utf-8")
    (RAIZ / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    print("Página gerada: docs/index.html")


def main():
    if "--so-html" in sys.argv:  # regenera a página sem acessar o portal
        gerar_html(json.loads(HISTORICO.read_text(encoding="utf-8")))
        return
    editais = coletar(baixar_pdf="--sem-pdf" not in sys.argv)
    total = sum(len(e["lotes"]) for e in editais)
    print(f"Editais: {len(editais)} | lotes: {total}")
    gerar_html(atualizar_historico(editais))


if __name__ == "__main__":
    main()
