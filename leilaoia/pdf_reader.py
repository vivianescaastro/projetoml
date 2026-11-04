"""Leitura de editais em PDF (texto nativo; PDFs escaneados vão direto para a IA)."""
from __future__ import annotations

import io
import re

import pdfplumber


def extrair_paginas(pdf: bytes) -> list[str]:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return [p.extract_text() or "" for p in doc.pages]


def extrair_texto(pdf: bytes) -> tuple[str, int]:
    paginas = extrair_paginas(pdf)
    return "\n".join(paginas), len(paginas)


def normalizar(texto: str) -> str:
    texto = texto.replace(" ", " ")
    texto = re.sub(r"-\n(?=[a-zà-ú])", "", texto)       # hifenização de quebra de linha
    return re.sub(r"\s+", " ", texto).strip()
