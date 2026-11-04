"""Geração do PDF do Dossiê (reportlab)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle)

AZUL = colors.HexColor("#1F3A5F")
COR = {"verde": colors.HexColor("#1B8A4B"), "amarelo": colors.HexColor("#C98A00"), "vermelho": colors.HexColor("#C0392B")}
SEV = {"alta": ("#C0392B", "ALTO"), "media": ("#C98A00", "MÉDIO"), "baixa": ("#3B7DD8", "BAIXO"), "ok": ("#1B8A4B", "OK")}


def brl(v):
    return "—" if v is None else "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _p(txt, st):
    return Paragraph(escape(str(txt)) if txt is not None else "—", st)


def gerar_pdf(d: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm,
                            bottomMargin=1.6 * cm, title="Dossiê de Leilão", author="LeilãoIA")
    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], textColor=AZUL, fontSize=18, spaceAfter=4)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], textColor=AZUL, fontSize=12.5, spaceBefore=12, spaceAfter=5)
    N = ParagraphStyle("N", parent=ss["BodyText"], fontSize=9, leading=12)
    S = ParagraphStyle("S", parent=N, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    C = ParagraphStyle("C", parent=N, alignment=TA_CENTER)
    v, f, cu, lote = d["veredito"], d["ficha"], d["custos"], d.get("lote")
    corv = COR[v["cor"]]
    story = [Paragraph(f"Dossiê de Leilão — decisão de compra" + (f"  ·  <font color='#C98A00'>{escape(d['id'])}</font>" if d.get("id") else ""), H1),
             Paragraph(f"Gerado em {escape(d['gerado_em'])} · arquivo: {escape(d['arquivo'])} · leilão {escape(d['tipo_leilao'])} · "
                       f"leitura {'por IA' if d['modo_leitura']=='ia' else 'por regras (revisar)'}", S), Spacer(1, 8)]
    banner = Table([[Paragraph(f"<font color='white' size=20><b>{v['decisao']}</b></font>", C)]], colWidths=[17.4 * cm], rowHeights=[1.5 * cm])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), corv), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
    story += [banner, Spacer(1, 6)]
    for titulo, itens, cor in [("Bloqueios", v["bloqueios"], "#C0392B"), ("Pontos de atenção", v["atencoes"], "#C98A00"), ("A favor", v["positivos"], "#1B8A4B")]:
        if itens:
            story.append(Paragraph(f"<font color='{cor}'><b>{titulo}</b></font>", N))
            story += [Paragraph("• " + escape(i), N) for i in itens]
            story.append(Spacer(1, 3))
    # resumo
    story.append(Paragraph("1. Resumo do negócio", H2))
    linhas = [["Bem", lote["descricao"] if lote else (f.get("descricao_bem") or "—")],
              ["Objetivo", f"{d['perfil']['objetivo']} · risco {d['perfil']['risco']} · orçamento {brl(d['perfil'].get('orcamento_max'))}"],
              ["Leiloeiro", f"{f.get('leiloeiro') or '—'} ({'credenciado' if f.get('leiloeiro_credenciado') else 'credenciamento não confirmado'})"],
              ["Processo / juízo", f"{f.get('processo') or '—'} {f.get('juizo') or ''}"],
              ["Avaliação", brl(f.get("valor_avaliacao"))],
              ["Lance simulado", brl(cu["lance"])],
              ["Custo total", f"{brl(cu['custo_total'])}  (+{cu['acrescimo_pct']}% sobre o lance)"],
              ["Valor de revenda/mercado", brl(cu.get("valor_venda_ref"))],
              ["Lucro / margem estimados", f"{brl(cu.get('lucro'))} / {cu['margem_pct']}%" if cu.get("margem_pct") is not None else "—"],
              ["Lance máximo recomendado", brl(cu.get("lance_maximo_recomendado"))]]
    t = Table([[_p(a, N), _p(b, N)] for a, b in linhas], colWidths=[4.6 * cm, 12.8 * cm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    if d.get("respostas"):
        story.append(Paragraph("Objetivo da compra — perguntas e respostas", H2))
        t = Table([[_p(r["pergunta"], N), _p(r["resposta"], N)] for r in d["respostas"]], colWidths=[10.4 * cm, 7.0 * cm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EEF2F7")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    # custos
    story.append(Paragraph("2. Custos detalhados", H2))
    rows = [["Item", "Base", "Valor (R$)", "Pago a / quando / como", "Origem"]]
    rows.append([_p("Lance arrematado", N), _p("lance", S), _p(brl(cu["lance"]), N), _p("Vendedor / leiloeiro", S), _p("—", S)])
    for i in cu["itens"]:
        base = {"fixo": "fixo", "pct_lance": f"{i['valor']}% do lance" if i["valor"] is not None else "% do lance",
                "pct_avaliacao": "% da avaliação", "diaria": f"{brl(i['valor'])} × {i['quantidade']:.0f} dias"}[i["tipo"]]
        val = brl(i["valor_calculado"]) if i["valor_calculado"] is not None else "A CONFIRMAR"
        if not i["computa_no_total"]:
            val += " (abatido)"
        det = " · ".join(x for x in [i.get("pago_a"), i.get("quando"), i.get("como")] if x) or "—"
        rows.append([_p(i["nome"] + (f"\n{i['obs']}" if i.get("obs") else "") + (f"\n“{i['fonte'][:220]}”" + (f" (p. {i['pagina']})" if i.get("pagina") else "") if i.get("fonte") and i["origem"] == "edital" else ""), N), _p(base, S), _p(val, N), _p(det, S), _p(i["origem"], S)])
    rows.append([_p("<b>CUSTO TOTAL</b>", N), "", _p(brl(cu["custo_total"]), N), "", ""])
    t = Table(rows, colWidths=[6.0 * cm, 2.7 * cm, 2.7 * cm, 4.2 * cm, 1.8 * cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EEF2F7")), ("FONTSIZE", (0, 0), (-1, 0), 8)]))
    story.append(t)
    story.append(Paragraph("Origem: <i>edital</i> = extraído do PDF; <i>estimado</i> = premissa ajustável (não consta no edital); <i>usuario</i> = informado por você.", S))
    story.append(Paragraph(f"Subtotal só com o que consta no edital: <b>{brl(cu['subtotal_edital'])}</b> · estimativas: {brl(cu['extras_estimados'])} · informados por você: {brl(cu['extras_usuario'])}", N))
    story.append(Paragraph("3. A quem pagar", H2))
    t = Table([["Beneficiário", "Valor"]] + [[_p(b["pago_a"], N), _p(brl(b["valor"]), N)] for b in cu["por_beneficiario"]], colWidths=[11 * cm, 6.4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey)]))
    story.append(t)
    if f.get("forma_pagamento") or f.get("prazo_pagamento_texto"):
        story.append(Paragraph(f"<b>Como pagar:</b> {escape(f.get('forma_pagamento') or '—')} · <b>prazo:</b> {escape(f.get('prazo_pagamento_texto') or '—')}"
                               + (f" · <b>parcelamento:</b> {escape(f['parcelamento'][:200])}" if f.get("parcelamento") else ""), N))
    # prazos
    story.append(Paragraph("4. Prazos", H2))
    if d["prazos"]:
        t = Table([["Data", "Evento", "Alerta"]] + [[_p(p["data"], N), _p(p["evento"], N), _p(p["alerta"] or "", S)] for p in d["prazos"]],
                  colWidths=[2.6 * cm, 8.8 * cm, 6.0 * cm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    else:
        story.append(Paragraph("Nenhum prazo identificado no edital.", N))
    # riscos
    story.append(Paragraph(f"5. Pontos de atenção — leilão {escape(d['tipo_leilao'])}", H2))
    for p in d["pontos"]:
        cor, rot = SEV[p["severidade"]]
        bloco = [Paragraph(f"<font color='{cor}'><b>[{rot}]</b></font> <b>{escape(p['titulo'])}</b> — {escape(p['descricao'])}", N)]
        meta = " · ".join(x for x in [("Fundamento: " + p["fundamento"]) if p.get("fundamento") else None] if x)
        if meta:
            bloco.append(Paragraph(escape(meta), S))
        if p.get("trecho") and p["severidade"] != "ok":
            bloco.append(Paragraph("“" + escape(p["trecho"][:300]) + "”", S))
        story.append(KeepTogether(bloco + [Spacer(1, 3)]))
    if d.get("divergencias"):
        story.append(Paragraph("<b>Divergências entre planilha e edital:</b> " + escape(" | ".join(d["divergencias"])), N))
    if f.get("lacunas"):
        story.append(Paragraph("<b>Não encontrado no edital:</b> " + escape(" | ".join(f["lacunas"])), N))
    if f.get("valores_encontrados"):
        story.append(Paragraph("6. Valores citados no edital (texto literal)", H2))
        t = Table([["Pág.", "Valores", "Trecho"]] + [[str(v.get("pagina") or "—"), _p(" · ".join(v["valores"]), S), _p(v["trecho"][:300], S)] for v in f["valores_encontrados"]],
                  colWidths=[1.0 * cm, 3.6 * cm, 12.8 * cm], repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(t)
    # etapas
    story.append(Paragraph("7. Trilha de decisão dos agentes", H2))
    t = Table([["#", "Agente", "Resultado"]] + [[("—" if e["status"] == "skipped" else str(e["id"] if e["id"] <= 10 else "")), _p(e["nome"] + (" (desviado)" if e["status"] == "skipped" else ""), N), _p(e["resumo"], S)] for e in d["etapas"]],
              colWidths=[0.8 * cm, 3.6 * cm, 13.0 * cm], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), AZUL), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    story += [Spacer(1, 10), Paragraph("Este dossiê é uma análise automatizada de apoio à decisão e não substitui a leitura integral do edital nem assessoria jurídica. "
                                       "Valores marcados como estimados dependem de confirmação.", S)]

    def rodape(c, _d):
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
        c.drawString(1.8 * cm, 1 * cm, "LeilãoIA — dossiê de decisão")
        c.drawRightString(A4[0] - 1.8 * cm, 1 * cm, f"pág. {c.getPageNumber()}")
    doc.build(story, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()
