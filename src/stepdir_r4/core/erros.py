"""Modos de erro públicos do núcleo. Mensagens em PT-BR, prontas para diálogo GTK."""

from __future__ import annotations


class ErroConfigR4(Exception):
    """Base de todos os erros do núcleo."""


class ConfigNaoEncontrada(ErroConfigR4):
    """abrir(): pasta ou R4.ini/R4.hal ausentes."""


class ConfigCorrompida(ErroConfigR4):
    """Linha-âncora de um campo da whitelist não localizada no arquivo instalado
    (edição manual destruiu a estrutura reconhecível)."""

    def __init__(self, chave: str, arquivo: str) -> None:
        self.chave = chave
        self.arquivo = arquivo
        super().__init__(
            f"Não encontrei a linha de '{chave}' em {arquivo}. "
            f"O arquivo foi editado além do reconhecível."
        )


class CampoDesconhecido(ErroConfigR4):
    """definir()/ler(): id fora da whitelist. Nada é alterado."""

    def __init__(self, chave: str) -> None:
        self.chave = chave
        super().__init__(f"Campo desconhecido: '{chave}' não está na whitelist.")


class ValorInvalido(ErroConfigR4):
    """Valor com tipo errado ou fora da faixa. Nada é alterado."""

    def __init__(self, chave: str, motivo: str) -> None:
        self.chave = chave
        self.motivo = motivo
        super().__init__(f"Valor inválido para '{chave}': {motivo}")


class ArquivoAlteradoExternamente(ErroConfigR4):
    """aplicar()/salvar(): arquivo em disco mudou desde a carga. Nada foi gravado;
    chame recarregar() e redecida."""

    def __init__(self, arquivo: str) -> None:
        self.arquivo = arquivo
        super().__init__(
            f"{arquivo} foi modificado fora do aplicativo. Nada foi gravado — "
            f"recarregue a configuração antes de continuar."
        )


class ErroInstalacao(ErroConfigR4):
    """instalar_config(): falha em algum passo (cópia, backup, launcher)."""
