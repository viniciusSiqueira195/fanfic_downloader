import os
import re
import unicodedata
from xml.sax.saxutils import escape
from converters.normalizacao import normalizar
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate

FONTES_UNICODE = [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"]

MARCADOR_CAPITULO = re.compile(r'-{2,}\s*CAPITULO\s+(\d+)\s*-{0,}\s*$')

def _registrar_fonte():
    for caminho_fonte in FONTES_UNICODE:
        if os.path.exists(caminho_fonte):
            pdfmetrics.registerFont(TTFont("FontePrincipal", caminho_fonte))
            return "FontePrincipal"
    # Helvetica embutida só cobre latin-1, suficiente para o português
    return "Helvetica"

def salvar_pdf(titulo, texto, pasta_destino):
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

    estilo_titulo = ParagraphStyle("Titulo", fontName=fonte, fontSize=16, leading=20, alignment=TA_CENTER, spaceAfter=16)
    estilo_capitulo = ParagraphStyle("Capitulo", fontName=fonte, fontSize=14, leading=18, alignment=TA_CENTER, spaceBefore=16, spaceAfter=10)
    estilo_texto = ParagraphStyle("Texto", fontName=fonte, fontSize=12, leading=17, alignment=TA_JUSTIFY, spaceAfter=8)

    doc = SimpleDocTemplate(caminho_completo, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=15 * mm, bottomMargin=15 * mm, title=titulo)

    elementos = [Paragraph(escape(titulo), estilo_titulo)]
    for paragrafo in texto.split('\n'):
        if not paragrafo.strip():
            continue
        capitulo = MARCADOR_CAPITULO.match(paragrafo.strip())
        if capitulo:
            elementos.append(Paragraph(f"Capítulo {capitulo.group(1)}", estilo_capitulo))
        else:
            elementos.append(Paragraph(escape(paragrafo), estilo_texto))

    doc.build(elementos)

    return caminho_completo