"""Camada de IA (Claude): leitura nativa de PDF + extração estruturada. Opcional — há fallback heurístico."""
from __future__ import annotations

import base64
import os
from typing import Optional

from .schemas import Edital

MODELO = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def disponivel() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


PROMPT = """Você é um analista de editais de leilão no Brasil (judicial, Receita Federal e extrajudicial).
Leia o edital em PDF anexo e registre os dados com a ferramenta `registrar_edital`.

Regras:
- NUNCA invente dado. Se não estiver no edital, deixe null e liste em `lacunas`.
- Valores em reais (número), datas em dd/mm/aaaa, percentuais como número (5 = 5%).
- `custos`: liste TODO custo do arrematante além do lance — comissão do leiloeiro NÃO entra aqui (use comissao_pct),
  mas entram: armazenamento/pátio (tipo "diaria", valor por dia; dias sem cobrança em dias_gratis), taxa administrativa,
  remoção, custas, ITBI, escritura/registro, transferência/vistoria/despachante, caução/sinal (computa_no_total=false se
  for abatida do preço), débitos por conta do arrematante (IPVA, IPTU, condomínio, multas), tributos.
  Para cada custo informe pago_a, quando (prazo) e como (PIX, boleto, depósito judicial...) e cite o trecho em `fonte`.
- `pontos_atencao`: riscos específicos deste edital (quem responde pelos débitos, leiloeiro credenciado, preço vil,
  ocupação, prazos curtos, multas, venda no estado), com severidade alta/media/baixa, trecho e fundamento legal (CPC
  arts. 879, 886, 887, 891, 892, 895, 897, 901, 903 quando judicial).
- FIDELIDADE: `fonte` de cada custo e de cada ponto deve ser cópia LITERAL do edital (sem parafrasear) e `pagina`
  o número da página do PDF. Não some, não arredonde, não deduza valores que o edital não escreve.
- `valores_encontrados`: liste na ordem do edital TODA passagem que cite valor em R$ ou percentual (trecho literal,
  página e os valores), mesmo que você não saiba classificá-la como custo.
- prazo_pagamento_dias: converta horas em dias (24h = 1)."""


def extrair_edital_pdf(pdf: bytes, tipo_hint: Optional[str] = None) -> Edital:
    import anthropic
    client = anthropic.Anthropic()
    schema = Edital.model_json_schema()
    msg = client.messages.create(
        model=MODELO, max_tokens=8000,
        tools=[{"name": "registrar_edital", "description": "Registra a ficha estruturada do edital.",
                "input_schema": schema}],
        tool_choice={"type": "tool", "name": "registrar_edital"},
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.b64encode(pdf).decode()}},
            {"type": "text", "text": PROMPT + (f"\nTipo de leilão informado pelo usuário: {tipo_hint}." if tipo_hint else "")},
        ]}])
    for bloco in msg.content:
        if bloco.type == "tool_use":
            return Edital.model_validate(bloco.input)
    raise RuntimeError("A IA não devolveu a ficha estruturada.")
