"""Contratos de dados trocados entre os agentes (validados com Pydantic)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

TIPOS = ("Judicial", "Receita Federal", "Extrajudicial")


class Perfil(BaseModel):
    """Saída do Agente 1 — objetivo da compra."""
    objetivo: Literal["revenda", "uso", "investimento"] = "revenda"
    orcamento_max: Optional[float] = None
    categoria: str = "Todas"          # Veículos | Bens Diversos | Imóvel | Todas
    uf: Optional[str] = None
    tipo_leilao: str = "Todos"        # Judicial | Receita Federal | Extrajudicial | Todos
    risco: Literal["baixo", "medio", "alto"] = "medio"
    margem_alvo_pct: float = 20.0
    # perguntas de aceitação (None = não respondida → sem restrição)
    pagamento_imediato: Optional[bool] = None   # terá o valor total em até 2 dias úteis?
    aceita_ocupado: Optional[bool] = None       # aceita bem ocupado?
    aceita_debitos: Optional[bool] = None       # aceita assumir débitos do bem?
    prazo_revenda_meses: Optional[int] = None   # em quanto tempo precisa revender / liberar o bem


class Lote(BaseModel):
    id: str
    categoria: str = "Bens Diversos"
    descricao: str = ""
    uf: Optional[str] = None
    cidade: Optional[str] = None
    tipo_leilao: Optional[str] = None
    valor_avaliacao: Optional[float] = None
    lance_minimo: Optional[float] = None
    valor_mercado: Optional[float] = None   # FIPE / mercado: base para revenda e margem
    data_leilao: Optional[str] = None
    leiloeiro: Optional[str] = None
    comissao_pct: Optional[float] = None
    situacao: Optional[str] = None
    link: Optional[str] = None
    desconto_pct: Optional[float] = None    # calculado pelo Agente 2


class Trecho(BaseModel):
    """Passagem literal do edital com os valores (R$ / %) que ela cita."""
    pagina: Optional[int] = None
    trecho: str
    valores: list[str] = Field(default_factory=list)


class ItemCusto(BaseModel):
    nome: str
    tipo: Literal["fixo", "pct_lance", "pct_avaliacao", "diaria"] = "fixo"
    valor: Optional[float] = None           # R$ (fixo/diária) ou % (pct_*)
    quantidade: float = 1                   # dias cobrados (diária) — calculado pelo Agente 9
    dias_gratis: float = 0                  # dias sem cobrança (armazenamento)
    pago_a: Optional[str] = None
    quando: Optional[str] = None
    como: Optional[str] = None
    origem: Literal["edital", "estimado", "usuario"] = "edital"
    fonte: Optional[str] = None             # trecho LITERAL do edital que sustenta o custo
    pagina: Optional[int] = None            # página do PDF onde está o trecho
    computa_no_total: bool = True           # caução abatida do preço não soma de novo
    obs: Optional[str] = None


class Ponto(BaseModel):
    titulo: str
    severidade: Literal["alta", "media", "baixa", "ok"] = "media"
    descricao: str = ""
    trecho: Optional[str] = None
    fundamento: Optional[str] = None


class Edital(BaseModel):
    """Saída do Agente 7 — ficha extraída do PDF do edital."""
    tipo_leilao: Optional[str] = None
    descricao_bem: Optional[str] = None
    categoria_bem: Optional[str] = None
    processo: Optional[str] = None
    juizo: Optional[str] = None
    comarca: Optional[str] = None
    leiloeiro: Optional[str] = None
    leiloeiro_credenciado: Optional[bool] = None
    plataforma: Optional[str] = None
    data_praca1: Optional[str] = None       # dd/mm/aaaa
    data_praca2: Optional[str] = None
    valor_avaliacao: Optional[float] = None
    lance_minimo_1: Optional[float] = None
    lance_minimo_2: Optional[float] = None
    prazo_pagamento_dias: Optional[float] = None
    prazo_pagamento_texto: Optional[str] = None
    pagamento_avista: Optional[bool] = None
    parcelamento: Optional[str] = None
    forma_pagamento: Optional[str] = None   # PIX, boleto, depósito judicial...
    comissao_pct: Optional[float] = None
    comissao_responsavel: Optional[str] = None
    prazo_retirada_dias: Optional[float] = None
    debitos_responsabilidade: Optional[str] = None
    ocupacao: Optional[str] = None
    custos: list[ItemCusto] = Field(default_factory=list)
    valores_encontrados: list[Trecho] = Field(default_factory=list)   # TODO valor em R$/% citado no edital, com página
    pontos_atencao: list[Ponto] = Field(default_factory=list)
    lacunas: list[str] = Field(default_factory=list)


class Premissas(BaseModel):
    """Escolhas do usuário para o cálculo de custos (Agente 9)."""
    praca: Literal[1, 2] = 1
    lance: Optional[float] = None
    dias_armazenamento: float = 15
    reforma: float = 0
    outros_custos: float = 0
    valor_revenda: Optional[float] = None
    itbi_pct: float = 3.0
    registro_pct: float = 1.0
    transferencia_veiculo: float = 600.0
    comissao_padrao_pct: float = 5.0
