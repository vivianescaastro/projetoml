"""Histórico de análises: cada execução grava JSON + planilha (xlsx) e reconstrói o espelho em HTML.

Fonte da verdade = `analises/json/*.json`. A planilha e o HTML são regenerados a partir dela (idempotente).
Pasta configurável por DADOS_DIR (padrão: <repo>/analises). AUTO_COMMIT=1 envia as mudanças ao GitHub (opt-in).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).parent / "historico_template.html"
_LOCK = threading.Lock()


def pasta() -> Path:
    d = Path(os.getenv("DADOS_DIR") or REPO / "analises")
    (d / "json").mkdir(parents=True, exist_ok=True)
    return d


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()[:40] or "analise"


def _bem(d: dict) -> str:
    return (d.get("lote") or {}).get("descricao") or d["ficha"].get("descricao_bem") or d.get("arquivo") or "—"


def _linhas(d: dict):
    f, c, v, lote = d["ficha"], d["custos"], d["veredito"], d.get("lote") or {}
    cont = {s: sum(1 for p in d["pontos"] if p["severidade"] == s) for s in ("alta", "media")}
    bem, i = _bem(d), d["id"]
    analise = [i, d["gerado_em"], d["arquivo"], lote.get("id"), bem, lote.get("categoria") or f.get("categoria_bem"),
               d["tipo_leilao"], v["decisao"], c["lance"], c["custo_total"], c.get("subtotal_edital"),
               c.get("extras_estimados"), c.get("extras_usuario"), c.get("valor_venda_ref"), c.get("lucro"),
               c.get("margem_pct"), c.get("lance_maximo_recomendado"), cont["alta"], cont["media"], f.get("leiloeiro"),
               f.get("processo"), f.get("data_praca1"), f.get("data_praca2"), f.get("lance_minimo_1"),
               f.get("lance_minimo_2"), f.get("comissao_pct"), f.get("prazo_pagamento_texto"), f.get("forma_pagamento"),
               f.get("debitos_responsabilidade"), "IA" if d["modo_leitura"] == "ia" else "regras",
               " | ".join(v["bloqueios"]), " | ".join(v["atencoes"])]
    custos = [[i, bem, x["nome"], x["tipo"], x["valor"], x["quantidade"], x["valor_calculado"], x.get("pago_a"),
               x.get("quando"), x.get("como"), x["origem"], "sim" if x["computa_no_total"] else "não (abatido)",
               x.get("pagina"), x.get("fonte") if x["origem"] == "edital" else None] for x in c["itens"]]
    pontos = [[i, bem, p["severidade"], p["titulo"], p["descricao"], p.get("fundamento"), p.get("trecho")] for p in d["pontos"]]
    valores = [[i, bem, t.get("pagina"), " · ".join(t["valores"]), t["trecho"]] for t in f.get("valores_encontrados", [])]
    prazos = [[i, bem, p["data"], p["evento"], p.get("alerta")] for p in d["prazos"]]
    return analise, custos, pontos, valores, prazos


ABAS = {
    "Analises": ["ID", "Data", "PDF", "Lote", "Bem", "Categoria", "Tipo de leilão", "Veredito", "Lance", "Custo total",
                 "Só edital", "Estimativas", "Informado por você", "Valor de referência", "Lucro", "Margem %",
                 "Lance máximo", "Riscos altos", "Riscos médios", "Leiloeiro", "Processo", "1ª praça", "2ª praça",
                 "Lance mín. 1ª", "Lance mín. 2ª", "Comissão %", "Prazo de pagamento", "Forma de pagamento",
                 "Débitos", "Leitura", "Bloqueios", "Atenção"],
    "Custos": ["ID", "Bem", "Item", "Base", "Valor/%", "Qtd", "Valor calculado", "Pago a", "Quando", "Como", "Origem",
               "Soma no total", "Página", "Trecho literal do edital"],
    "Pontos": ["ID", "Bem", "Severidade", "Ponto", "Descrição", "Fundamento", "Trecho"],
    "Valores_edital": ["ID", "Bem", "Página", "Valores", "Trecho literal"],
    "Prazos": ["ID", "Bem", "Data", "Evento", "Alerta"],
}


def _planilha(dossies: list[dict], destino: Path) -> None:
    wb = Workbook()
    wb.remove(wb.active)
    ws = {n: wb.create_sheet(n) for n in ABAS}
    for n, cab in ABAS.items():
        ws[n].append(cab)
        for c in ws[n][1]:
            c.font = Font(bold=True, color="FFFFFF")
            c.fill = PatternFill("solid", fgColor="1F3A5F")
        ws[n].freeze_panes = "A2"
    for d in dossies:
        a, cu, po, va, pr = _linhas(d)
        ws["Analises"].append(a)
        for r in cu: ws["Custos"].append(r)
        for r in po: ws["Pontos"].append(r)
        for r in va: ws["Valores_edital"].append(r)
        for r in pr: ws["Prazos"].append(r)
    for row in ws["Analises"].iter_rows(min_row=2, min_col=9, max_col=17):
        for c in row:
            if c.column in (9, 10, 11, 12, 13, 14, 15, 17):
                c.number_format = '"R$" #,##0.00'
    for n, cab in ABAS.items():
        for j, h in enumerate(cab, 1):
            ws[n].column_dimensions[ws[n].cell(1, j).column_letter].width = 60 if "Trecho" in h or h in ("Descrição", "Bloqueios", "Atenção", "Evento") else max(12, min(30, len(h) + 4))
    wb.save(destino)


def reconstruir(d: Path | None = None) -> dict:
    d = d or pasta()
    dossies = []
    for p in sorted((d / "json").glob("*.json"), reverse=True):
        try:
            dossies.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    _planilha(list(reversed(dossies)), d / "historico.xlsx")
    dados = json.dumps(dossies, ensure_ascii=False).replace("</", "<\\/")
    (d / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/", dados), encoding="utf-8")
    return {"analises": len(dossies)}


def _commit(d: Path) -> None:
    try:
        rel = os.path.relpath(d, REPO)
        subprocess.run(["git", "add", rel], cwd=REPO, check=True, timeout=30, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Histórico: nova análise de edital"], cwd=REPO, timeout=30, capture_output=True)
        subprocess.run(["git", "push"], cwd=REPO, timeout=90, capture_output=True)
    except Exception:  # noqa: BLE001 — melhor esforço
        pass


def salvar(dossie: dict) -> dict:
    d = pasta()
    with _LOCK:
        ident = datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3] + "-" + _slug((dossie.get("lote") or {}).get("id") or dossie.get("arquivo", ""))
        dossie["id"] = ident
        (d / "json" / f"{ident}.json").write_text(json.dumps(dossie, ensure_ascii=False, indent=1), encoding="utf-8")
        total = reconstruir(d)["analises"]
    if os.getenv("AUTO_COMMIT") == "1":
        threading.Thread(target=_commit, args=(d,), daemon=True).start()
    return {"id": ident, "planilha": "historico.xlsx", "total": total, "github": os.getenv("AUTO_COMMIT") == "1"}


if __name__ == "__main__":   # python -m leilaoia.storage  → reconstrói planilha + HTML
    print(reconstruir())
