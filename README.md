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

No menu principal, escolha **Baixar livros**. Digite o título ou autor e, no
controle seguinte, selecione **Todas as fontes**, **Visionvox**,
**Project Gutenberg**, **Wikisource** ou **Internet Archive**. Depois escolha EPUB,
TXT ou PDF, filtre o idioma se quiser
e pesquise. Português vem selecionado inicialmente; **Todos os idiomas** continua
disponível. O filtro é aplicado pelo catálogo quando a fonte oferece esse recurso.
A pesquisa tem páginas; use os botões de página anterior e próxima para navegar.
**Descobrir livros para baixar** permite navegar pelos mais baixados ou por tema,
respeitando idioma e formato. Só entram nessa lista itens com um arquivo validável
no formato escolhido. A descoberta combina Project Gutenberg e Internet Archive,
remove obras repetidas e alterna os catálogos para aumentar a variedade.
O acervo Visionvox é destinado a pessoas com deficiência visual.
O Gutenberg reúne principalmente clássicos em vários idiomas, pesquisados pela
[API independente Gutendex](https://gutendex.com/). EPUB e TXT são as opções mais
comuns; um livro pode não existir no formato selecionado. A troca de fonte limpa
os resultados anteriores e mantém o termo para uma nova pesquisa.
Se o Gutendex não responder em dez segundos, o aplicativo consulta automaticamente
o catálogo OPDS oficial do Project Gutenberg, sem manter a janela esperando pelo
timeout antigo de trinta segundos.

A Wikisource pesquisa obras livres em português, inglês, espanhol ou francês e
usa o exportador oficial para entregar EPUB ou PDF. O Internet Archive pesquisa
somente itens que declaram licença aberta ou estado de domínio público e só mostra
um resultado quando encontra um arquivo público no formato escolhido. Alguns itens
do acervo podem ter qualidade de digitalização inferior à de uma edição revisada.

Na lista de resultados, Enter, Shift+F10, a tecla de menu ou o clique direito
abrem as ações **Baixar**, **Ler detalhes e sinopse** e **Escolher outra pasta para
downloads**. A sinopse aparece em uma janela de texto navegável. Ao baixar, o
aplicativo usa a pasta salva; se não houver uma pasta válida, pede a escolha
naquele momento e a grava imediatamente nas preferências.

As fontes são consultadas simultaneamente e o status informa cada resposta sem
travar a janela. Resultados equivalentes são reunidos e as correspondências mais
próximas aparecem primeiro. Quando um catálogo já entrega pelo menos cinco itens,
a lista é liberada sem aguardar outro catálogo lento; ele pode ser consultado
diretamente pelo seletor de fonte. O botão **Verificar fontes** testa os catálogos sob
demanda. O histórico guarda até 50 downloads existentes e permite abrir o livro
ou sua pasta. A tela de detalhes informa fonte, formato, autor e idioma quando o
catálogo fornece esses dados, além de permitir copiar a sinopse.

Ao iniciar uma consulta, o formulário de pesquisa desaparece e a janela mostra
somente o andamento, a lista e suas ações. **Voltar à pesquisa** ou Escape retorna
ao formulário sem apagar o termo digitado. O histórico abre em sua própria janela.

Atalhos da janela de livros: `Ctrl+F` volta à pesquisa, `Ctrl+D` baixa o item
selecionado, `Ctrl+H` abre o histórico e `F5` repete a pesquisa.

Em **Configurações**, o carregamento das listas pode usar o modo manual ou
contínuo. No modo manual, chegar aos cinco últimos itens acrescenta até quinze
resultados sem trocar de tela nem perder a seleção. No modo contínuo, as páginas
seguintes entram automaticamente em segundo plano. O limite padrão é 200 itens;
o valor 0 solicita todos os resultados disponíveis. O limite é aplicado também
quando uma fonte retorna uma página maior que o espaço restante.

Os arquivos são preservados no formato original, com limite de 100 MB. Se o livro
já existir, o aplicativo oferece abrir o arquivo, salvar uma cópia numerada ou cancelar.
O cancelamento da pesquisa combinada
é percebido imediatamente; uma conexão já aberta pode terminar em segundo plano
até seu timeout. Use Tab/Shift+Tab para navegar e Escape para fechar ou solicitar
cancelamento. O fluxo foi validado manualmente com navegação por teclado e leitor
de tela durante o desenvolvimento.

Cada fonte declara os formatos e idiomas que oferece; os seletores escondem
combinações indisponíveis. Consultas idênticas usam um cache em memória de dois
minutos e as conexões fazem poucas tentativas automáticas para falhas temporárias.

Sites sem catálogo público estável ou que distribuam obras sem autorização não são
incluídos. Veja o
[diagnóstico e plano de evolução](docs/diagnostico-e-plano.md) para o estado do
projeto, problemas conhecidos e pesquisa inicial das fontes.

## Sons de navegação

Os menus e a janela de livros oferecem tons curtos e suaves ao navegar e confirmar.
Na lista de livros, Enter abre o menu de ações; no campo de pesquisa, Enter pesquisa.
O áudio toca sem bloquear a interface e não substitui os
nomes, mensagens ou estados dos controles. Para desativar, abra **Configurações**,
desmarque **Sons suaves de navegação e confirmação** e escolha **Salvar**.
Também é possível ativar separadamente os sons de abertura, navegação e confirmação.
Os sons de abertura, navegação e confirmação vêm do pacote profissional Interface Sounds,
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

O GitHub Actions executa compilação e testes em Windows a cada push na `main` e
em pull requests. A validação humana está descrita no
[roteiro de acessibilidade do módulo de livros](docs/teste-acessibilidade-livros.md).
O fluxo de release também executa um autoteste do pacote compilado antes de
publicá-lo. O atualizador rejeita caminhos inseguros no ZIP, limita a extração e
restaura os arquivos anteriores se a aplicação da atualização falhar.
