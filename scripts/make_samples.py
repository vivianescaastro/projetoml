"""Gera a base de exemplo (xlsx) e 3 editais FICTÍCIOS em PDF para testar o app."""
from pathlib import Path

from openpyxl import load_workbook
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from leilaoia.excel_db import DATA_DIR, modelo_xlsx

ROOT = Path(__file__).resolve().parent.parent / "leilaoia"
SAMPLES = ROOT / "samples"

EDITAIS = {
"edital_judicial_veiculo.pdf": ("EDITAL DE LEILÃO JUDICIAL — DOCUMENTO FICTÍCIO PARA TESTE", [
"5ª Vara Cível da Comarca de Campinas/SP. Processo nº 1001234-56.2022.8.26.0114, em que figura como exequente Banco Exemplo S/A e executado Fulano de Tal.",
"O leiloeiro público oficial João da Silva, matriculado na JUCESP sob nº 123 e credenciado junto ao Tribunal de Justiça, realizará o leilão eletrônico no site www.leiloesexemplo.com.br.",
"BEM: Veículo Honda Civic EXL 2019, placa ABC1D23, avaliado em R$ 48.000,00 (quarenta e oito mil reais).",
"1ª praça: 12/12/2026, às 14h, pelo lance mínimo correspondente ao valor da avaliação, R$ 48.000,00. 2ª praça: 15/12/2026, às 14h, não sendo aceitos lances inferiores a 50% da avaliação, considerado preço vil, ou seja R$ 24.000,00 (art. 891 do CPC).",
"COMISSÃO: o arrematante pagará ao leiloeiro comissão de 5% (cinco por cento) sobre o valor da arrematação, à parte, não integrando o lance.",
"PAGAMENTO: o pagamento deverá ser efetuado à vista, em até 24 (vinte e quatro) horas após o encerramento do leilão, por PIX ou depósito judicial. Admite-se parcelamento nos termos do art. 895 do CPC, com entrada de 25% e saldo em até 30 parcelas, mediante proposta escrita.",
"DÉBITOS: os débitos de IPVA e licenciamento anteriores à penhora sub-rogam-se no preço da arrematação (art. 908, §1º, do CPC). Multas de trânsito posteriores à constrição ficarão a cargo do arrematante.",
"ARMAZENAMENTO: o veículo encontra-se no pátio Auto Guarda, com 5 (cinco) dias gratuitos após a arrematação; após esse prazo será cobrada diária de R$ 45,00 por dia, paga diretamente ao depósito. A remoção do bem é por conta do arrematante.",
"A transferência da propriedade junto ao Detran, vistoria e despachante são de responsabilidade do arrematante. Custas da carta de arrematação: R$ 380,00.",
"O bem é vendido no estado em que se encontra, ad corpus, sem garantia. O executado e o credor foram devidamente intimados (art. 889 do CPC). A desistência ou o não pagamento sujeita o arrematante à multa de 20% (art. 897 do CPC).",
]),
"edital_receita_federal.pdf": ("EDITAL DE LEILÃO — RECEITA FEDERAL — DOCUMENTO FICTÍCIO PARA TESTE", [
"A Secretaria Especial da Receita Federal do Brasil (RFB) torna público o leilão de mercadorias apreendidas, declaradas abandonadas e com pena de perdimento aplicada, conduzido pelo leiloeiro Carlos Eduardo Lima, credenciado, pelo portal www.leilaorfbexemplo.com.br.",
"Lote 12: Veículo Fiat Toro 2020, avaliado em R$ 62.000,00. 1º leilão: 20/12/2026 com lance inicial de R$ 62.000,00. 2º leilão: 28/12/2026 com lance inicial de R$ 43.400,00.",
"Os interessados devem se cadastrar e se habilitar com CPF ou CNPJ válido no portal até 24 horas antes do leilão.",
"O pagamento será à vista, por boleto bancário ou PIX, no prazo de 2 (dois) dias úteis contados do encerramento do leilão. A comissão do leiloeiro é de 5% sobre o valor da arrematação, paga pelo arrematante.",
"Taxa administrativa de R$ 150,00 por lote. Os bens estão armazenados em depósito alfandegado e deverão ser retirados em até 10 (dez) dias após o pagamento, sob pena de perdimento do bem sem direito a restituição. Após o 5º dia, incide armazenagem de R$ 38,00 por dia.",
"Os bens são vendidos no estado em que se encontram, sem garantia, vedada a devolução. A regularização junto ao Detran e eventuais tributos incidentes são de responsabilidade do arrematante.",
]),
"edital_extrajudicial_imovel.pdf": ("EDITAL DE LEILÃO EXTRAJUDICIAL — DOCUMENTO FICTÍCIO PARA TESTE", [
"Banco Exemplo S/A, credor fiduciário, nos termos da Lei nº 9.514/97, levará a público leilão extrajudicial do imóvel dado em alienação fiduciária por Beltrano da Silva (fiduciante), conduzido pela leiloeira Maria Souza, matriculada na JUCESP nº 456, pelo site www.leiloesbancoexemplo.com.br.",
"IMÓVEL: Apartamento 82, Ed. Solar, Santo André/SP, matrícula 55.321. Avaliação: R$ 580.000,00.",
"1º leilão: 10/12/2026, lance mínimo de R$ 520.000,00. 2º leilão: 18/12/2026, lance mínimo de R$ 310.000,00, correspondente ao valor da dívida.",
"Comissão da leiloeira: 5% sobre o valor da arrematação, paga pelo arrematante. Pagamento à vista em até 24 horas por TED ou PIX; sinal de R$ 20.000,00 será abatido do preço.",
"Por conta do arrematante: ITBI, escritura, registro, emolumentos e demais despesas de transferência. Débitos de IPTU e condomínio em atraso, estimados em R$ 18.400,00, são de responsabilidade do arrematante.",
"O imóvel encontra-se ocupado. A desocupação, inclusive eventual ação de reintegração de posse (art. 30 da Lei 9.514/97), correrá por conta do arrematante. Fica assegurado ao devedor fiduciante o direito de preferência até a assinatura do auto de arrematação (art. 27, §2º-B).",
"O imóvel é vendido no estado em que se encontra, sem garantia, não cabendo vistoria posterior.",
]),
}


def edital_pdf(nome, titulo, paragrafos):
    st = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(SAMPLES / nome), pagesize=A4, title=titulo)
    flow = [Paragraph(titulo, st["Title"]), Spacer(1, 12)]
    for p in paragrafos:
        flow += [Paragraph(p, st["BodyText"]), Spacer(1, 8)]
    doc.build(flow)


def base():
    import io
    wb = load_workbook(io.BytesIO(modelo_xlsx()))
    ws = wb["Lotes"]
    ws.delete_rows(2)
    L = [
        ["L001", "Veículos", "Honda Civic EXL 2019 - 62.000 km", "SP", "Campinas", "Judicial", 48000, 48000, 78000, "12/12/2026", "João da Silva", 5, "Funcionando; 5 dias grátis de pátio", ""],
        ["L002", "Veículos", "Fiat Toro Freedom 2020 - 48.000 km", "SP", "Santos", "Receita Federal", 62000, 62000, 98000, "20/12/2026", "Carlos Eduardo Lima", 5, "Apreendido", ""],
        ["L003", "Imóvel", "Apartamento 82 - 78 m² - Santo André", "SP", "Santo André", "Extrajudicial", 580000, 520000, 640000, "10/12/2026", "Maria Souza", 5, "Ocupado", ""],
        ["L004", "Veículos", "VW Gol 1.0 2018", "MG", "Belo Horizonte", "Judicial", 31000, 15500, 38000, "05/12/2026", "Ana Paula", 5, "Documentação ok", ""],
        ["L005", "Veículos", "Toyota Hilux SRX 2017 diesel", "PR", "Curitiba", "Extrajudicial", 130000, 98000, 158000, "14/12/2026", "Rui Barbosa", 5, "Sinistro leve", ""],
        ["L006", "Imóvel", "Casa 3 dorm. 150 m² - Londrina", "PR", "Londrina", "Judicial", 420000, 210000, 395000, "08/12/2026", "Pedro Lima", 5, "Ocupado", ""],
        ["L007", "Bens Diversos", "Lote de 40 notebooks usados", "SP", "São Paulo", "Receita Federal", 52000, 26000, 48000, "17/12/2026", "Carlos Eduardo Lima", 5, "Apreendidos", ""],
        ["L008", "Bens Diversos", "Máquina CNC Romi D800", "RS", "Caxias do Sul", "Judicial", 180000, 90000, 150000, "11/12/2026", "Lúcia Fernandes", 5, "Funcionando", ""],
        ["L009", "Imóvel", "Sala comercial 45 m² - Centro RJ", "RJ", "Rio de Janeiro", "Extrajudicial", 300000, 240000, 310000, "09/12/2026", "Marcos Dias", 5, "Desocupada", ""],
        ["L010", "Veículos", "Yamaha MT-07 2021", "RS", "Porto Alegre", "Receita Federal", 36000, 25000, 42000, "21/12/2026", "Carlos Eduardo Lima", 5, "Apreendida", ""],
    ]
    for r in L:
        ws.append(r)
    wb.save(DATA_DIR / "base_exemplo.xlsx")


if __name__ == "__main__":
    DATA_DIR.mkdir(exist_ok=True); SAMPLES.mkdir(exist_ok=True)
    base()
    for n, (t, p) in EDITAIS.items():
        edital_pdf(n, t, p)
    print("ok")
