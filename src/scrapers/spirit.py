def baixar_spirit(url, modo, formato, pasta, callback_progresso, cancel_event, selecao_capitulos=""):
    """
    Módulo temporariamente desativado devido ao Cloudflare Turnstile.
    Retorna uma mensagem amigável para o usuário final.
    """
    callback_progresso(10, "Verificando disponibilidade do servidor...", -1)

    mensagem = (
        "O download do Spirit Fanfics está temporariamente indisponível.\n\n"
        "O site ativou um sistema de segurança extremo (Cloudflare) que bloqueia "
        "aplicativos de acessibilidade e leitura automatizada.\n\n"
        "Estamos estudando uma forma de contornar isso para uma atualização futura. "
        "Por enquanto, aproveite os downloads do FanFiction.net, Wattpad e Plus Fanfiction!"
    )

    # Retorna False para a interface entender que o download parou, e exibe a mensagem explicativa
    return False, mensagem
