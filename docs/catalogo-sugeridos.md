# Explorar livros sugeridos

A primeira versão está implementada com o Gutendex: mostra obras populares ou por
tema, respeita idioma e formato e descarta qualquer resultado sem URL de download
aceita. As fontes futuras devem conservar essa garantia.

## Experiência acessível

O comando **Descobrir livros para baixar** abre a escolha de tema sem misturar pesquisa e
downloads. Ele aproveita o idioma e o formato selecionados. Depois de confirmar,
a tela de filtros desaparece e surge uma lista paginada. Cada item informa título,
autor, idioma e fonte. Enter abre **Ler detalhes** ou **Baixar**.

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

Uma fonte só pode participar desta tela quando retornar um arquivo de download
validável. Links de leitura, empréstimo ou páginas de catálogo não são resultados.
Cada adaptador continua responsável por restringir seu domínio e formato.

As respostas podem ser guardadas em cache local por algumas horas. Isso acelera a
navegação, respeita limites das APIs e permite voltar à página anterior sem nova
consulta. O cache não deve guardar credenciais nem histórico de navegação externo.
