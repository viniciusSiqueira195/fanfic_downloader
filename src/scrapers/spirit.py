import requests
from bs4 import BeautifulSoup
import time

# Imports corretos baseados na estrutura do Edu
from converters.to_txt import salvar_txt
from converters.to_pdf import salvar_pdf
from converters.to_epub import salvar_epub

def baixar_spirit(url, modo, formato, pasta, callback_progresso, cancel_event):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    
    try:
        callback_progresso(5, "Conectando ao Spirit...", -1)
        response = requests.get(url, headers=headers)
        
        # Proteção contra o Cloudflare
        if response.status_code == 403:
            return False, "O Spirit bloqueou o acesso (Cloudflare). Tente novamente mais tarde."
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Metadados principais
        titulo_bruto = soup.find('h1')
        titulo = titulo_bruto.get_text(strip=True) if titulo_bruto else "Fanfic_Spirit"
        
        # Mapeamento de capítulos
        links_capitulos = []
        if modo == "Apenas este capítulo":
            links_capitulos.append(url)
        else:
            callback_progresso(10, "Mapeando índice de capítulos...", -1)
            select_caps = soup.find('select', id='capitulo') or soup.find('select', class_='form-control')
            if select_caps:
                for option in select_caps.find_all('option'):
                    link = option.get('value')
                    if link:
                        links_capitulos.append(link if 'http' in link else "https://www.spiritfanfiction.com" + link)
            if not links_capitulos: 
                links_capitulos.append(url)

        total_caps = len(links_capitulos)
        texto_completo = "" 
        
        # Loop de Download
        for i, link in enumerate(links_capitulos):
            if cancel_event.is_set(): 
                return False, "Download cancelado pelo usuário."
                
            porcentagem = 10 + int((i / total_caps) * 70)
            callback_progresso(porcentagem, f"Baixando capítulo {i+1} de {total_caps}...", -1)
            
            if link != url:
                time.sleep(1.5) # Respeito ao servidor para evitar bloqueio
                resp_cap = requests.get(link, headers=headers)
                if resp_cap.status_code == 403:
                    return False, "Bloqueio do Spirit detectado no meio do download."
                soup_cap = BeautifulSoup(resp_cap.text, 'html.parser')
            else:
                soup_cap = soup
                
            # Extraindo o título do capítulo para o gerador de índices do Edu
            titulo_cap_bruto = soup_cap.find('h2')
            nome_capitulo = titulo_cap_bruto.get_text(strip=True) if titulo_cap_bruto else f"CAPITULO {i+1}"
            
            div_texto = soup_cap.find('div', class_='texto-capitulo') or soup_cap.find('div', id='texto') or soup_cap.find('div', class_='chapter-text')
            
            if div_texto:
                # Injeta a marcação do capítulo para os metadados exatamente como no Wattpad
                texto_completo += f"--- {nome_capitulo} ---\n\n"
                texto_completo += div_texto.get_text(separator='\n\n', strip=True) + "\n\n\n"
            else:
                texto_completo += f"--- {nome_capitulo} ---\n\n[Não foi possível extrair o texto deste capítulo.]\n\n\n"

        callback_progresso(85, f"Preparando conversão para {formato}...", -1)
        
        # --- Integração dos Conversores do Edu ---
        if formato == "TXT":
            caminho = salvar_txt(titulo, texto_completo, pasta)
            callback_progresso(100, "Concluído!", 0)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
            
        elif formato == "PDF":
            callback_progresso(90, "Gerando PDF com índices...", -1)
            caminho = salvar_pdf(titulo, texto_completo, pasta)
            callback_progresso(100, "Concluído!", 0)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
            
        elif formato == "EPUB":
            callback_progresso(90, "Montando EPUB com metadados...", -1)
            caminho = salvar_epub(titulo, texto_completo, pasta)
            callback_progresso(100, "Concluído!", 0)
            return True, f"Download concluído!\nArquivo salvo em:\n{caminho}"
            
        else:
            return False, f"O formato {formato} ainda será implementado."
            
    except requests.exceptions.RequestException as e:
        return False, f"Erro de conexão com o Spirit:\n{str(e)}"
    except Exception as e:
        return False, f"Erro inesperado ao processar: {str(e)}"