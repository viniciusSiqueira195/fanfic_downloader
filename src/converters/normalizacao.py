import unicodedata

# Letras decorativas ("small caps") usadas em títulos do Wattpad -> letras comuns,
# para que fontes e leitores de tela consigam ler o texto
MAPA_DECORATIVOS = str.maketrans({
    'ᴀ': 'a', 'ʙ': 'b', 'ᴄ': 'c', 'ᴅ': 'd', 'ᴇ': 'e', 'ꜰ': 'f', 'ɢ': 'g', 'ʜ': 'h', 'ɪ': 'i',
    'ᴊ': 'j', 'ᴋ': 'k', 'ʟ': 'l', 'ᴍ': 'm', 'ɴ': 'n', 'ᴏ': 'o', 'ᴘ': 'p', 'ꞯ': 'q', 'ʀ': 'r',
    'ꜱ': 's', 'ᴛ': 't', 'ᴜ': 'u', 'ᴠ': 'v', 'ᴡ': 'w', 'ʏ': 'y', 'ᴢ': 'z',
})

def normalizar(texto):
    # NFKC converte variantes de compatibilidade (negrito matemático, fullwidth etc.)
    return unicodedata.normalize('NFKC', texto).translate(MAPA_DECORATIVOS)
