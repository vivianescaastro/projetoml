"""Pontos de atenção por tipo de leilão (Agentes 4, 5 e 6) — checklist determinístico com fundamento legal."""
from __future__ import annotations

import re

from .schemas import Edital, Ponto

# (id, título, severidade se alerta, regex, alerta_quando, explicação alerta, explicação ok, fundamento)
JUDICIAL = [
    ("leiloeiro", "Leiloeiro nomeado/credenciado", "alta", r"credenciad|nomead|matriculad|junta comercial|jucesp", "ausente",
     "Edital não demonstra que o leiloeiro é credenciado/nomeado — pode gerar nulidade.", "Leiloeiro credenciado/nomeado identificado.", "CPC arts. 879 e 880"),
    ("preco_vil", "Preço vil na 2ª praça", "alta", r"pre[çc]o vil|50\s*%|cinquenta por cento", "ausente",
     "Não há critério claro de preço vil; lance baixo pode ser anulado.", "Critério de preço vil (mín. 50% da avaliação) informado.", "CPC art. 891"),
    ("debitos", "Débitos do bem — sub-rogação", "alta", r"sub-?rog", "ausente",
     "Edital não esclarece sub-rogação: IPVA/IPTU/condomínio podem recair sobre o arrematante.", "Débitos sub-rogam no preço (arrematante recebe o bem livre).", "CPC art. 908 §1º; CTN art. 130 p.ú."),
    ("intimacao", "Intimação do executado, cônjuge e credores", "media", r"intima", "ausente",
     "Não consta intimação das partes — risco de nulidade da arrematação.", "Intimações mencionadas.", "CPC art. 889"),
    ("desistencia", "Multa por desistência / não pagamento", "media", r"multa|desist|20\s*%", "presente",
     "Há multa por desistência ou inadimplência — avalie capacidade de pagamento antes de arrematar.", "Sem penalidade expressa por desistência.", "CPC art. 897"),
    ("ocupacao", "Ocupação / imissão na posse", "media", r"ocupad|desocup|imiss[ãa]o|reintegra", "presente",
     "Bem pode estar ocupado; imissão na posse tem custo e prazo.", "Sem menção a ocupação.", "CPC art. 901 §1º"),
    ("estado", "Venda no estado / ad corpus", "baixa", r"no estado|ad corpus|sem garantia", "presente",
     "Venda no estado em que se encontra — sem garantia de qualidade; faça vistoria.", "Sem cláusula de venda no estado.", "CPC art. 886 V; CC art. 500"),
    ("desfazimento", "Desfazimento da arrematação", "baixa", r"embargos|anula|desfeita|invalid", "presente",
     "Edital menciona hipóteses de desfazimento: capital pode ficar retido até o fim do processo.", "Sem referência a desfazimento.", "CPC art. 903"),
]
RECEITA = [
    ("pagto_curto", "Prazo curto de pagamento", "media", r"[àa] vista|\d+\s*(?:\([^)]*\)\s*)?(?:horas|dias [úu]teis)", "presente",
     "Pagamento à vista/prazo curto: tenha o valor total disponível.", "Sem exigência de pagamento imediato.", "Edital RFB"),
    ("retirada", "Prazo de retirada e perda do bem", "alta", r"retirad|perdimento|perda", "ausente",
     "Edital não informa prazo de retirada — confirme antes de lançar.", "Prazo/regra de retirada informados.", "Portaria RFB / edital"),
    ("garantia", "Sem garantia / estado do bem", "media", r"no estado|sem garantia|não h[áa] garantia|vistoria", "presente",
     "Bens vendidos no estado, sem garantia ou devolução.", "Sem cláusula de ausência de garantia.", "Edital RFB"),
    ("tributos", "Tributos e armazenagem", "alta", r"armazen|icms|tribut|impost|taxa", "ausente",
     "Não há menção a tributos/armazenagem — pode haver custo oculto.", "Tributos/armazenagem mencionados (ver custos).", "Edital RFB"),
    ("habilitacao", "Cadastro e habilitação", "baixa", r"cadastr|habilita|e-?cac|cpf|cnpj", "ausente",
     "Exigências de cadastro/habilitação não identificadas.", "Exigências de cadastro/habilitação identificadas.", "Edital RFB"),
    ("restricoes", "Restrições de uso/revenda", "media", r"vedad|proib|restri|licença|anvisa|exército", "presente",
     "Há restrições de uso, revenda ou licenças específicas.", "Sem restrições de uso expressas.", "Edital RFB"),
    ("detran", "Baixa / regularização de veículo", "media", r"detran|baixa|sucata|chassi", "presente",
     "Veículo pode exigir regularização/baixa no Detran.", "Sem exigência de regularização.", "Edital RFB"),
]
EXTRAJUDICIAL = [
    ("fiduciaria", "Base legal da alienação fiduciária", "media", r"9\.514|fiduci", "ausente",
     "Edital não cita a Lei 9.514 — confirme se o leilão é regular.", "Lei 9.514/97 citada.", "Lei 9.514/97 art. 27"),
    ("preferencia", "Direito de preferência do devedor", "alta", r"prefer[êe]ncia|purg", "presente",
     "Devedor pode exercer preferência até a assinatura do auto — arrematação pode não se concretizar.", "Sem menção a preferência do devedor.", "Lei 9.514 art. 27 §2º-B"),
    ("debitos", "IPTU, condomínio e débitos do bem", "alta", r"iptu|condom[íi]nio|ipva|multas|licenciamento", "presente",
     "Há débitos citados — verifique se ficam por conta do arrematante.", "Sem débitos citados (confirme em certidões).", "CTN art. 130; Lei 9.514 art. 27 §8º"),
    ("ocupacao", "Ocupação e desocupação", "alta", r"ocupad|desocup|reintegra|imiss", "presente",
     "Bem ocupado — desocupação por conta do arrematante (prazo e custo imprevisíveis).", "Sem menção a ocupação.", "Lei 9.514 art. 30"),
    ("estado", "Venda no estado / vistoria", "media", r"no estado|sinistro|sucata|vistoria|ad corpus", "presente",
     "Venda no estado, sem garantia — vistoria é por conta do arrematante.", "Sem cláusula de venda no estado.", "CC art. 500"),
    ("leiloeiro", "Leiloeiro registrado", "media", r"junta comercial|jucesp|jucerja|jucemg|matr[íi]cula", "ausente",
     "Registro do leiloeiro na Junta Comercial não identificado.", "Registro do leiloeiro identificado.", "Decreto 21.981/1932"),
    ("custos_transf", "ITBI, escritura e registro", "media", r"itbi|escritura|registro|laud[êe]mio", "ausente",
     "Custos de transferência não detalhados.", "Custos de transferência mencionados (ver custos).", "Edital"),
]
LISTAS = {"Judicial": JUDICIAL, "Receita Federal": RECEITA, "Extrajudicial": EXTRAJUDICIAL}


def rodar_checklist(tipo: str, texto: str, ed: Edital) -> list[Ponto]:
    t = re.sub(r"\s+", " ", texto)
    pontos: list[Ponto] = []
    for _id, titulo, sev, rx, quando, msg_alerta, msg_ok, fund in LISTAS[tipo]:
        m = re.search(rx, t, re.I)
        achou = bool(m)
        trecho = t[max(0, m.start() - 70): m.end() + 130].strip() if m else None
        alerta = achou if quando == "presente" else not achou
        # refinos com os dados extraídos
        if _id == "preco_vil" and tipo == "Judicial" and ed.valor_avaliacao and ed.lance_minimo_2:
            pct = ed.lance_minimo_2 / ed.valor_avaliacao * 100
            if pct < 50:
                alerta, msg_alerta = True, f"Lance mínimo da 2ª praça ({pct:.0f}% da avaliação) está abaixo de 50% — configura preço vil."
            elif achou:
                alerta = False
        if _id == "debitos" and tipo == "Extrajudicial" and ed.debitos_responsabilidade:
            if "arrematante" in ed.debitos_responsabilidade.lower():
                alerta = True
            elif "sub-rog" in ed.debitos_responsabilidade.lower():
                alerta, msg_ok = False, "Débitos sub-rogam no preço."
        if _id == "debitos" and tipo == "Judicial" and ed.debitos_responsabilidade:
            dr = ed.debitos_responsabilidade
            if dr.startswith("Por conta"):
                alerta, sev, msg_alerta = True, "alta", "Edital coloca débitos por conta do arrematante — contraria a sub-rogação (CPC 908 §1º); confirme."
            elif dr.startswith("Misto"):
                alerta, sev, msg_alerta = True, "media", "Parte dos débitos sub-roga no preço e parte fica por conta do arrematante (ex.: multas posteriores) — some ao custo."
        pontos.append(Ponto(titulo=titulo, severidade=sev if alerta else "ok",
                            descricao=msg_alerta if alerta else msg_ok,
                            trecho=trecho if (achou and (alerta or quando == "ausente")) else (trecho if achou else None),
                            fundamento=fund))
    return pontos
