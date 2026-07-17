# fanfic_downloader
Aplicativo acessível em Python para baixar fanfics do Spirit, Wattpad e FanFiction.net nos formatos PDF, EPUB ou TXT.

## Busca opcional por termo
- O fluxo atual por link direto continua igual.
- Agora você também pode pesquisar por termo e selecionar um resultado para preencher a URL automaticamente.
- Você pode escolher um servidor específico ou usar **Todas as fontes** para consultar tudo de uma vez.
- Endpoints incluídos:
  - Wattpad API pública: `https://www.wattpad.com/api/v3/stories?query=...`
  - Spirit busca pública: `https://www.spiritfanfiction.com/busca?query=...`
  - FanFiction.net via scraping de resultados web (DuckDuckGo HTML): `https://duckduckgo.com/html/?q=site:fanfiction.net/s/+...`
  - PlusFiction via scraping: tentativa direta em `https://plusfiction.com/search/<termo>` com fallback para DuckDuckGo (`site:plusfiction.com/book ...`) se houver bloqueio 403.

## Preenchimento de URL pela busca
- A busca serve para **encontrar** a fanfic e **preencher automaticamente** o campo de URL.
- O download continua acontecendo pelo fluxo normal do botão **Baixar Fanfic**, usando a URL preenchida.

## Download PlusFiction
- Agora também há tentativa de download direto para links do PlusFiction (capítulo único e obra completa).
- Em caso de bloqueio, o app tenta alternativa automática (sessão persistente, aquecimento de cookies e retentativas com host alternativo).
- Se mesmo assim houver bloqueio (HTTP 403), o app mostra mensagem clara de erro.
