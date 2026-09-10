# fanfic_downloader
Aplicativo acessível em Python para baixar fanfics do Spirit, Wattpad e FanFiction.net nos formatos PDF, EPUB ou TXT.

O aplicativo também verifica releases no GitHub e pode se atualizar automaticamente após validar o hash SHA-256 do pacote.
Essa checagem pode ser ativada ou desativada nas preferências da tela inicial.

## Executar no Windows

Na raiz do projeto, em PowerShell, com Python instalado:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe src/main.py
```

O fluxo do Spirit também depende do navegador Camoufox local. A instalação das
dependências Python, sozinha, não comprova que o navegador esteja preparado.

## Livros: escolha da fonte

No menu principal, escolha **Baixar livros** e selecione **Visionvox** ou
**Project Gutenberg** no campo “Fonte da pesquisa”. Pesquise título ou autor,
escolha EPUB, TXT ou PDF, selecione um resultado e informe uma pasta existente.
A pesquisa tem páginas; use os botões de página anterior e próxima para navegar.
O acervo Visionvox é destinado a pessoas com deficiência visual.
O Gutenberg reúne principalmente clássicos em vários idiomas, pesquisados pela
[API independente Gutendex](https://gutendex.com/). EPUB e TXT são as opções mais
comuns; um livro pode não existir no formato selecionado. A troca de fonte limpa
os resultados anteriores e mantém o termo para uma nova pesquisa.

Os arquivos são preservados no formato original, com limite de 100 MB. Um arquivo
existente com o mesmo nome não é substituído. O cancelamento pode aguardar o timeout
da requisição atual. Use Tab/Shift+Tab para navegar e Escape para fechar ou solicitar
cancelamento. A janela ainda precisa de validação prática com NVDA/Narrador.

LeLivros e outras fontes ainda não estão integrados. Veja o
[diagnóstico e plano de evolução](docs/diagnostico-e-plano.md) para o estado do
projeto, problemas conhecidos e pesquisa inicial das fontes.

## Sons de navegação

Os menus e a janela de livros oferecem tons curtos e suaves ao navegar e confirmar.
Na lista de livros, Enter inicia o download do resultado selecionado; no campo de
pesquisa, Enter pesquisa. O áudio toca sem bloquear a interface e não substitui os
nomes, mensagens ou estados dos controles. Para desativar, abra **Configurações**,
desmarque **Sons suaves de navegação e confirmação** e escolha **Salvar**.
Os sons de navegação e confirmação vêm do pacote profissional Interface Sounds,
criado pela Kenney e publicado sob licença CC0. Os arquivos usados estão incluídos
no aplicativo e não dependem do esquema sonoro do Windows.

## Testes offline

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes não fazem login, não consultam os sites e não aplicam atualizações.
Cobrem o núcleo e o novo módulo de livros; não substituem testes com leitores de
tela nem a verificação real das fontes externas.
