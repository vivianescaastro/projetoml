"""API + interface web do LeilãoIA."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import agents, excel_db, llm
from .dossie_pdf import gerar_pdf
from .schemas import Lote, Perfil, Premissas

ROOT = Path(__file__).parent
MAX_PDF = 25 * 1024 * 1024
MAX_XLSX = 10 * 1024 * 1024
app = FastAPI(title="LeilãoIA", version="1.0")


@app.get("/api/health")
def health():
    return {"ok": True, "ia": llm.disponivel(), "modelo": llm.MODELO if llm.disponivel() else None}


@app.get("/api/base/modelo")
def baixar_modelo():
    return Response(excel_db.modelo_xlsx(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": 'attachment; filename="modelo_base_leiloes.xlsx"'})


@app.post("/api/base")
async def enviar_base(arquivo: UploadFile = File(...)):
    dados = await arquivo.read()
    if len(dados) > MAX_XLSX:
        raise HTTPException(413, "Planilha acima de 10 MB.")
    try:
        bid, base = excel_db.salvar_upload(dados, arquivo.filename or "base.xlsx")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Planilha inválida: {exc}")
    return {"base_id": bid, "nome": base.nome, "lotes": len(base.lotes), "avisos": base.avisos[:30]}


@app.get("/api/base/{base_id}")
def info_base(base_id: str):
    try:
        base = excel_db.carregar_base(base_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(404, str(exc))
    return {"base_id": base_id, "nome": base.nome, "lotes": len(base.lotes), "avisos": base.avisos[:30]}


@app.post("/api/lotes/buscar")
def buscar_lotes(corpo: dict):
    try:
        perfil = Perfil.model_validate(corpo.get("perfil") or {})
        base = excel_db.carregar_base(corpo.get("base_id") or "exemplo")
    except (ValidationError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(422, str(exc))
    lotes = excel_db.buscar(base, perfil)
    return {"perfil": perfil.model_dump(), "total_base": len(base.lotes), "lotes": [l.model_dump() for l in lotes]}


@app.post("/api/analise")
async def analisar(edital: UploadFile = File(...), perfil: str = Form("{}"), premissas: str = Form("{}"),
                   lote: Optional[str] = Form(None), tipo_leilao: Optional[str] = Form(None)):
    pdf = await edital.read()
    if not pdf.startswith(b"%PDF"):
        raise HTTPException(422, "O arquivo enviado não é um PDF.")
    if len(pdf) > MAX_PDF:
        raise HTTPException(413, "PDF acima de 25 MB.")
    try:
        p = Perfil.model_validate(json.loads(perfil or "{}"))
        pr = Premissas.model_validate(json.loads(premissas or "{}"))
        lt = Lote.model_validate(json.loads(lote)) if lote else None
    except (ValidationError, json.JSONDecodeError) as exc:
        raise HTTPException(422, f"Parâmetros inválidos: {exc}")
    tipo = excel_db.norm_tipo(tipo_leilao) if tipo_leilao else None

    def gerar():
        for ev in agents.executar(pdf, edital.filename or "edital.pdf", lt, p, pr, tipo):
            yield json.dumps(ev, ensure_ascii=False) + "\n"

    return StreamingResponse(gerar(), media_type="application/x-ndjson", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@app.post("/api/dossie/pdf")
def dossie_pdf(dossie: dict):
    try:
        pdf = gerar_pdf(dossie)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(422, f"Não foi possível gerar o PDF: {exc}")
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="dossie_leilao.pdf"'})


@app.get("/api/exemplos")
def exemplos():
    return [{"arquivo": p.name, "url": f"/exemplos/{p.name}"} for p in sorted((ROOT / "samples").glob("*.pdf"))]


app.mount("/exemplos", StaticFiles(directory=ROOT / "samples"), name="exemplos")
app.mount("/", StaticFiles(directory=ROOT / "static", html=True), name="static")
