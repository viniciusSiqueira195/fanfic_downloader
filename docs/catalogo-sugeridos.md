# Proposta: explorar livros sugeridos

## Experiência acessível

O menu **Explorar catálogo** deve abrir uma tela própria, sem misturar pesquisa e
downloads. A ordem sugerida é: idioma, tema, fonte e ordenação. Depois de confirmar,
a tela de filtros desaparece e surge uma lista paginada. Cada item informa título,
autor, idioma, disponibilidade e fonte. Enter abre ações como **Ler detalhes**,
**Baixar**, **Abrir para leitura** e **Adicionar à lista de leitura**, mostrando
somente as ações realmente disponíveis.

A primeira versão não precisa criar um perfil do usuário. Ela pode listar obras
populares por tema e idioma, alternar páginas e esconder itens já baixados. Uma
evolução posterior pode usar temas escolhidos e o histórico local, sempre com uma
opção para limpar esses dados.

## Catálogos adequados

- [Gutendex](https://gutendex.com/) já oferece livros do Project Gutenberg,
  ordenação por popularidade, filtro de idioma e busca por tema. É adequado tanto
  para sugestões quanto para download direto.
- [Open Library](https://openlibrary.org/developers/api) oferece pesquisa, assuntos,
  metadados e disponibilidade. Deve ser usada com cache, identificação do aplicativo
  e baixo volume. Um item pode ser público, emprestável ou apenas catalogado; a tela
  precisa anunciar essa diferença.
- [Google Books](https://developers.google.com/books/docs/v1/using) tem pesquisa por
  assunto, idioma, relevância e data, mas requer identificação por chave e nem todo
  resultado possui download. É melhor candidato para descoberta do que para download.
- [Standard Ebooks](https://standardebooks.org/feeds) possui feeds OPDS próprios para
  navegação e download, porém o catálogo completo exige associação ou autorização
  para projetos de código aberto. Não deve ser integrado sem obter esse acesso.

## Arquitetura

Fontes de descoberta devem retornar metadados e uma disponibilidade explícita:
`download`, `leitura online`, `empréstimo` ou `somente catálogo`. Fontes de download
continuam responsáveis por validar o domínio e o arquivo. A interface nunca deve
transformar automaticamente um link de leitura ou empréstimo em download.

As respostas podem ser guardadas em cache local por algumas horas. Isso acelera a
navegação, respeita limites das APIs e permite voltar à página anterior sem nova
consulta. O cache não deve guardar credenciais nem histórico de navegação externo.
