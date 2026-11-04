"""Agente 9 — cálculo de custos, plano de pagamento (a quem / como pagar) e lance máximo."""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from .schemas import Edital, ItemCusto, Premissas


def _valor(item: ItemCusto, lance: float, avaliacao: Optional[float]) -> Optional[float]:
    if item.valor is None:
        return None
    if item.tipo == "pct_lance":
        return lance * item.valor / 100
    if item.tipo == "pct_avaliacao":
        return (avaliacao or lance) * item.valor / 100
    if item.tipo == "diaria":
        return item.valor * item.quantidade
    return item.valor


def montar_itens(ed: Edital, categoria: str, p: Premissas) -> list[ItemCusto]:
    itens: list[ItemCusto] = []
    forma = ed.forma_pagamento
    prazo = ed.prazo_pagamento_texto
    comissao = ed.comissao_pct
    if comissao is not None:
        itens.append(ItemCusto(nome="Comissão do leiloeiro", tipo="pct_lance", valor=comissao, pago_a="Leiloeiro",
                               quando=prazo, como=forma, origem="edital", fonte=ed.comissao_responsavel))
    else:
        itens.append(ItemCusto(nome="Comissão do leiloeiro (estimada)", tipo="pct_lance", valor=p.comissao_padrao_pct,
                               pago_a="Leiloeiro", quando=prazo, como=forma, origem="estimado",
                               obs="Não consta no edital; usado % padrão. Confirmar."))
    nomes = set()
    for c in ed.custos:
        c = c.model_copy()
        if c.tipo == "diaria":
            c.quantidade = max(0.0, p.dias_armazenamento - c.dias_gratis)
            c.obs = ((c.obs + " ") if c.obs else "") + f"Considerados {p.dias_armazenamento:.0f} dias de permanência (ajustável)."
        if c.quando is None:
            c.quando = prazo
        if c.como is None:
            c.como = forma
        itens.append(c); nomes.add(c.nome)
    # custos citados no edital sem valor: usa estimativa configurável (marcada como estimada)
    for c in itens:
        if c.valor is not None:
            continue
        n = c.nome.lower()
        if "itbi" in n:
            c.tipo, c.valor = "pct_lance", p.itbi_pct
        elif "escritura" in n or "registro" in n:
            c.tipo, c.valor = "pct_lance", p.registro_pct
        elif "transfer" in n:
            c.tipo, c.valor = "fixo", p.transferencia_veiculo
        else:
            continue
        c.origem = "estimado"
        c.obs = "Valor não consta no edital — estimativa ajustável nas premissas."
    # estimativas (só se o edital não trouxe e o tipo de bem pede)
    if categoria == "Imóvel":
        if not any("ITBI" in n for n in nomes):
            itens.append(ItemCusto(nome="ITBI (estimado)", tipo="pct_lance", valor=p.itbi_pct, pago_a="Prefeitura",
                                   origem="estimado", obs="Alíquota varia por município — ajuste nas premissas."))
        if not any("registro" in n.lower() or "escritura" in n.lower() for n in nomes):
            itens.append(ItemCusto(nome="Escritura e registro (estimado)", tipo="pct_lance", valor=p.registro_pct,
                                   pago_a="Cartório", origem="estimado", obs="Estimativa — varia por cartório/estado."))
    elif categoria == "Veículos" and not any("ransfer" in n for n in nomes):
        itens.append(ItemCusto(nome="Transferência / vistoria (estimado)", tipo="fixo", valor=p.transferencia_veiculo,
                               pago_a="Detran / despachante", origem="estimado", obs="Estimativa — ajuste nas premissas."))
    if p.reforma:
        itens.append(ItemCusto(nome="Reforma / reparos", tipo="fixo", valor=p.reforma, pago_a="Prestadores",
                               origem="usuario"))
    if p.outros_custos:
        itens.append(ItemCusto(nome="Outros custos informados", tipo="fixo", valor=p.outros_custos, origem="usuario"))
    return itens


def calcular(ed: Edital, categoria: str, p: Premissas, lance: float, valor_mercado: Optional[float]) -> dict:
    itens = montar_itens(ed, categoria, p)
    linhas, total_extras, pendentes = [], 0.0, []
    por_benef: "OrderedDict[str, float]" = OrderedDict()
    for it in itens:
        v = _valor(it, lance, ed.valor_avaliacao)
        linha = it.model_dump()
        linha["valor_calculado"] = None if v is None else round(v, 2)
        if v is None:
            pendentes.append(it.nome)
        elif it.computa_no_total:
            total_extras += v
            por_benef[it.pago_a or "Outros"] = por_benef.get(it.pago_a or "Outros", 0) + v
        linhas.append(linha)
    por_benef = OrderedDict([("Vendedor (lance arrematado)", lance), *por_benef.items()])
    total = lance + total_extras
    venda = p.valor_revenda or valor_mercado
    lucro = margem = None
    if venda:
        lucro = venda - total
        margem = lucro / total * 100
    # lance máximo para atingir a margem-alvo (itens percentuais escalam com o lance)
    fixos = sum((_valor(i, 0, ed.valor_avaliacao) or 0) for i in itens if i.computa_no_total and i.tipo in ("fixo", "diaria", "pct_avaliacao"))
    pct = sum((i.valor or 0) / 100 for i in itens if i.computa_no_total and i.tipo == "pct_lance" and i.valor is not None)
    return {
        "lance": round(lance, 2), "itens": linhas, "custos_extras": round(total_extras, 2),
        "custo_total": round(total, 2), "acrescimo_pct": round(total_extras / lance * 100, 1) if lance else None,
        "por_beneficiario": [{"pago_a": k, "valor": round(v, 2)} for k, v in por_benef.items()],
        "valor_venda_ref": venda, "lucro": None if lucro is None else round(lucro, 2),
        "margem_pct": None if margem is None else round(margem, 1),
        "pendentes": pendentes, "_fixos": fixos, "_pct": pct,
    }


def lance_maximo(res: dict, margem_alvo_pct: float) -> Optional[float]:
    venda = res.get("valor_venda_ref")
    if not venda:
        return None
    investimento_max = venda / (1 + margem_alvo_pct / 100)
    lm = (investimento_max - res["_fixos"]) / (1 + res["_pct"])
    return round(max(lm, 0), 2)
