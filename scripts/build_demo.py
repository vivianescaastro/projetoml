"""Gera leilaoia/demo.html: demonstração estática com os 3 cenários processados pela cadeia real."""
import json
from pathlib import Path

from leilaoia import agents, excel_db
from leilaoia.schemas import Perfil, Premissas

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "leilaoia" / "samples"
CEN = [
    ("L001", "edital_judicial_veiculo.pdf", "Judicial · veículo", "Honda Civic 2019 em leilão judicial",
     Perfil(objetivo="revenda", orcamento_max=100000, risco="medio", margem_alvo_pct=20)),
    ("L002", "edital_receita_federal.pdf", "Receita Federal · veículo", "Fiat Toro 2020 apreendida pela Receita",
     Perfil(objetivo="revenda", orcamento_max=100000, risco="medio", margem_alvo_pct=20)),
    ("L003", "edital_extrajudicial_imovel.pdf", "Extrajudicial · imóvel", "Apartamento em alienação fiduciária",
     Perfil(objetivo="revenda", orcamento_max=650000, risco="medio", margem_alvo_pct=15)),
]
base = excel_db.carregar_base()
out = []
for lid, arq, rot, tit, perfil in CEN:
    lote = next(l for l in base.lotes if l.id == lid)
    lote.desconto_pct = round((1 - lote.lance_minimo / lote.valor_mercado) * 100, 1)
    evs = [e for e in agents.executar((S / arq).read_bytes(), arq, lote, perfil, Premissas())]
    assert not [e for e in evs if e["type"] == "erro"], arq
    for e in evs:
        e.pop("seg", None)
    resumo = f"{perfil.objetivo} · orçamento R$ {perfil.orcamento_max:,.0f} · risco {perfil.risco} · margem-alvo {perfil.margem_alvo_pct:.0f}%".replace(",", ".")
    out.append({"rotulo": rot, "titulo": tit, "perfil": resumo, "eventos": evs})
html = (ROOT / "scripts" / "demo_template.html").read_text().replace("/*__DATA__*/", json.dumps(out, ensure_ascii=False))
(ROOT / "leilaoia" / "demo.html").write_text(html)
print("demo.html:", len(html) // 1024, "KB")

# versão para GitHub Pages: documento HTML completo em docs/index.html
i = html.index("</style>") + len("</style>")
docs = ROOT / "docs"
docs.mkdir(exist_ok=True)
(docs / "index.html").write_text('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
                                 '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n'
                                 + html[:i] + "\n</head>\n<body>\n" + html[i:] + "\n</body>\n</html>\n")
(docs / ".nojekyll").write_text("")
print("docs/index.html pronto")
