"""Lógica pura do configurador (F4) — sem GTK.

Agrupamento de campos por aba/classe, parâmetros de widget por tipo e
textos PT-BR. A casca GTK (`configurador.py`) só monta widgets a partir
destes dados e repassa edições ao `ConfigR4`; toda decisão fica aqui,
testável sem display.
"""

from __future__ import annotations

import locale

from ..core import ConfigR4
from ..core.campos import Campo, Classe, Tipo

FAIXA_LIVRE = 1_000_000_000.0
"""Limite dos SpinButton quando o campo não declara mínimo/máximo."""


def campos_da_aba(aba_id: str) -> tuple[list[Campo], list[Campo]]:
    """(básicos, avançados) da aba, na ordem do catálogo."""
    da_aba = [c for c in ConfigR4.campos() if c.aba == aba_id]
    basicos = [c for c in da_aba if c.classe is Classe.BASICA]
    avancados = [c for c in da_aba if c.classe is Classe.AVANCADA]
    return basicos, avancados


def faixa(campo: Campo) -> tuple[float, float, float, int]:
    """(mínimo, máximo, passo, casas decimais) para SpinButton."""
    minimo = campo.minimo if campo.minimo is not None else -FAIXA_LIVRE
    maximo = campo.maximo if campo.maximo is not None else FAIXA_LIVRE
    if campo.tipo in (Tipo.INTEIRO, Tipo.PINO_ENTRADA, Tipo.PINO_SAIDA):
        return float(minimo), float(maximo), 1.0, 0
    # 10 casas = a precisão que o núcleo grava no arquivo (config._fmt
    # arredonda em 10); o SCALE do eixo A usa 9 (53.333333333). A exibição
    # corta os zeros à direita (formatar_numero), então "250" segue "250".
    return float(minimo), float(maximo), 1.0, 10


def separador_decimal() -> str:
    """Separador decimal da locale do usuário ("," em pt_BR, "." em C/en).

    O SpinButton com `numeric=True` só aceita o separador da locale: em
    pt_BR, um texto com "." é rejeitado e o campo fica EM BRANCO — e o
    próximo update() zera o valor. Por isso a UI formata com o separador
    local; o arquivo continua com "." (core.config._fmt não depende da
    locale)."""
    return locale.localeconv().get("decimal_point") or "."


def formatar_numero(valor: float, digitos: int, separador: str = ".") -> str:
    """Número no estilo do arquivo: sem zeros à direita ("250", "0.5").

    O SpinButton mostraria casas fixas ("250.000"); o R4.ini escreve
    inteiro sem casa decimal e float curto (`core.config._fmt`) — a UI
    acompanha para o usuário reconhecer o valor do arquivo. `separador`
    troca o "." pelo da locale (ver `separador_decimal`).
    """
    arredondado = round(float(valor), digitos)
    if arredondado == int(arredondado):
        return str(int(arredondado))
    return f"{arredondado:.{digitos}f}".rstrip("0").replace(".", separador)


def rotulo_widget(campo: Campo) -> str:
    """Rótulo exibido ao lado do widget (unidade entre parênteses)."""
    if campo.unidade:
        return f"{campo.rotulo} ({campo.unidade})"
    return campo.rotulo


def sensivel(campo: Campo, valores: dict) -> bool:
    """Campos do eixo A (menos o toggle) apagam quando o eixo está
    desabilitado — igual ao Mach3, que esmaece recursos desligados."""
    if campo.aba == "eixo_a" and campo.papel != "eixo_a":
        return bool(valores.get("eixo_a.habilitado", True))
    return True


def texto_pendencias(alterado: bool) -> str:
    if alterado:
        return "Há alterações pendentes — use Aplicar ou Salvar."
    return "Sem alterações pendentes."


def texto_gravado(arquivos: tuple, com_backup: bool) -> str:
    if not arquivos:
        return "Nada a gravar nesta aba."
    nomes = ", ".join(a.name for a in arquivos)
    sufixo = " (backup criado — Cancelar desfaz)" if com_backup else ""
    return f"Gravado: {nomes}{sufixo}"


TEXTO_AVISO_REINICIAR = (
    "O LinuxCNC precisa ser reaberto para ler as mudanças.\n\n"
    "Se ele estiver aberto agora, será FECHADO — um programa em execução "
    "na máquina é interrompido. Continuar?"
)

TEXTO_NAO_FECHOU = (
    "O LinuxCNC não terminou de fechar em 15 segundos. Feche-o "
    "manualmente e clique em Reiniciar de novo."
)

TEXTO_SEM_LINUXCNC = (
    "O comando `linuxcnc` não foi encontrado neste sistema. "
    "Abra o LinuxCNC manualmente pelo atalho “launch R4”."
)
