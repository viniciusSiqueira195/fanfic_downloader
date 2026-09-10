# Roteiro de acessibilidade do módulo de livros

Este roteiro complementa os testes automatizados. Deve ser executado no Windows
com NVDA e, em uma segunda rodada, com Narrador.

1. Abra **Baixar livros** e confirme que o foco inicial anuncia “Título ou autor”.
2. Percorra todos os controles com Tab e Shift+Tab, verificando nome, função e ordem.
3. Pesquise com Enter e confirme que o foco anuncia imediatamente “Pesquisando”.
4. Durante “Todas as fontes”, confirme que cada catálogo é anunciado uma vez e que
   a janela continua respondendo.
5. Confirme que o primeiro resultado recebe foco ao terminar e contém título,
   fonte e formato.
6. Abra o menu com Enter, Shift+F10 e tecla de menu. Teste detalhes, cópia e download.
7. Inicie e cancele pesquisa e download com Escape. Confirme o estado anunciado.
8. Baixe um arquivo repetido e teste abrir existente, salvar cópia e cancelar.
9. Abra o histórico com Ctrl+H e teste abrir livro e pasta sem usar o mouse.
10. Teste Ctrl+F, Ctrl+D e F5, alto contraste, escalas de 150% e 200% e janela reduzida.

Registre leitor de tela, versão, escala, fonte pesquisada e qualquer anúncio
ausente, repetido ou fora de ordem. Não considere apenas a aparência visual.
