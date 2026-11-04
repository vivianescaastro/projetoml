"""Leitura de editais em PDF (texto nativo; PDFs escaneados vão direto para a IA)."""
from __future__ import annotations

import io
import re

import pdfplumber


def extrair_texto(pdf: bytes) -> tuple[str, int]:
    paginas = []
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        n = len(doc.pages)
        for p in doc.pages:
            paginas.append(p.extract_text() or "")
    texto = "\n".join(paginas)
    return texto, n


def normalizar(texto: str) -> str:
    texto = texto.replace(" ", " ")
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)       # hifenização de quebra de linha
    return re.sub(r"\s+", " ", texto).strip()
