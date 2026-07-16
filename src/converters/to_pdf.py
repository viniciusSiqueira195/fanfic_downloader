import os
import re
import unicodedata
from io import BytesIO
from xml.sax.saxutils import escape, quoteattr
from converters.normalizacao import normalizar
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer
from reportlab.platypus.tableofcontents import TableOfContents

FONTES_UNICODE = [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]

MARCADOR_CAPITULO = re.compile(r'-{2,}\s*CAPITULO\s+(\d+)(?:\s*:\s*(.*?))?\s*-{2,}\s*$')


class DocumentoComIndice(SimpleDocTemplate):
    def beforeDocument(self):
        super().beforeDocument()
        self._contador_capitulos = 0

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "Capitulo":
            self._contador_capitulos += 1
            titulo = flowable.getPlainText()
            chave = f"capitulo-{self._contador_capitulos}"
            self.canv.bookmarkPage(chave)
            self.canv.addOutlineEntry(titulo, chave, level=0)
            self.notify("TOCEntry", (0, titulo, self.page, chave))

def _registrar_fonte():
    for caminho_fonte in FONTES_UNICODE:
        if os.path.exists(caminho_fonte):
            pdfmetrics.registerFont(TTFont("FontePrincipal", caminho_fonte))
            return "FontePrincipal"
    # Helvetica embutida só cobre latin-1, suficiente para o português
    return "Helvetica"


def _criar_imagem_capa(capa):
    if not capa:
        return None
    try:
        imagem = Image(BytesIO(capa))
        escala = min((90 * mm) / imagem.imageWidth, (120 * mm) / imagem.imageHeight)
        imagem.drawWidth = imagem.imageWidth * escala
        imagem.drawHeight = imagem.imageHeight * escala
        imagem.hAlign = 'CENTER'
        return imagem
    except Exception:
        return None


def salvar_pdf(titulo, texto, pasta_destino, metadados=None, capa=None):
    titulo_limpo = titulo.split(' - ')[0]
    titulo_limpo = unicodedata.normalize('NFKD', titulo_limpo).encode('ascii', 'ignore').decode('utf-8')

    nome_arquivo = "".join(c for c in titulo_limpo if c.isalnum() or c == ' ').strip()
    nome_arquivo = " ".join(nome_arquivo.split())

    if not nome_arquivo:
        nome_arquivo = "Fanfic_Wattpad"

    caminho_completo = os.path.join(pasta_destino, f"{nome_arquivo}.pdf")

    fonte = _registrar_fonte()

    titulo = normalizar(titulo)
    texto = normalizar(texto)
    metadados = metadados or {}
    autor = normalizar(metadados.get('autor', ''))
    descricao = normalizar(metadados.get('descricao', ''))
    origem = metadados.get('origem', '')

    estilo_titulo = ParagraphStyle("Titulo", fontName=fonte, fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=16)
    estilo_titulo_indice = ParagraphStyle("TituloIndice", fontName=fonte, fontSize=14, leading=18, alignment=TA_CENTER, spaceBefore=16, spaceAfter=10)
    estilo_capitulo = ParagraphStyle("Capitulo", fontName=fonte, fontSize=14, leading=18, alignment=TA_CENTER, spaceBefore=16, spaceAfter=10)
    estilo_texto = ParagraphStyle("Texto", fontName=fonte, fontSize=12, leading=17, alignment=TA_JUSTIFY, spaceAfter=8)
    estilo_autor = ParagraphStyle("Autor", fontName=fonte, fontSize=12, leading=16, alignment=TA_CENTER, spaceAfter=12)
    estilo_origem = ParagraphStyle("Origem", fontName=fonte, fontSize=9, leading=12, alignment=TA_CENTER, spaceBefore=8)

    estilo_indice = ParagraphStyle("Indice", fontName=fonte, fontSize=14, leading=18, spaceAfter=6)

    doc = DocumentoComIndice(caminho_completo, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=titulo, author=autor, subject=descricao)

    indice = TableOfContents()
    indice.levelStyles = [estilo_indice]
    elementos = [Paragraph(escape(titulo), estilo_titulo)]
    imagem_capa = _criar_imagem_capa(capa)
    if imagem_capa:
        elementos.extend([imagem_capa, Spacer(1, 8 * mm)])
    if autor:
        elementos.append(Paragraph(f"Por {escape(autor)}", estilo_autor))
    if descricao:
        elementos.append(Paragraph(escape(descricao), estilo_texto))
    if origem:
        elementos.append(Paragraph(f"Origem: <link href={quoteattr(origem)}>Wattpad</link>", estilo_origem))

    tem_capitulos = any(MARCADOR_CAPITULO.match(linha.strip()) for linha in texto.split('\n'))
    if imagem_capa or autor or descricao or origem:
        elementos.append(PageBreak())
    if tem_capitulos:
        elementos.extend([
            Paragraph("Índice", estilo_titulo_indice),
            indice,
            PageBreak(),
        ])
    for paragrafo in texto.split('\n'):
        if not paragrafo.strip():
            continue
        capitulo = MARCADOR_CAPITULO.match(paragrafo.strip())
        if capitulo:
            titulo_capitulo = capitulo.group(2).strip() if capitulo.group(2) else f"Capítulo {capitulo.group(1)}"
            elementos.append(Paragraph(escape(titulo_capitulo), estilo_capitulo))
        else:
            elementos.append(Paragraph(escape(paragrafo), estilo_texto))

    doc.multiBuild(elementos)

    return caminho_completo
