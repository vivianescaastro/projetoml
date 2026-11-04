"""Cadeia orquestrada de 10 agentes. `executar` é um gerador de eventos consumidos pela interface."""
from __future__ import annotations

import time
import traceback
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

from . import costs, heuristics, llm
from .checklists import rodar_checklist
from .excel_db import norm_tipo
from .pdf_reader import extrair_paginas, normalizar
from .schemas import Edital, Lote, Perfil, Ponto, Premissas

NOMES = {
    1: "Objetivo da compra", 2: "Banco de dados", 3: "Tipo de leilão", 4: "Judicial",
    5: "Receita Federal", 6: "Extrajudicial", 7: "Análise de edital", 8: "Prazos",
    9: "Custos", 10: "Dossiê",
    21: "Veículos", 22: "Bens Diversos", 23: "Imóvel", 91: "A quem pagar / Como pagar",
}
CAT_ID = {"Veículos": 21, "Bens Diversos": 22, "Imóvel": 23}
ESPECIALISTA = {"Judicial": 4, "Receita Federal": 5, "Extrajudicial": 6}


def _brl(v) -> str:
    return "—" if v is None else "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sn(v: Optional[bool], sim: str = "Sim", nao: str = "Não") -> str:
    return "Não respondida" if v is None else (sim if v else nao)


def respostas_do_perfil(p: Perfil) -> list[dict]:
    """Agente 1: o objetivo da compra em formato de perguntas e respostas (aparece no dossiê, PDF e planilha)."""
    obj = {"revenda": "Revender com lucro", "investimento": "Investir e manter (renda ou valorização)", "uso": "Uso próprio"}[p.objetivo]
    prazo = {3: "Até 3 meses", 6: "Até 6 meses", 12: "Até 12 meses"}.get(p.prazo_revenda_meses or 0, "Sem pressa" if p.prazo_revenda_meses == 0 else "Não respondida")
    qa = [
        ("O que você pretende fazer com o bem?", obj),
        ("Qual tipo de bem você procura?", "Qualquer" if p.categoria in ("Todas", "", None) else p.categoria),
        ("Em que tipo de leilão vai participar?", "Ainda não sei" if p.tipo_leilao in ("Todos", "", None) else p.tipo_leilao),
        ("Qual o máximo que pode gastar no total (lance + comissão, taxas e impostos)?", _brl(p.orcamento_max) if p.orcamento_max else "Sem limite informado"),
        ("Em qual estado (UF) quer comprar?", p.uf or "Qualquer"),
    ]
    if p.objetivo != "uso":
        qa += [("Qual o lucro mínimo que compensa (% sobre o que será investido)?", f"{p.margem_alvo_pct:g}%"),
               ("Em quanto tempo precisa revender ou liberar o bem?", prazo)]
    qa += [
        ("Terá o valor total disponível para pagar em até 2 dias úteis?", _sn(p.pagamento_imediato, "Sim", "Não — só consigo parcelado")),
        ("Aceita comprar bem ocupado (pode exigir ação para desocupar)?", _sn(p.aceita_ocupado)),
        ("Aceita assumir débitos do bem (IPVA, IPTU, condomínio, multas)?", _sn(p.aceita_debitos)),
        ("Quanto risco aceita nesta compra?", {"baixo": "Pouco risco", "medio": "Risco moderado", "alto": "Aceito risco alto"}[p.risco]),
    ]
    return [{"pergunta": q, "resposta": r} for q, r in qa]


def _categoria(lote: Optional[Lote], perfil: Perfil, texto: str) -> tuple[str, str]:
    import re
    if lote and lote.categoria in CAT_ID:
        return lote.categoria, "banco de dados"
    if perfil.categoria in CAT_ID:
        return perfil.categoria, "perfil do comprador"
    t = texto.lower()
    if re.search(r"matr[íi]cula|im[óo]vel|apartamento|terreno|\bcasa\b|sala comercial", t):
        return "Imóvel", "texto do edital"
    if re.search(r"ve[íi]culo|placa|chassi|renavam|motocicleta|\bmoto\b", t):
        return "Veículos", "texto do edital"
    return "Bens Diversos", "padrão"


def _data(s: Optional[str]) -> Optional[date]:
    try:
        return datetime.strptime(s, "%d/%m/%Y").date() if s else None
    except ValueError:
        return None


def _ev(id_, status, resumo="", dados=None, t0=None):
    e = {"type": "agent", "id": id_, "nome": NOMES[id_], "status": status, "resumo": resumo}
    if dados is not None:
        e["dados"] = dados
    if t0 is not None:
        e["seg"] = round(time.time() - t0, 2)
    return e


def executar(pdf: bytes, nome_arquivo: str, lote: Optional[Lote], perfil: Perfil,
             prem: Premissas, tipo_manual: Optional[str] = None) -> Iterator[dict]:
    etapas: list[dict] = []

    def fim(id_, resumo, dados=None, t0=None, status="done"):
        etapas.append({"id": id_, "nome": NOMES[id_], "status": status, "resumo": resumo})
        return _ev(id_, status, resumo, dados, t0)

    try:
        paginas_txt = extrair_paginas(pdf)            # leitura do PDF (insumo dos agentes 2 e 3)
        paginas = len(paginas_txt)
        texto_n = normalizar("\n".join(paginas_txt))
        escaneado = len(texto_n) < 200 * max(paginas, 1) * 0.2

        # ---- Agente 1
        t0 = time.time(); yield _ev(1, "running")
        qa = respostas_do_perfil(perfil)
        r = (f"{len(qa)} perguntas respondidas. Objetivo: {perfil.objetivo} · orçamento {_brl(perfil.orcamento_max)} · risco {perfil.risco}"
             + (f" · margem-alvo {perfil.margem_alvo_pct:.0f}%" if perfil.objetivo != "uso" else ""))
        yield fim(1, r, {**perfil.model_dump(), "respostas": qa}, t0)

        # ---- Agente 2
        t0 = time.time(); yield _ev(2, "running")
        if lote:
            r = f"Lote {lote.id} da base: {lote.descricao} — lance mín. {_brl(lote.lance_minimo)}" + \
                (f" ({lote.desconto_pct:.0f}% abaixo do mercado)" if lote.desconto_pct is not None else "")
            yield fim(2, r, lote.model_dump(), t0)
        else:
            yield fim(2, "Lote avulso: análise feita só com o edital (sem item da base).", None, t0)
        # ---- ramo de categoria do banco de dados: Veículos | Bens Diversos | Imóvel
        categoria, origem_cat = _categoria(lote, perfil, texto_n)
        for nome_cat, cid in CAT_ID.items():
            if nome_cat == categoria:
                yield _ev(cid, "running")
                yield fim(cid, f"Categoria: {categoria} (fonte: {origem_cat}).", {"categoria": categoria}, None)
            else:
                yield fim(cid, "Categoria não aplicável a este lote.", None, None, status="skipped")

        # ---- Agente 3 (decisão: tipo de leilão)
        t0 = time.time(); yield _ev(3, "running")
        tipo_edital, pontos_tipo = heuristics.detectar_tipo(texto_n)
        tipo = tipo_manual or (lote.tipo_leilao if lote and lote.tipo_leilao else None) or tipo_edital
        origem = "informado pelo usuário" if tipo_manual else ("planilha" if lote and lote.tipo_leilao else "texto do edital")
        alertas_tipo = []
        if tipo is None and escaneado and llm.disponivel():
            tipo = "Judicial"; origem = "padrão (PDF escaneado, sem texto)"
        if tipo is None:
            raise ValueError("Não foi possível identificar o tipo de leilão. Selecione-o manualmente.")
        if tipo_edital and tipo_edital != tipo and not tipo_manual:
            alertas_tipo.append(f"Divergência: base/usuário diz '{tipo}', mas o texto do edital sugere '{tipo_edital}'.")
        yield fim(3, f"Tipo: {tipo} (fonte: {origem}). PDF com {paginas} pág."
                  + (" ⚠ " + alertas_tipo[0] if alertas_tipo else ""),
                  {"tipo": tipo, "pontuacao_texto": pontos_tipo, "alertas": alertas_tipo}, t0)

        # ---- Agentes 4/5/6 (especialista do tipo escolhido; os outros são desviados)
        esp = ESPECIALISTA[tipo]
        for k in (4, 5, 6):
            if k != esp:
                yield fim(k, "Ramo não utilizado neste leilão.", None, None, status="skipped")
        t0 = time.time(); yield _ev(esp, "running")
        modo, aviso_modo = "heuristico", None
        ed: Optional[Edital] = None
        if llm.disponivel():
            try:
                ed = llm.extrair_edital_pdf(pdf, tipo)
                modo = "ia"
            except Exception as exc:  # noqa: BLE001
                aviso_modo = f"IA indisponível ({type(exc).__name__}); usado extrator por regras."
        if ed is None:
            if escaneado:
                aviso_modo = "PDF sem texto (escaneado): configure ANTHROPIC_API_KEY para leitura por IA/OCR."
            ed = heuristics.extrair("\n".join(paginas_txt), paginas_txt)
        if modo == "ia":                              # complementa a leitura da IA com a varredura literal
            if not ed.valores_encontrados:
                ed.valores_encontrados = heuristics.varrer_valores(paginas_txt)
            for c in ed.custos:
                if c.pagina is None:
                    c.pagina = heuristics.localizar_pagina(c.fonte, paginas_txt)
        ed.tipo_leilao = tipo
        checklist = rodar_checklist(tipo, texto_n, ed)
        n_alerta = sum(1 for p in checklist if p.severidade != "ok")
        yield fim(esp, f"{len(checklist)} pontos conferidos para leilão {tipo}: {n_alerta} alertas "
                  f"({'leitura por IA' if modo == 'ia' else 'leitura por regras'}).",
                  {"checklist": [p.model_dump() for p in checklist], "modo": modo, "aviso": aviso_modo}, t0)

        # ---- Agente 7 (consolida e cruza com a base)
        t0 = time.time(); yield _ev(7, "running")
        diverg: list[str] = []
        if lote:
            if lote.valor_avaliacao and ed.valor_avaliacao and abs(lote.valor_avaliacao - ed.valor_avaliacao) > 1:
                diverg.append(f"Avaliação na base ({_brl(lote.valor_avaliacao)}) ≠ edital ({_brl(ed.valor_avaliacao)}).")
            if lote.lance_minimo and ed.lance_minimo_1 and abs(lote.lance_minimo - ed.lance_minimo_1) > 1 \
                    and (not ed.lance_minimo_2 or abs(lote.lance_minimo - ed.lance_minimo_2) > 1):
                diverg.append(f"Lance mínimo na base ({_brl(lote.lance_minimo)}) ≠ edital ({_brl(ed.lance_minimo_1)}).")
            if lote.comissao_pct and ed.comissao_pct and abs(lote.comissao_pct - ed.comissao_pct) > 0.01:
                diverg.append(f"Comissão na base ({lote.comissao_pct:g}%) ≠ edital ({ed.comissao_pct:g}%).")
        diverg += alertas_tipo
        pontos: list[Ponto] = list(checklist)
        titulos = {p.titulo.lower() for p in pontos}
        for p in ed.pontos_atencao:                      # pontos adicionais encontrados pela IA
            if p.titulo.lower() not in titulos:
                pontos.append(p)
        for d in diverg:
            pontos.append(Ponto(titulo="Divergência base × edital", severidade="media", descricao=d))
        ordem = {"alta": 0, "media": 1, "baixa": 2, "ok": 3}
        pontos.sort(key=lambda p: ordem[p.severidade])
        contagem = {s: sum(1 for p in pontos if p.severidade == s) for s in ordem}
        yield fim(7, f"Ficha consolidada: {contagem['alta']} riscos altos, {contagem['media']} médios, "
                  f"{contagem['baixa']} baixos; {len(ed.lacunas)} lacunas; {len(diverg)} divergências.",
                  {"ficha": ed.model_dump(), "contagem": contagem, "divergencias": diverg}, t0)

        # ---- Agente 8 (prazos)
        t0 = time.time(); yield _ev(8, "running")
        prazos = _prazos(ed, lote)
        yield fim(8, f"{len(prazos)} marcos no cronograma"
                  + (f"; {sum(1 for p in prazos if p['alerta'])} com alerta." if any(p['alerta'] for p in prazos) else "."),
                  {"cronograma": prazos}, t0)

        # ---- Agente 9 (custos)
        t0 = time.time(); yield _ev(9, "running")
        lance = prem.lance
        if lance is None:
            lance = (ed.lance_minimo_2 if prem.praca == 2 else ed.lance_minimo_1) or (lote.lance_minimo if lote else None)
        if not lance:
            raise ValueError("Informe o lance planejado (não foi possível inferir o lance mínimo do edital).")
        ed.categoria_bem = categoria
        custos = costs.calcular(ed, categoria, prem, lance, lote.valor_mercado if lote else None)
        lm = costs.lance_maximo(custos, perfil.margem_alvo_pct) if perfil.objetivo != "uso" else None
        custos["lance_maximo_recomendado"] = lm
        custos.pop("_fixos", None); custos.pop("_pct", None)
        yield fim(9, f"Lance {_brl(lance)} → custo total {_brl(custos['custo_total'])} "
                  f"(+{custos['acrescimo_pct']}% sobre o lance)"
                  + (f"; margem {custos['margem_pct']}%" if custos["margem_pct"] is not None else "") + ".",
                  custos, t0)

        # ---- saída do Agente 9: a quem pagar / como pagar
        t0 = time.time(); yield _ev(91, "running")
        benef = custos["por_beneficiario"]
        pagto = {"beneficiarios": benef, "forma": ed.forma_pagamento, "prazo": ed.prazo_pagamento_texto,
                 "parcelamento": ed.parcelamento,
                 "itens": [{"item": i["nome"], "pago_a": i.get("pago_a"), "quando": i.get("quando"), "como": i.get("como"),
                            "valor": i["valor_calculado"]} for i in custos["itens"] if i["computa_no_total"]]}
        yield fim(91, "A quem: " + "; ".join(f"{b['pago_a']} {_brl(b['valor'])}" for b in benef)
                  + f". Como: {ed.forma_pagamento or 'não informado'} · prazo {ed.prazo_pagamento_texto or 'não informado'}.",
                  pagto, t0)

        # ---- Agente 10 (dossiê e veredito)
        t0 = time.time(); yield _ev(10, "running")
        ver = _veredito(perfil, ed, pontos, custos, prazos, modo, lm, lance)
        etapas.append({"id": 10, "nome": NOMES[10], "status": "done", "resumo": f"Veredito: {ver['decisao']}"})
        dossie = {
            "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "arquivo": nome_arquivo, "modo_leitura": modo, "aviso_modo": aviso_modo,
            "perfil": perfil.model_dump(), "respostas": respostas_do_perfil(perfil), "lote": lote.model_dump() if lote else None,
            "premissas": prem.model_dump(), "tipo_leilao": tipo, "ficha": ed.model_dump(),
            "pontos": [p.model_dump() for p in pontos], "divergencias": diverg,
            "prazos": prazos, "custos": custos, "veredito": ver, "etapas": etapas,
        }
        yield _ev(10, "done", f"Veredito: {ver['decisao']}", None, t0)
        yield {"type": "dossie", "dados": dossie}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "erro", "mensagem": str(exc) or type(exc).__name__, "detalhe": traceback.format_exc(limit=3)}


def _prazos(ed: Edital, lote: Optional[Lote]) -> list[dict]:
    hoje = date.today()
    out: list[dict] = []

    def add(d: Optional[date], evento: str, alerta: Optional[str] = None, extra: str = ""):
        if d:
            if d < hoje and not alerta:
                alerta = "Data já passou — confirme se o leilão ainda está aberto."
            out.append({"data": d.strftime("%d/%m/%Y"), "evento": evento + extra, "alerta": alerta})

    d1 = _data(ed.data_praca1) or (_data(lote.data_leilao) if lote else None)
    d2 = _data(ed.data_praca2)
    add(d1, "1ª praça / 1º leilão", None, f" — lance mín. {_brl(ed.lance_minimo_1)}" if ed.lance_minimo_1 else "")
    add(d2, "2ª praça / 2º leilão", None, f" — lance mín. {_brl(ed.lance_minimo_2)}" if ed.lance_minimo_2 else "")
    base = d1 or d2
    if ed.prazo_pagamento_dias is not None:
        n = ed.prazo_pagamento_dias
        alerta = "Prazo de pagamento muito curto — deixe o valor total disponível." if n <= 2 else None
        lim = (base + timedelta(days=int(n))) if base else None
        if lim:
            add(lim, f"Pagamento limite ({ed.prazo_pagamento_texto})", alerta)
        else:
            out.append({"data": "—", "evento": f"Prazo de pagamento: {ed.prazo_pagamento_texto}", "alerta": alerta})
        if ed.parcelamento:
            out.append({"data": "—", "evento": "Parcelamento previsto: " + ed.parcelamento[:140], "alerta": None})
    if ed.prazo_retirada_dias is not None:
        ref = (base + timedelta(days=int(ed.prazo_pagamento_dias or 0))) if base else None
        alerta = "Retirada fora do prazo pode gerar perda do bem/armazenagem." if ed.prazo_retirada_dias <= 10 else None
        if ref:
            add(ref + timedelta(days=int(ed.prazo_retirada_dias)), f"Retirada limite ({ed.prazo_retirada_dias:.0f} dias após pagamento)", alerta)
        else:
            out.append({"data": "—", "evento": f"Prazo de retirada: {ed.prazo_retirada_dias:.0f} dias", "alerta": alerta})
    for c in ed.custos:
        if c.tipo == "diaria" and c.dias_gratis:
            out.append({"data": "—", "evento": f"Armazenamento: {c.dias_gratis:.0f} dias gratuitos, depois {_brl(c.valor)}/dia", "alerta": None})
    return out


def _veredito(perfil: Perfil, ed: Edital, pontos: list[Ponto], custos: dict, prazos: list[dict],
              modo: str, lance_max: Optional[float], lance: float) -> dict:
    bloqueios: list[str] = []
    atencoes: list[str] = []
    positivos: list[str] = []
    altas = [p for p in pontos if p.severidade == "alta"]
    limites = {"baixo": (1, 1), "medio": (3, 1), "alto": (4, 2)}[perfil.risco]  # (não comprar >=, atenção >=)
    if len(altas) >= limites[0]:
        bloqueios.append(f"{len(altas)} riscos altos ({'; '.join(p.titulo for p in altas[:4])}) — acima da sua tolerância ({perfil.risco}).")
    elif len(altas) >= limites[1]:
        atencoes.append(f"{len(altas)} risco(s) alto(s): {'; '.join(p.titulo for p in altas)}.")
    else:
        positivos.append("Nenhum risco alto relevante para o seu perfil.")
    if perfil.orcamento_max and custos["custo_total"] > perfil.orcamento_max:
        bloqueios.append(f"Custo total {_brl(custos['custo_total'])} excede o orçamento {_brl(perfil.orcamento_max)}.")
    elif perfil.orcamento_max:
        positivos.append(f"Custo total dentro do orçamento ({_brl(custos['custo_total'])}).")
    # ---- respostas de aceitação do Agente 1 × o que o edital diz
    ocup = [p for p in pontos if "ocupa" in p.titulo.lower() and p.severidade != "ok"]
    deb = (ed.debitos_responsabilidade or "").startswith(("Por conta", "Misto")) or any(
        c["nome"].startswith("Débitos a cargo") for c in custos["itens"])
    if ocup and perfil.aceita_ocupado is False:
        bloqueios.append("O edital indica bem ocupado/desocupação e você respondeu que não aceita bem ocupado.")
    elif ocup and perfil.prazo_revenda_meses and perfil.prazo_revenda_meses <= 3:
        atencoes.append("Bem possivelmente ocupado e você precisa revender em até 3 meses: a desocupação pode estourar o prazo.")
    if deb and perfil.aceita_debitos is False:
        bloqueios.append("Há débitos do bem por conta do arrematante e você respondeu que não aceita assumir débitos.")
    if ed.prazo_pagamento_dias is not None and ed.prazo_pagamento_dias <= 2 and perfil.pagamento_imediato is False:
        (atencoes if ed.parcelamento else bloqueios).append(
            f"Pagamento exigido em {ed.prazo_pagamento_texto} e você não terá o valor total disponível"
            + (" — o edital cita parcelamento; confirme as condições (normalmente exige proposta antes do leilão)." if ed.parcelamento else "."))
    m = custos.get("margem_pct")
    if perfil.objetivo != "uso" and m is not None:
        if m < 0:
            bloqueios.append(f"Margem negativa ({m:.1f}%) sobre o valor de referência {_brl(custos['valor_venda_ref'])}.")
        elif m < perfil.margem_alvo_pct:
            atencoes.append(f"Margem {m:.1f}% abaixo da meta de {perfil.margem_alvo_pct:.0f}%."
                            + (f" Lance máximo recomendado: {_brl(lance_max)}." if lance_max else ""))
        else:
            positivos.append(f"Margem estimada {m:.1f}% (meta {perfil.margem_alvo_pct:.0f}%).")
    elif perfil.objetivo == "uso" and custos.get("valor_venda_ref"):
        desc = (1 - custos["custo_total"] / custos["valor_venda_ref"]) * 100
        (positivos if desc > 0 else atencoes).append(f"Custo total {desc:+.1f}% vs. valor de mercado.")
    elif m is None and perfil.objetivo != "uso":
        atencoes.append("Sem valor de mercado/revenda para calcular margem.")
    if lance_max is not None and lance > lance_max:
        atencoes.append(f"Seu lance ({_brl(lance)}) está acima do lance máximo recomendado ({_brl(lance_max)}).")
    if custos["pendentes"]:
        atencoes.append("Custos sem valor no edital: " + ", ".join(custos["pendentes"]) + ".")
    if ed.lacunas:
        atencoes.append("Dados não encontrados no edital: " + "; ".join(l.split(" não")[0] for l in ed.lacunas) + ".")
    if any(p["alerta"] for p in prazos):
        atencoes.append("Alertas de prazo: " + " | ".join(p["alerta"] for p in prazos if p["alerta"])[:300])
    if modo != "ia":
        atencoes.append("Ficha extraída por regras (sem IA): revise os valores no PDF antes de decidir.")
    if bloqueios:
        decisao, cor = "NÃO COMPRAR", "vermelho"
    elif atencoes:
        decisao, cor = "ATENÇÃO", "amarelo"
    else:
        decisao, cor = "COMPRAR", "verde"
    return {"decisao": decisao, "cor": cor, "bloqueios": bloqueios, "atencoes": atencoes, "positivos": positivos,
            "lance_maximo_recomendado": lance_max}
