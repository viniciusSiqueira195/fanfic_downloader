import requests
from bs4 import BeautifulSoup
import time
import os

def baixar_spirit(url, modo, formato, pasta, callback_progresso, cancel_event):
    # O User-Agent disfarça nosso script como se fosse um navegador comum
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    }
    
    try:
        callback_progresso(5, "Conectando ao Spirit...", -1)
        
        response = requests.get(url, headers=headers)
        
        # Detector de Escudo: Se o Spirit ativou o Cloudflare pesado pós-manutenção
        if response.status_code == 403:
            return False, "O Spirit bloqueou o acesso (Proteção Anti-Robô/Cloudflare ativada). Não foi possível baixar no momento."
            
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pegar Título Oficial
        titulo_bruto = soup.find('h1')
        titulo = titulo_bruto.get_text(strip=True) if titulo_bruto else "Fanfic_Spirit"
        
        # Limpar o nome para salvar no Windows sem dar erro
        nome_arquivo = "".join(x for x in titulo if x.isalnum() or x in " -_").strip()
        
        # --- Lógica de extração de capítulos ---
        links_capitulos = []
        if modo == "Apenas este capítulo":
            links_capitulos.append(url)
        else:
            callback_progresso(10, "Mapeando índice de capítulos...", -1)
            
            # O Spirit costuma guardar a lista de capítulos em um elemento <select>
            select_caps = soup.find('select', id='capitulo') or soup.find('select', class_='form-control')
            
            if select_caps:
                for option in select_caps.find_all('option'):
                    link = option.get('value')
                    if link and 'spiritfanfiction.com' in link:
                        links_capitulos.append(link)
                    elif link: # Link relativo
                        links_capitulos.append("https://www.spiritfanfiction.com" + link)
                        
            # Fallback: se a página principal não for um capítulo, pega o primeiro capítulo visível
            if not links_capitulos:
                links_capitulos.append(url)

        total_caps = len(links_capitulos)
        texto_completo = f"{titulo}\n\n"
        
        # --- Loop de Download ---
        for i, link in enumerate(links_capitulos):
            # Escuta o botão cancelar
            if cancel_event.is_set():
                return False, "Download cancelado pelo usuário."
                
            porcentagem = 10 + int((i / total_caps) * 80)
            callback_progresso(porcentagem, f"Baixando capítulo {i+1} de {total_caps}...", -1)
            
            # Evita baixar a mesma página 2 vezes se já for o link inicial
            if link != url:
                time.sleep(1.5) # Respeito ao servidor para não tomar ban
                resp_cap = requests.get(link, headers=headers)
                if resp_cap.status_code == 403:
                    return False, "Bloqueio do Spirit detectado no meio do download."
                soup_cap = BeautifulSoup(resp_cap.text, 'html.parser')
            else:
                soup_cap = soup
                
            # Extrair o texto (Pega a div principal de leitura do Spirit)
            div_texto = soup_cap.find('div', class_='texto-capitulo') or \
                        soup_cap.find('div', class_='chapter-text') or \
                        soup_cap.find('div', id='texto') or \
                        soup_cap.find('div', class_='p-wrapper')
                        
            if div_texto:
                texto_completo += div_texto.get_text(separator='\n\n', strip=True) + "\n\n"
            else:
                texto_completo += f"[Não foi possível extrair o texto do capítulo {i+1}. O layout do site pode ter mudado.]\n\n"

        callback_progresso(95, "Salvando arquivo final...", -1)
        
        # --- Salvamento Base (Apenas TXT por enquanto para validar a extração) ---
        caminho_arquivo = os.path.join(pasta, f"{nome_arquivo}.txt")
        
        with open(caminho_arquivo, 'w', encoding='utf-8') as f:
            f.write(texto_completo)
            
        callback_progresso(100, "Concluído!", 0)
        return True, f"Fanfic salva com sucesso em formato TXT:\n{caminho_arquivo}\n\nNota: A conversão para PDF/EPUB deve ser conectada ao seu gerador padrão."
        
    except requests.exceptions.RequestException as e:
        return False, f"Erro de conexão com o Spirit:\n{str(e)}"
    except Exception as e:
        return False, f"Erro inesperado ao processar a página:\n{str(e)}"