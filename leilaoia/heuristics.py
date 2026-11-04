"""Extrator heurístico (sem IA) — usado quando não há ANTHROPIC_API_KEY ou a IA falha."""
from __future__ import annotations

import re
from typing import Optional

from .excel_db import norm_tipo, parse_brl
from .schemas import Edital, ItemCusto, Trecho

MONEY = r"R\$\s*(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
PCT = r"(\d+(?:,\d+)?)\s*%"
DATA = r"(\d{2}/\d{2}/\d{4})"


def _w(texto: str, m: re.Match, antes: int = 0, depois: int = 230) -> str:
    return texto[max(0, m.start() - antes): m.end() + depois]


def _corta(janela: str) -> str:
    """Corta a janela no fim da frase (ponto seguido de maiúscula)."""
    m = re.search(r"(?<!art)(?<!nº)(?<!n)\.\s+(?=[A-ZÀ-Ú])", janela)
    return janela[: m.start() + 1] if m else janela


def _trecho(texto: str, m: re.Match, n: int = 220) -> str:
    return _corta(texto[max(0, m.start() - 40): m.start() + n]).strip()


def _primeiro_valor(janela: str) -> Optional[float]:
    m = re.search(MONEY, janela)
    return parse_brl(m.group(1)) if m else None


def detectar_tipo(texto: str) -> tuple[Optional[str], dict]:
    t = texto.lower()
    pontos = {
        "Judicial": sum(t.count(k) for k in ["vara", "juízo", "juiz de direito", "código de processo civil",
                                              "cpc", "execução", "processo nº", "exequente", "penhora"]),
        "Receita Federal": sum(t.count(k) for k in ["receita federal", "rfb", "secretaria especial da receita",
                                                    "mercadorias apreendidas", "perdimento", "alfândega"]) * 2,
        "Extrajudicial": sum(t.count(k) for k in ["alienação fiduciária", "9.514", "credor fiduciário",
                                                  "leilão extrajudicial", "fiduciante", "banco", "instituição financeira"]),
    }
    melhor = max(pontos, key=pontos.get)
    return (melhor if pontos[melhor] > 0 else None), pontos


CUSTOS_DEF = [
    # nome, regex de palavra-chave, pago_a
    ("Armazenamento / pátio", r"armazen\w*|estadia|pátio|patio", "Depósito / pátio"),
    ("Taxa administrativa", r"taxa administrativa|taxa de administração|taxa de leiloaria|taxa de arrematação", "Leiloeiro"),
    ("Remoção / transporte do bem", r"remoção|remocao|guincho|transporte d[oe]", "Arrematante (transportadora)"),
    ("Custas / taxas judiciais", r"custas", "Tribunal / cartório"),
    ("Escritura, registro e emolumentos", r"emolumentos|escritura|registro d[aeo]|cartório de registro", "Cartório"),
    ("ITBI / laudêmio", r"\bITBI\b|laudêmio|laudemio", "Prefeitura / União"),
    ("Transferência / vistoria / despachante", r"transferência d[oe] (?:propriedade|veículo)|despachante|vistoria|\bDUT\b", "Detran / despachante"),
    ("Caução / sinal / depósito de garantia", r"cau[çc][ãa]o|\bsinal\b|depósito (?:prévio|de garantia|caução)", "Leiloeiro / conta judicial"),
    ("Tributos de importação / ICMS", r"\bICMS\b|imposto de importação|tributos federais", "Receita / Estado"),
]


def _item_custo(texto: str, nome: str, kw: str, pago: str) -> Optional[ItemCusto]:
    ocorrencias = list(re.finditer(kw, texto, re.I))
    if not ocorrencias:
        return None
    escolhido = None
    for m in ocorrencias:
        jan = _corta(texto[m.start(): m.start() + 260])
        if re.search(MONEY, jan) or re.search(PCT, jan):
            escolhido = (m, jan); break
    if escolhido is None:
        m = ocorrencias[0]
        escolhido = (m, _corta(texto[m.start(): m.start() + 260]))
    m, jan = escolhido
    valor = _primeiro_valor(jan)
    pm = re.search(PCT, jan)
    tipo, v, obs = "fixo", valor, None
    if valor is None and pm:
        tipo, v = "pct_lance", parse_brl(pm.group(1))
    elif valor is not None and re.search(r"por dia|diári|ao dia|/\s*dia", jan, re.I):
        tipo = "diaria"
    if valor is None and not pm:
        obs = "Valor não informado no edital — confirmar com o leiloeiro."
    item = ItemCusto(nome=nome, tipo=tipo, valor=v, pago_a=pago, fonte=jan.strip(), obs=obs)
    if tipo == "diaria":
        g = re.search(r"(\d+)\s*(?:\([^)]*\)\s*)?dias?\s+gratuit", texto, re.I) or \
            re.search(r"ap[óo]s o (\d+)[ºo°]?\s*dia", texto[max(0, m.start() - 90): m.start() + 260], re.I) or re.search(r"(\d+)\s*(?:\([^)]*\)\s*)?dias?[^.]{0,40}(?:isen|sem cobran)", jan, re.I)
        if g:
            item.dias_gratis = float(g.group(1))
            item.obs = f"{g.group(1)} dias sem cobrança; depois, diária."
    if "Caução" in nome:
        item.computa_no_total = not re.search(r"abat|compens|integr|dedu", jan, re.I)
        if not item.computa_no_total:
            item.obs = "Abatido do preço — não soma novamente no total."
    return item


def _debitos(t: str, ed: Edital) -> None:
    """Quem responde por IPVA/IPTU/condomínio/multas — analisa todas as frases relevantes."""
    frases = re.split(r"(?<!art)(?<!nº)(?<!n)(?<=[.;])\s+(?=[A-ZÀ-Ú])", t)
    kw = re.compile(r"d[ée]bitos?|d[íi]vidas?|IPVA|IPTU|condom[íi]nio|multas?|licenciamento", re.I)
    subrog, arrem = [], []
    for f in frases:
        if not kw.search(f):
            continue
        if re.search(r"sub-?rog", f, re.I):
            subrog.append(f)
        if re.search(r"arrematante|comprador|adquirente", f, re.I) and re.search(r"conta|responsab|a cargo|ficar", f, re.I):
            arrem.append(f)
    if subrog and arrem:
        ed.debitos_responsabilidade = "Misto: parte sub-roga no preço, parte por conta do arrematante"
    elif arrem:
        ed.debitos_responsabilidade = "Por conta do arrematante"
    elif subrog:
        ed.debitos_responsabilidade = "Sub-rogam no preço (quitados com o valor da arrematação)"
    elif any(kw.search(f) for f in frases):
        ed.debitos_responsabilidade = "Não esclarecido"
    for f in arrem:
        v = _primeiro_valor(f)
        ed.custos.append(ItemCusto(
            nome="Débitos a cargo do arrematante (IPVA/IPTU/condomínio/multas)", tipo="fixo", valor=v,
            pago_a="Prefeitura / condomínio / Detran", fonte=f.strip(),
            obs=None if v else "Valor não informado — pedir certidões de débitos."))


def varrer_valores(paginas: list[str]) -> list[Trecho]:
    """Lista, na ordem do edital, TODA passagem que cita valor em R$ ou percentual (texto literal + página)."""
    out, vistos = [], set()
    for n, pg in enumerate(paginas, 1):
        pg = re.sub(r"\s+", " ", pg)
        for fr in re.split(r"(?<!art)(?<!nº)(?<!n)(?<=[.;])\s+(?=[A-ZÀ-Ú0-9])", pg):
            vals = [m.group(0) for m in re.finditer(MONEY, fr)] + [m.group(0) for m in re.finditer(PCT, fr)]
            if vals and fr.strip() not in vistos:
                vistos.add(fr.strip())
                out.append(Trecho(pagina=n, trecho=fr.strip()[:500], valores=vals))
    return out


def localizar_pagina(trecho: Optional[str], paginas: list[str]) -> Optional[int]:
    if not trecho:
        return None
    chave = re.sub(r"\s+", " ", trecho).strip()[:45]
    for n, pg in enumerate(paginas, 1):
        if chave and chave in re.sub(r"\s+", " ", pg):
            return n
    return None


def extrair(texto_bruto: str, paginas: Optional[list[str]] = None) -> Edital:
    t = re.sub(r"\s+", " ", texto_bruto)
    ed = Edital()
    tipo, _ = detectar_tipo(t)
    ed.tipo_leilao = tipo

    if (m := re.search(r"(?:processo|autos)\s*(?:n[ºo°.]*)?\s*:?\s*(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})", t, re.I)):
        ed.processo = m.group(1)
    if (m := re.search(r"(\d+ª?\s*Vara[^,.;]{0,60})", t, re.I)):
        ed.juizo = m.group(1).strip()
    if (m := re.search(r"comarca de ([A-ZÀ-Ú][\wÀ-ú ]{2,30}?)(?:[,/.;]| - )", t, re.I)):
        ed.comarca = m.group(1).strip()
    NOME = (r"[A-ZÀ-Ú][\wÀ-ú.]+(?:\s+(?:d[aeo]s?\s+|e\s+)?[A-ZÀ-Ú][\wÀ-ú.]+){1,4}")
    if (m := re.search(r"leiloeir[oa](?: p[úu]blic[oa](?: oficial)?)?[:,]?\s*(?:Sr\.?\s*|Sra\.?\s*|Dr\.?\s*)?(" + NOME + ")", t)):
        ed.leiloeiro = m.group(1).strip()
    if re.search(r"credenciad|nomead[oa] (?:pelo|por)|cadastrad[oa] (?:no|junto)", t, re.I):
        ed.leiloeiro_credenciado = True
    if (m := re.search(r"(?:plataforma|site|portal)[^.]{0,40}?((?:www\.)?[\w-]+\.(?:com\.br|com|gov\.br|net\.br))", t, re.I)):
        ed.plataforma = m.group(1)

    # datas das praças
    if (m := re.search(r"(?:1[ªºa°]|primeir[ao])\s*(?:pra[çc]a|leil[ãa]o)[^0-9]{0,60}" + DATA, t, re.I)):
        ed.data_praca1 = m.group(1)
    if (m := re.search(r"(?:2[ªºa°]|segund[ao])\s*(?:pra[çc]a|leil[ãa]o)[^0-9]{0,60}" + DATA, t, re.I)):
        ed.data_praca2 = m.group(1)
    if not ed.data_praca1 and (m := re.search(DATA, t)):
        ed.data_praca1 = m.group(1)

    # valores
    if (m := re.search(r"avalia[çc][ãa]o[^R]{0,60}" + MONEY, t, re.I)) or \
       (m := re.search(r"avaliad[oa][^R]{0,60}" + MONEY, t, re.I)):
        ed.valor_avaliacao = parse_brl(m.group(1))
    if (m := re.search(r"(?:1[ªºa°]|primeir[ao])\s*(?:pra[çc]a|leil[ãa]o)[^R]{0,120}(?:lance m[íi]nimo|lance inicial|valor m[íi]nimo)?[^R]{0,40}" + MONEY, t, re.I)):
        ed.lance_minimo_1 = parse_brl(m.group(1))
    if (m := re.search(r"(?:2[ªºa°]|segund[ao])\s*(?:pra[çc]a|leil[ãa]o)[^R%]{0,160}" + MONEY, t, re.I)):
        ed.lance_minimo_2 = parse_brl(m.group(1))
    elif ed.valor_avaliacao and (m := re.search(r"(?:2[ªºa°]|segund[ao])\s*(?:pra[çc]a|leil[ãa]o)[^%]{0,200}?" + PCT, t, re.I)):
        ed.lance_minimo_2 = round(ed.valor_avaliacao * parse_brl(m.group(1)) / 100, 2)
    if not ed.lance_minimo_1 and ed.valor_avaliacao:
        ed.lance_minimo_1 = ed.valor_avaliacao

    # comissão do leiloeiro
    if (m := re.search(r"comiss[ãa]o[^%]{0,160}?" + PCT, t, re.I)) or (m := re.search(PCT + r"[^.]{0,80}comiss[ãa]o", t, re.I)):
        ed.comissao_pct = parse_brl(m.group(1))
        jan = _w(t, m, 80, 200)
        ed.comissao_responsavel = "arrematante" if re.search(r"arrematante|comprador", jan, re.I) else None

    # prazo de pagamento
    pm = re.search(r"(?:pagamento|pagar|depósito|deposito|quitação)[^.]{0,160}?(\d+)\s*(?:\([^)]*\)\s*)?(horas|dias [úu]teis|dias corridos|dias)", t, re.I)
    if pm:
        n = float(pm.group(1)); un = pm.group(2).lower()
        ed.prazo_pagamento_dias = round(n / 24, 2) if un.startswith("hora") else n
        ed.prazo_pagamento_texto = f"{pm.group(1)} {pm.group(2)}"
    ed.pagamento_avista = bool(re.search(r"[àa] vista", t, re.I)) or None
    if (m := re.search(r"parcel\w+[^.]{0,220}", t, re.I)):
        ed.parcelamento = _corta(m.group(0)).strip()
    fp = sorted({x.upper() if len(x) <= 4 else x.title() for x in
                 re.findall(r"\b(pix|ted|boleto|dep[óo]sito judicial|guia|darf|transfer[êe]ncia banc[áa]ria)\b", t, re.I)})
    ed.forma_pagamento = ", ".join(fp) or None

    # retirada
    if (m := re.search(r"retirad\w*[^.]{0,120}?(\d+)\s*(?:\([^)]*\)\s*)?dias", t, re.I)):
        ed.prazo_retirada_dias = float(m.group(1))

    _debitos(t, ed)
    for fr in re.split(r"(?<!art)(?<!nº)(?<!n)(?<=[.;])\s+(?=[A-ZÀ-Ú])", t):
        if re.search(r"ocupad|desocupa|imiss[ãa]o|reintegra", fr, re.I):
            ed.ocupacao = fr.strip()[:300]
            break

    # custos
    for nome, kw, pago in CUSTOS_DEF:
        it = _item_custo(t, nome, kw, pago)
        if it:
            ed.custos.append(it)
    # dedup de caução/sinal e armazenagem em tipo_leilao RF
    ed.custos = [c for c in ed.custos if not (c.nome.startswith("Tributos") and c.valor is None and c.obs is None)]
    if paginas:
        ed.valores_encontrados = varrer_valores(paginas)
        for c in ed.custos:
            c.pagina = localizar_pagina(c.fonte, paginas)
    # lacunas
    for campo, rot in [("comissao_pct", "Comissão do leiloeiro"), ("prazo_pagamento_dias", "Prazo de pagamento"),
                       ("valor_avaliacao", "Valor de avaliação"), ("data_praca1", "Data da 1ª praça/leilão"),
                       ("leiloeiro", "Nome do leiloeiro")]:
        if getattr(ed, campo) is None:
            ed.lacunas.append(f"{rot} não identificado(a) no texto — conferir no PDF.")
    return ed
