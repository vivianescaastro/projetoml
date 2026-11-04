from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from leilaoia import agents, excel_db, heuristics
from leilaoia.dossie_pdf import gerar_pdf
from leilaoia.main import app
from leilaoia.pdf_reader import extrair_texto, normalizar
from leilaoia.schemas import Perfil, Premissas

S = Path(__file__).parent.parent / "leilaoia" / "samples"


def texto(n):
    return normalizar(extrair_texto((S / n).read_bytes())[0])


def test_tipo_detectado():
    assert heuristics.detectar_tipo(texto("edital_judicial_veiculo.pdf"))[0] == "Judicial"
    assert heuristics.detectar_tipo(texto("edital_receita_federal.pdf"))[0] == "Receita Federal"
    assert heuristics.detectar_tipo(texto("edital_extrajudicial_imovel.pdf"))[0] == "Extrajudicial"


def test_extracao_judicial():
    ed = heuristics.extrair(texto("edital_judicial_veiculo.pdf"))
    assert ed.comissao_pct == 5 and ed.prazo_pagamento_dias == 1
    assert ed.lance_minimo_2 == 24000 and ed.leiloeiro == "João da Silva"
    arm = next(c for c in ed.custos if c.tipo == "diaria")
    assert arm.valor == 45 and arm.dias_gratis == 5


def test_extracao_extrajudicial_debitos_e_caucao():
    ed = heuristics.extrair(texto("edital_extrajudicial_imovel.pdf"))
    assert ed.lance_minimo_1 == 520000 and ed.lance_minimo_2 == 310000
    deb = next(c for c in ed.custos if c.nome.startswith("Débitos"))
    assert deb.valor == 18400
    cau = next(c for c in ed.custos if c.nome.startswith("Caução"))
    assert cau.valor == 20000 and not cau.computa_no_total


@pytest.mark.parametrize("arq,lid", [("edital_judicial_veiculo.pdf", "L001"), ("edital_receita_federal.pdf", "L002"),
                                     ("edital_extrajudicial_imovel.pdf", "L003")])
def test_pipeline_completo(arq, lid):
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == lid)
    evs = list(agents.executar((S / arq).read_bytes(), arq, lote, Perfil(), Premissas()))
    assert not [e for e in evs if e["type"] == "erro"]
    d = evs[-1]["dados"]
    assert d["veredito"]["decisao"] in ("COMPRAR", "ATENÇÃO", "NÃO COMPRAR")
    assert d["custos"]["custo_total"] > d["custos"]["lance"]
    assert gerar_pdf(d).startswith(b"%PDF")


def test_so_um_ramo_executa():
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == "L002")
    evs = list(agents.executar((S / "edital_receita_federal.pdf").read_bytes(), "x.pdf", lote, Perfil(), Premissas()))
    st = {e["id"]: e["status"] for e in evs if e["type"] == "agent" and e["status"] != "running"}
    assert st[5] == "done" and st[4] == st[6] == "skipped"


def test_planilha_invalida_e_modelo():
    with pytest.raises(ValueError):
        excel_db.ler_planilha(b"nao e xlsx")
    base = excel_db.ler_planilha(excel_db.modelo_xlsx())
    assert base.lotes[0].lance_minimo == 24000


def test_api(tmp_path, monkeypatch):
    monkeypatch.setenv("DADOS_DIR", str(tmp_path))
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"]
    r = c.post("/api/lotes/buscar", json={"perfil": {"categoria": "Imóvel"}})
    assert {l["categoria"] for l in r.json()["lotes"]} == {"Imóvel"}
    assert c.post("/api/analise", files={"edital": ("a.pdf", b"nao pdf")}).status_code == 422
    with (S / "edital_receita_federal.pdf").open("rb") as f:
        r = c.post("/api/analise", files={"edital": ("e.pdf", f, "application/pdf")})
    assert r.status_code == 200 and '"type": "dossie"' in r.text


def test_senha_de_acesso(monkeypatch, tmp_path):
    monkeypatch.setenv("DADOS_DIR", str(tmp_path))
    monkeypatch.setenv("APP_PASSWORD", "segredo")
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    assert c.get("/").status_code == 401
    assert c.get("/", auth=("eu", "errada")).status_code == 401
    assert c.get("/", auth=("eu", "segredo")).status_code == 200


@pytest.mark.parametrize("arq", ["edital_judicial_veiculo.pdf", "edital_receita_federal.pdf", "edital_extrajudicial_imovel.pdf"])
def test_fidelidade_todo_valor_do_pdf_aparece(arq):
    import re
    from leilaoia.pdf_reader import extrair_paginas
    pgs = extrair_paginas((S / arq).read_bytes())
    ed = heuristics.extrair("\n".join(pgs), pgs)
    no_pdf = set(re.findall(heuristics.MONEY, " ".join(pgs)))
    listados = set(re.findall(heuristics.MONEY, " ".join(t.trecho for t in ed.valores_encontrados)))
    assert no_pdf and no_pdf <= listados                       # nenhum R$ do edital ficou de fora
    assert all(c.pagina == 1 for c in ed.custos if c.fonte)    # cada custo aponta a página
    assert all(c.fonte in " ".join(pgs).replace("\n", " ") or c.fonte for c in ed.custos)


def test_base_fixa_e_subtotais():
    assert excel_db.carregar_base().lotes
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == "L003")
    d = list(agents.executar((S / "edital_extrajudicial_imovel.pdf").read_bytes(), "x.pdf", lote, Perfil(), Premissas()))[-1]["dados"]["custos"]
    assert abs(d["subtotal_edital"] + d["extras_estimados"] + d["extras_usuario"] - d["custo_total"]) < 0.01
    assert d["extras_estimados"] > 0


def test_historico_salva_planilha_e_html(tmp_path, monkeypatch):
    import json as _j
    from openpyxl import load_workbook
    from leilaoia import storage
    monkeypatch.setenv("DADOS_DIR", str(tmp_path))
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == "L001")
    for arq in ("edital_judicial_veiculo.pdf", "edital_judicial_veiculo.pdf"):
        d = list(agents.executar((S / arq).read_bytes(), arq, lote, Perfil(), Premissas()))[-1]["dados"]
        info = storage.salvar(d)
    assert info["total"] == 2          # duas análises seguidas não podem se sobrescrever
    wb = load_workbook(tmp_path / "historico.xlsx")
    assert set(wb.sheetnames) == {"Analises", "Custos", "Pontos", "Valores_edital", "Prazos", "Objetivo_perguntas"}
    assert wb["Analises"].max_row >= 2 and wb["Custos"].max_row > 2
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Histórico de Análises" in html and "edital_judicial_veiculo.pdf" in html
    assert len(list((tmp_path / "json").glob("*.json"))) == info["total"]


def test_api_grava_no_historico(tmp_path, monkeypatch):
    monkeypatch.setenv("DADOS_DIR", str(tmp_path))
    c = TestClient(app)
    with (S / "edital_receita_federal.pdf").open("rb") as f:
        r = c.post("/api/analise", files={"edital": ("e.pdf", f, "application/pdf")})
    assert '"type": "salvo"' in r.text and (tmp_path / "historico.xlsx").exists()


def test_ids_sequenciais(tmp_path, monkeypatch):
    from leilaoia import storage
    monkeypatch.setenv("DADOS_DIR", str(tmp_path))
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == "L002")
    ids = []
    for _ in range(3):
        d = list(agents.executar((S / "edital_receita_federal.pdf").read_bytes(), "x.pdf", lote, Perfil(), Premissas()))[-1]["dados"]
        ids.append(storage.salvar(d)["id"])
    assert ids == ["AN-0001", "AN-0002", "AN-0003"]
    next((tmp_path / "json").glob("AN-0003*")).unlink()   # apagar não reaproveita número
    d = list(agents.executar((S / "edital_receita_federal.pdf").read_bytes(), "x.pdf", lote, Perfil(), Premissas()))[-1]["dados"]
    assert storage.salvar(d)["id"] == "AN-0004"
    assert gerar_pdf(d).startswith(b"%PDF")


def _veredito(arq, lid, **perfil):
    lote = next(l for l in excel_db.carregar_base().lotes if l.id == lid)
    return list(agents.executar((S / arq).read_bytes(), arq, lote, Perfil(**perfil), Premissas()))[-1]["dados"]


def test_respostas_do_objetivo_no_dossie():
    d = _veredito("edital_judicial_veiculo.pdf", "L001", aceita_ocupado=False)
    assert any("ocupado" in r["pergunta"] for r in d["respostas"])
    assert d["respostas"][0]["resposta"] == "Revender com lucro"


def test_resposta_nao_aceita_ocupado_bloqueia():
    d = _veredito("edital_extrajudicial_imovel.pdf", "L003", orcamento_max=900000, aceita_ocupado=False)
    assert any("não aceita bem ocupado" in b for b in d["veredito"]["bloqueios"])
    assert d["veredito"]["decisao"] == "NÃO COMPRAR"


def test_resposta_nao_aceita_debitos_e_pagamento():
    d = _veredito("edital_extrajudicial_imovel.pdf", "L003", orcamento_max=900000, aceita_debitos=False, pagamento_imediato=False)
    b = " ".join(d["veredito"]["bloqueios"])
    assert "não aceita assumir débitos" in b and "não terá o valor total" in b


def test_sem_respostas_nao_cria_bloqueio_novo():
    d = _veredito("edital_extrajudicial_imovel.pdf", "L003", orcamento_max=900000)
    assert not any("você respondeu" in b or "não terá" in b for b in d["veredito"]["bloqueios"])
