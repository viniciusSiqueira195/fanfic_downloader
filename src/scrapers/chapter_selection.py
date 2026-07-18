import re


class SelecaoCapitulosError(ValueError):
    pass


def interpretar_selecao(especificacao):
    indices = set()

    for trecho in especificacao.split(","):
        trecho = trecho.strip()
        correspondencia = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", trecho)
        if not correspondencia:
            raise SelecaoCapitulosError(
                "Informe capítulos como 1-5, 8, 10-12."
            )

        inicio = int(correspondencia.group(1))
        fim = int(correspondencia.group(2) or inicio)
        if inicio < 1 or fim < inicio:
            raise SelecaoCapitulosError(
                "Os números dos capítulos devem começar em 1 e o início do intervalo não pode ser maior que o fim."
            )

        indices.update(range(inicio, fim + 1))

    if not indices:
        raise SelecaoCapitulosError("Informe ao menos um capítulo para baixar.")

    return sorted(indices)


def selecionar_capitulos(capitulos, especificacao):
    indices = interpretar_selecao(especificacao)
    total = len(capitulos)
    fora_do_limite = [indice for indice in indices if indice > total]
    if fora_do_limite:
        raise SelecaoCapitulosError(
            f"A obra possui {total} capítulos; o capítulo {fora_do_limite[0]} não existe."
        )

    return [(indice, capitulos[indice - 1]) for indice in indices]
