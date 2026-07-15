import requests
from bs4 import BeautifulSoup

def baixar_spirit(url, modo):
    # O User-Agent disfarça nosso script como se fosse um navegador comum
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        # Levanta um erro automático se a página não for encontrada (erro 404, etc)
        response.raise_for_status()
        
        # Transforma o HTML puro em um objeto que podemos navegar
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Pega o título principal da página para testarmos
        titulo = soup.title.string.strip() if soup.title else "Título Desconhecido"
        
        return True, f"Conexão bem sucedida! Encontramos a fanfic:\n{titulo}"
        
    except requests.exceptions.RequestException as e:
        return False, f"Erro ao tentar acessar o Spirit:\n{str(e)}" 
