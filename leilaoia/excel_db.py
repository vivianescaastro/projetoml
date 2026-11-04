"""Agente 2 (dados): leitura e validação da planilha Excel de lotes."""
from __future__ import annotations

import io
import re
import unicodedata
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .schemas import TIPOS, Lote, Perfil

DATA_DIR = Path(__file__).parent / "data"
UPLOAD_DIR = Path(__import__("tempfile").gettempdir()) / "leilaoia_bases"
UPLOAD_DIR.mkdir(exist_ok=True)

COLUNAS = {
    "id": ["id", "lote", "codigo", "n lote", "numero do lote"],
    "categoria": ["categoria", "tipo de bem", "classe"],
    "descricao": ["descricao", "bem", "descricao do bem", "item"],
    "uf": ["uf", "estado"],
    "cidade": ["cidade", "municipio", "comarca"],
    "tipo_leilao": ["tipo de leilao", "tipo leilao", "tipo_leilao", "modalidade"],
    "valor_avaliacao": ["avaliacao", "valor de avaliacao", "valor avaliacao"],
    "lance_minimo": ["lance minimo", "lance inicial", "valor minimo", "lance"],
    "valor_mercado": ["valor de mercado", "mercado", "fipe", "valor fipe", "valor mercado"],
    "data_leilao": ["data", "data do leilao", "data leilao", "data da praca", "1a praca"],
    "leiloeiro": ["leiloeiro"],
    "comissao_pct": ["comissao", "comissao %", "comissao pct", "comissao (%)"],
    "situacao": ["situacao", "status", "observacoes", "obs"],
    "link": ["link", "url", "edital"],
}
OBRIGATORIAS = ("descricao", "lance_minimo")
CATEGORIAS = {"veiculos": "Veículos", "veiculo": "Veículos", "imovel": "Imóvel", "imoveis": "Imóvel",
              "bens diversos": "Bens Diversos", "diversos": "Bens Diversos", "bens": "Bens Diversos"}


def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9%() ]+", " ", s).strip()


def parse_brl(v) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"\d{1,3}\.\d{3}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def norm_tipo(v) -> Optional[str]:
    n = _norm(v)
    if not n:
        return None
    if "judic" in n and "extra" not in n:
        return "Judicial"
    if "receita" in n or "rfb" in n or "federal" in n:
        return "Receita Federal"
    if "extra" in n or "fiduci" in n or "bancari" in n:
        return "Extrajudicial"
    return None


def _data(v) -> Optional[str]:
    if isinstance(v, (datetime, date)):
        return v.strftime("%d/%m/%Y")
    return str(v).strip() if v not in (None, "") else None


class Base:
    def __init__(self, lotes: list[Lote], avisos: list[str], nome: str):
        self.lotes, self.avisos, self.nome = lotes, avisos, nome


def ler_planilha(conteudo: bytes, nome: str = "base.xlsx") -> Base:
    try:
        wb = load_workbook(io.BytesIO(conteudo), data_only=True, read_only=True)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Arquivo não é uma planilha .xlsx válida.") from exc
    ws = wb["Lotes"] if "Lotes" in wb.sheetnames else wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Planilha vazia.")
    # cabeçalho = primeira linha com ao menos 2 colunas reconhecidas
    mapa: dict[str, int] = {}
    inicio = 0
    for i, r in enumerate(rows[:10]):
        cand = {}
        for j, cel in enumerate(r):
            n = _norm(cel)
            for campo, aliases in COLUNAS.items():
                if n in aliases and campo not in cand:
                    cand[campo] = j
        if len(cand) >= 2:
            mapa, inicio = cand, i + 1
            break
    faltam = [c for c in OBRIGATORIAS if c not in mapa]
    if faltam:
        raise ValueError(f"Colunas obrigatórias não encontradas: {', '.join(faltam)}. "
                         "Baixe o modelo de planilha.")
    lotes, avisos = [], []
    for k, r in enumerate(rows[inicio:], start=inicio + 1):
        def g(campo):
            j = mapa.get(campo)
            return r[j] if j is not None and j < len(r) else None
        if not any(c not in (None, "") for c in r):
            continue
        desc = str(g("descricao") or "").strip()
        lance = parse_brl(g("lance_minimo"))
        if not desc:
            avisos.append(f"Linha {k}: sem descrição — ignorada.")
            continue
        if lance is None:
            avisos.append(f"Linha {k} ({desc[:30]}): lance mínimo ausente/inválido.")
        tipo_raw = g("tipo_leilao")
        tipo = norm_tipo(tipo_raw)
        if tipo_raw and not tipo:
            avisos.append(f"Linha {k}: tipo de leilão '{tipo_raw}' não reconhecido "
                          f"(use {', '.join(TIPOS)}).")
        cat_raw = _norm(g("categoria"))
        categoria = CATEGORIAS.get(cat_raw, "Bens Diversos")
        if cat_raw and cat_raw not in CATEGORIAS:
            avisos.append(f"Linha {k}: categoria '{g('categoria')}' tratada como Bens Diversos.")
        uf = (str(g("uf") or "").strip().upper() or None)
        if uf and len(uf) != 2:
            avisos.append(f"Linha {k}: UF '{uf}' inválida."); uf = None
        lotes.append(Lote(
            id=str(g("id") or f"L{k:03d}").strip(), categoria=categoria, descricao=desc,
            uf=uf, cidade=(str(g("cidade")).strip() if g("cidade") else None), tipo_leilao=tipo,
            valor_avaliacao=parse_brl(g("valor_avaliacao")), lance_minimo=lance,
            valor_mercado=parse_brl(g("valor_mercado")), data_leilao=_data(g("data_leilao")),
            leiloeiro=(str(g("leiloeiro")).strip() if g("leiloeiro") else None),
            comissao_pct=parse_brl(g("comissao_pct")),
            situacao=(str(g("situacao")).strip() if g("situacao") else None),
            link=(str(g("link")).strip() if g("link") else None)))
    if not lotes:
        raise ValueError("Nenhum lote válido encontrado na planilha.")
    return Base(lotes, avisos, nome)


def salvar_upload(conteudo: bytes, nome: str) -> tuple[str, Base]:
    base = ler_planilha(conteudo, nome)       # valida antes de gravar
    bid = uuid.uuid4().hex[:12]
    (UPLOAD_DIR / f"{bid}.xlsx").write_bytes(conteudo)
    return bid, base


def caminho_base_fixa() -> Path:
    """Base fornecida: env BASE_XLSX, senão data/base_leiloes.xlsx, senão a base de exemplo."""
    env = __import__("os").getenv("BASE_XLSX")
    for cand in ([Path(env)] if env else []) + [DATA_DIR / "base_leiloes.xlsx", DATA_DIR / "base_exemplo.xlsx"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("Nenhuma planilha de base encontrada (coloque em leilaoia/data/base_leiloes.xlsx).")


def carregar_base(base_id: str = "fixa") -> Base:
    if base_id == "fixa":
        p = caminho_base_fixa()
    elif base_id == "exemplo":
        p = DATA_DIR / "base_exemplo.xlsx"
    else:
        if not re.fullmatch(r"[0-9a-f]{12}", base_id):
            raise ValueError("base_id inválido")
        p = UPLOAD_DIR / f"{base_id}.xlsx"
    if not p.exists():
        raise FileNotFoundError("Base não encontrada — envie a planilha novamente.")
    return ler_planilha(p.read_bytes(), p.name)


def buscar(base: Base, perfil: Perfil, limite: int = 15) -> list[Lote]:
    """Filtra pelo perfil e ranqueia pelo desconto sobre o valor de mercado."""
    out = []
    for l in base.lotes:
        if perfil.categoria not in ("Todas", "", None) and l.categoria != perfil.categoria:
            continue
        if perfil.uf and l.uf != perfil.uf.upper():
            continue
        if perfil.tipo_leilao not in ("Todos", "", None) and l.tipo_leilao != perfil.tipo_leilao:
            continue
        if perfil.orcamento_max and l.lance_minimo and l.lance_minimo > perfil.orcamento_max:
            continue
        c = l.model_copy()
        if c.valor_mercado and c.lance_minimo:
            c.desconto_pct = round((1 - c.lance_minimo / c.valor_mercado) * 100, 1)
        out.append(c)
    out.sort(key=lambda x: (x.desconto_pct is None, -(x.desconto_pct or 0)))
    return out[:limite]


def modelo_xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Lotes"
    cab = ["ID", "Categoria", "Descrição", "UF", "Cidade", "Tipo de leilão", "Avaliação",
           "Lance mínimo", "Valor de mercado", "Data", "Leiloeiro", "Comissão (%)", "Situação", "Link"]
    ws.append(cab)
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F3A5F")
    ws.append(["L001", "Veículos", "Honda Civic EXL 2019 - 62.000 km", "SP", "Campinas", "Judicial",
               48000, 24000, 78000, "12/12/2026", "João da Silva", 5, "Funcionando", ""])
    for col, w in zip("ABCDEFGHIJKLMN", [8, 14, 42, 6, 16, 16, 12, 14, 16, 12, 18, 12, 18, 30]):
        ws.column_dimensions[col].width = w
    ins = wb.create_sheet("Instruções")
    for t in ["Preencha a aba 'Lotes' (uma linha por lote).",
              "Obrigatórios: Descrição e Lance mínimo.",
              "Categoria: Veículos, Bens Diversos ou Imóvel.",
              "Tipo de leilão: Judicial, Receita Federal ou Extrajudicial.",
              "Valores em R$ (número ou texto 1.234,56). Valor de mercado = FIPE/avaliação de mercado.",
              "Os nomes das colunas podem variar um pouco; o sistema reconhece sinônimos."]:
        ins.append([t])
    ins.column_dimensions["A"].width = 90
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue()
