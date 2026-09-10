# Diagnóstico e início da retomada

Inspeção local em 9 de setembro de 2026. Base: commit `1c16fb4`, versão declarada 1.0.1.
Havia uma alteração local em `config.json` antes do trabalho; ela foi preservada.

## Estado encontrado

Aplicativo desktop Python/wxPython com cerca de 2.850 linhas de código Python,
quatro adaptadores de fanfics (Spirit, Wattpad, FanFiction.net via FicHub e
PlusFiction), pesquisa por fonte, exportação TXT/PDF/EPUB e atualização via GitHub.
O menu de livros existia, mas só mostrava uma mensagem de desenvolvimento.
Não havia suíte de testes nem configuração de integração contínua versionadas.
O README não explicava instalação ou execução. As dependências de produção não
têm versões definidas. Neste Python local faltavam BeautifulSoup, EbookLib e ReportLab.

A interface já usa controles nativos, nomes explícitos em campos, navegação com
Enter/Escape, restauração de foco em vários fluxos, pasta digitável e progresso
também em texto. São bases úteis para manter. A inspeção do código não equivale
a uma avaliação concluída com leitores de tela.

## Problemas prioritários ainda abertos

1. **Pesquisa de fanfics bloqueia a interface.** `MainFrame.on_pesquisar`, em
   `src/gui/app.py`, chama as fontes diretamente no evento do botão. As consultas
   sequenciais podem bloquear teclado e atualização da janela por vários timeouts.
   Extrair um serviço de pesquisa e executá-lo em worker, com cancelamento e
   entrega de resultados por `wx.CallAfter`.
2. **Wattpad possui requisições sem timeout.** `src/scrapers/wattpad.py` pode esperar
   indefinidamente; o cancelamento só é observado entre etapas. Padronizar rede,
   timeout, tentativas limitadas e erros antes de declarar esse fluxo confiável.
3. **Conversão de EPUB do FicHub pode mudar a ordem dos capítulos.**
   `extrair_texto_de_epub`, em `src/scrapers/fanfiction_net.py`, ordena arquivos
   alfabeticamente, em vez de seguir o `spine` do EPUB. Criar fixture com capítulos
   1, 2 e 10 e navegação fora da ordem lexical antes de corrigir.
4. **Atualização não tem rollback.** `src/updater.py` valida SHA-256, mas copia o
   pacote diretamente sobre a instalação em execução. Uma falha no meio pode
   deixar versões misturadas; no Windows, o executável em uso também exige atenção.
   Precisa de processo auxiliar, staging, recuperação e testes com instalações falsas.
   A comparação atual de versões também não implementa pré-releases semânticas.
5. **Reconhecimento das fontes por substring.** `_processar_download` procura
   nomes de sites em qualquer parte da URL. Substituir por validação do hostname
   e registro explícito de adaptadores. O módulo novo já valida hosts exatos.
6. **Configuração misturada com a janela.** JSON, caminhos, threads, downloads,
   pesquisa e atualização estão concentrados em `gui/app.py` (771 linhas na base).
   JSON válido com campos ausentes pode falhar na inicialização. Configuração e
   sessão dependem do diretório de trabalho; criar serviço de preferências com
   defaults validados e migração de caminho sem perder as preferências atuais.
7. **Acessibilidade dos arquivos ainda é limitada.** O EPUB gerado junta a obra
   em uma única página, sem navegação real por capítulos. O PDF não configura
   estrutura semântica marcada. Texto selecionável não comprova acessibilidade.
   Preservar capítulos, idioma, autoria, títulos e ordem de leitura em um modelo comum.
8. **Distribuição pouco reproduzível.** O spec local do PyInstaller não está
   versionado; não há pipeline de build/teste e as dependências não estão travadas.
   Preparar build limpo, versões verificadas e teste do executável em Windows antes
   de publicar uma release.

Não foram feitos downloads reais das quatro fontes antigas, login no Spirit,
execução do atualizador ou validação do executável em `dist`. A presença do código
não comprova que cada serviço externo continua funcionando.

## Estado atual do módulo de livros

- `books/visionvox.py`: busca por título/autor e formato, página por consulta,
  modelo imutável de resultado e parser separado da rede. Cliente HTTP injetável
  para testes. Não inventa autor a partir do nome do arquivo.
- `books/gutenberg.py`: segunda fonte com metadados, formatos e sinopses via Gutendex.
- `books/catalog.py` e `books/sources.py`: contrato comum, busca concorrente,
  resultados progressivos, ordenação, deduplicação e falha isolada por catálogo.
- `books/download.py`: download em blocos, progresso, cancelamento, timeout, limite de 100 MB,
  validação básica do tipo do arquivo, restrição de redirecionamentos, limpeza de
  temporários e recusa de sobrescrita. Preserva o formato original.
- `gui/books_dialog.py`: pesquisa/download em worker, paginação, detalhes e sinopse
  copiáveis, progresso acessível, diagnóstico das fontes, atalhos, histórico e
  ações para abrir livro/pasta. A pasta só é pedida quando necessária.
- Conversor EPUB: escapa texto literal em HTML, normaliza letras decorativas,
  gera identificadores distintos e usa nomes de arquivo compatíveis com Windows.
- Testes offline sobre capítulos, normalização, TXT, EPUB, versões/hashes,
  pesquisa de livros e transferência. São um início de cobertura, não cobertura
  integral dos scrapers ou validação formal de acessibilidade.

O módulo segue a divisão interface → coordenação → adaptadores de catálogo e
transferência. Novas fontes entram pelo mesmo contrato e precisam restringir seus
próprios destinos de download.

## Viabilidade de outras fontes

### Visionvox: integração inicial confirmada

O [site principal](https://visionvox.com.br/) apresenta o acervo como destinado
a pessoas com deficiência visual. A [biblioteca](https://visionvox.com.br/biblioteca/)
oferece EPUB, TXT e PDF. Consulta HTTP real confirmou o formulário `GET busca.php`
com os parâmetros `busca`, `ext`, `pagina` e `num_page`; os arquivos são servidos
também em `visionvox.net`. É integração por HTML público, não API oficial.

Uma busca real por “Machado de Assis Dom Casmurro” retornou um EPUB. O download
temporário de 1.024.242 bytes passou pela validação do serviço e foi removido.
Isso comprova esse caminho específico na data do teste, não todos os arquivos.

### LeLivros: pendente de confirmação

A tentativa de abrir `https://lelivros.love/` pela ferramenta de pesquisa terminou
em timeout. Não foi encontrada uma API oficial confirmada nesta investigação
inicial. Não significa que o serviço não exista ou que uma integração seja
impossível. Antes de implementar, confirmar o endereço usado pelo usuário e
inspecionar um fluxo real, redirecionamentos e formatos. Nenhum suporte foi anunciado
ou incluído no aplicativo para essa fonte.

### Outras opções verificadas em documentação

- [Project Gutenberg](https://www.gutenberg.org/ebooks/offline_catalogs.html):
  catálogos destinados a integração e feeds OPDS. A documentação anuncia que
  o OPDS XML deve ser descontinuado em 2027 e que OPDS2 está em testes; considerar
  essa transição. Para catálogo local, usar os dados fornecidos, evitando varrer HTML.
- [Open Library](https://openlibrary.org/developers/api): APIs para descoberta e
  metadados, com limites de uso e recomendação de cache/identificação. Um resultado
  de busca não significa que o arquivo integral esteja disponível para download.
- [Google Books](https://developers.google.com/books/docs/v1/using?hl=pt-br):
  possível fonte de descoberta e de arquivos quando disponibilizados. Necessita
  prova de integração específica antes de entrar na lista de fontes suportadas.

“Qualquer site” não é um contrato tecnicamente sustentável. É possível oferecer
um catálogo crescente de adaptadores, indicando busca, formatos, disponibilidade,
login necessário e falhas por fonte. Não existe nesta pesquisa evidência de uma
API universal que entregue todos os livros. Downloads dependem do acesso oferecido
por cada fonte; autenticação, empréstimo ou DRM exigem fluxos próprios.

## Critérios de acessibilidade para a próxima rodada

Validar com NVDA e Narrador no Windows: nomes, papéis e estados dos controles,
Tab/Shift+Tab, Enter/Escape, foco após pesquisa/cancelamento/erro, leitura da lista,
ausência de anúncios repetitivos e uso sem mouse. Testar também alto contraste,
escala de 150%/200%, janela pequena e navegação por pessoa com deficiência motora.

No módulo de livros, Escape durante uma operação solicita cancelamento e mantém
a janela viva até o worker terminar; uma requisição em andamento pode demorar até
seu timeout. A publicação do arquivo usa hard link no mesmo volume: pastas em
sistemas de arquivos que não suportam hard links precisam de tratamento adicional.
O limite de 100 MB exclui parte dos PDFs grandes. A verificação de assinatura não
substitui EPUBCheck, análise de acessibilidade ou validação completa de PDF.

Próxima sequência: testar a nova janela com leitor de tela; corrigir pesquisa e
timeouts antigos; cobrir os parsers com fixtures; modelar obra/capítulos; adicionar
a segunda fonte; preparar CI e release reproduzível. Cada etapa deve manter as
fanfics funcionando e trazer uma prova de regressão verificável.
