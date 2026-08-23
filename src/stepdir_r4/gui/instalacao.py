"""Lógica pura do wizard de instalação (F2) — sem GTK.

Catálogo de modelos, parâmetros coletados pelas telas e textos PT-BR
(resumo e resultado). A casca GTK (`wizard.py`) só coleta valores e
exibe estes textos; toda decisão fica aqui, testável sem display.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from ..core.instalador import ResultadoInstalacao

if TYPE_CHECKING:
    from ..sistema import Checagem

FOLGA_MAX_LIMIT = 15.0
"""MAX_LIMIT = dimensão da mesa + 15 (regra da Spark V2, ver specs)."""

MODELOS: tuple[tuple[str, str], ...] = (("spark_v2", "Spark V2"),)
"""(id, rótulo PT-BR) dos modelos de CNC suportados. Só Spark V2 por enquanto."""

MESA_PADRAO: dict[str, tuple[float, float]] = {"spark_v2": (800.0, 600.0)}
"""Dimensões padrão (X, Y) em mm por modelo."""


def rotulo_modelo(id_modelo: str) -> str:
    for ident, rotulo in MODELOS:
        if ident == id_modelo:
            return rotulo
    raise ValueError(f"Modelo desconhecido: {id_modelo!r}")


@dataclass(frozen=True)
class ParametrosWizard:
    """O que as telas do wizard coletam antes de gerar a config."""

    modelo: str
    mesa_x: float
    mesa_y: float
    criar_launcher: bool = True


def texto_curso(mesa_x: float, mesa_y: float) -> str:
    """Linha ao vivo da tela de dimensões: curso máximo resultante."""
    return (
        f"Curso máximo resultante (MAX_LIMIT): "
        f"X = {mesa_x + FOLGA_MAX_LIMIT:g} mm, "
        f"Y = {mesa_y + FOLGA_MAX_LIMIT:g} mm"
    )


def texto_resumo(
    params: ParametrosWizard, linhas_sistema: tuple[str, ...] = ()
) -> str:
    """Texto da página de confirmação, antes de gravar qualquer coisa.

    `linhas_sistema` (F3): situação de rede/drivers decidida nas páginas
    de sistema, mostrada junto do resumo da config.
    """
    linhas = [
        f"Modelo da CNC: {rotulo_modelo(params.modelo)}",
        f"Dimensões da mesa: X = {params.mesa_x:g} mm, Y = {params.mesa_y:g} mm",
        texto_curso(params.mesa_x, params.mesa_y),
        f"Pasta da configuração: ~/linuxcnc/configs/R4",
        "Atalho na Área de Trabalho: "
        + ("sim" if params.criar_launcher else "não"),
        *linhas_sistema,
        "",
        "Se já existir uma configuração R4, ela vira um backup datado — "
        "nada é perdido.",
    ]
    return "\n".join(linhas)


def texto_resultado(
    res: ResultadoInstalacao, verificacao: str | None = None
) -> str:
    """Texto da página final quando a instalação deu certo.

    `verificacao` (F3): relatório do ping na placa + hash dos drivers.
    """
    linhas = [f"Configuração criada em {res.pasta_config}"]
    if res.backup_anterior:
        linhas.append(
            f"Configuração anterior preservada em {res.backup_anterior}"
        )
    if res.launcher:
        linhas.append(f"Atalho criado: {res.launcher}")
    if verificacao:
        linhas.append("")
        linhas.append(verificacao)
    linhas.append("")
    linhas.append(
        "Abra o LinuxCNC pelo atalho “launch R4” para usar a nova "
        "configuração."
    )
    return "\n".join(linhas)


def texto_erro(erro: Exception) -> str:
    """Texto da página final quando a instalação falhou. Nada foi perdido:
    o instalador só renomeia a pasta antiga (backup) antes de copiar."""
    return (
        "A instalação não foi concluída.\n\n"
        f"{erro}\n\n"
        "Nenhuma configuração anterior foi apagada. Corrija o problema "
        "e execute o assistente novamente."
    )


_URL = re.compile(r"https?://[^\s,()<>]+")

_COR_OK = "#1a7f37"
_COR_FALHA = "#c62828"


def _linkar(texto_escapado: str) -> str:
    """Converte URLs em <a href> clicável. Recebe texto já escapado."""
    return _URL.sub(
        lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', texto_escapado
    )


def markup_checagens(checagens: list[Checagem]) -> str:
    """Versão Pango markup de `sistema.texto_checagens` para a GUI:
    rótulo em negrito, símbolo colorido, detalhe menor com URLs
    clicáveis e uma linha em branco entre os itens."""
    blocos = []
    for c in checagens:
        simbolo = (
            f'<span foreground="{_COR_OK}" weight="bold">✔</span>'
            if c.ok
            else f'<span foreground="{_COR_FALHA}" weight="bold">✘</span>'
        )
        detalhe = _linkar(escape(c.detalhe))
        blocos.append(
            f"{simbolo}  <b>{escape(c.rotulo)}</b>\n"
            f"      <small>{detalhe}</small>"
        )
    if all(c.ok for c in checagens):
        rodape = "<b>Tudo pronto para instalar.</b>"
    else:
        rodape = (
            "Há pendências. Você pode continuar mesmo assim, mas a "
            "instalação pode não funcionar até resolvê-las."
        )
    return "\n\n".join(blocos) + "\n\n" + rodape


def markup_tutorial(texto: str) -> str:
    """Tutorial com URLs clicáveis (Pango markup)."""
    return _linkar(escape(texto))
