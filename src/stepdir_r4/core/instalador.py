"""instalar_config() — monta ~/linuxcnc/configs/R4 a partir dos templates embutidos.

NUNCA gera arquivo do zero: copia a config Spark V2 versionada em
``stepdir_r4/data/config_r4`` e ajusta, via o próprio editor in-place,
MAX_LIMIT (mesa + 15) e PROGRAM_PREFIX (xdg-user-dir DESKTOP).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from pathlib import Path
from typing import Callable

from .config import ConfigR4
from .erros import ErroInstalacao, ValorInvalido

Executar = Callable[[list[str]], str]
"""Seam de subprocess: recebe argv, devolve stdout sem quebra final.
Adapter de produção: subprocess.run. Adapter de teste: lambda."""


@dataclass(frozen=True)
class ResultadoInstalacao:
    """Relatório do que o instalador fez (caminhos absolutos)."""

    pasta_config: Path
    backup_anterior: Path | None
    launcher: Path | None
    symlink_desktop: Path | None


def _executar_real(argv: list[str]) -> str:
    saida = subprocess.run(
        argv, capture_output=True, text=True, timeout=10, check=True
    )
    return saida.stdout.rstrip("\n")


def _dir_desktop(executar: Executar) -> Path:
    try:
        caminho = executar(["xdg-user-dir", "DESKTOP"]).strip()
        if caminho:
            return Path(caminho)
    except Exception:
        pass
    return Path.home() / "Desktop"


def _copiar_templates(destino: Path) -> None:
    origem = resources.files("stepdir_r4").joinpath("data/config_r4")
    with resources.as_file(origem) as pasta_origem:
        shutil.copytree(pasta_origem, destino)


_LAUNCHER = """\
[Desktop Entry]
Terminal=false
Name=launch R4
Exec=linuxcnc {ini}
Type=Application
Icon=/usr/share/linuxcnc/linuxcncicon.png
"""


def instalar_config(
    raiz_configs: Path | None = None,
    mesa_x: float = 800.0,
    mesa_y: float = 600.0,
    criar_launcher: bool = True,
    executar: Executar | None = None,
) -> ResultadoInstalacao:
    """Monta a config R4 completa a partir dos templates embutidos.

    Cria ``raiz_configs/R4`` (padrão ~/linuxcnc/configs; o nome R4 é imposto
    por construção — obrigatório). Pasta existente vira backup datado —
    idempotente por backup, nunca perde a config anterior. Aplica
    MAX_LIMIT = mesa + 15 nos eixos X e Y, resolve PROGRAM_PREFIX e cria
    launcher .desktop + symlink no Desktop.
    """
    if mesa_x <= 0 or mesa_y <= 0:
        raise ValorInvalido("mesa", "dimensões da mesa devem ser maiores que zero")
    executar = executar or _executar_real

    raiz = Path(raiz_configs) if raiz_configs else Path.home() / "linuxcnc/configs"
    pasta = raiz / "R4"

    backup_anterior: Path | None = None
    try:
        raiz.mkdir(parents=True, exist_ok=True)
        if pasta.exists():
            carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_anterior = raiz / f"R4.bak-{carimbo}"
            pasta.rename(backup_anterior)
        _copiar_templates(pasta)
    except OSError as e:
        raise ErroInstalacao(f"Falha ao montar a pasta da configuração: {e}") from e

    desktop = _dir_desktop(executar)

    cfg = ConfigR4(pasta)
    cfg.definir("eixo_x.max_limit", mesa_x + 15)
    cfg.definir("eixo_y.max_limit", mesa_y + 15)
    cfg.definir("geral.program_prefix", f"{desktop}/")
    cfg.salvar()

    launcher: Path | None = None
    symlink: Path | None = None
    if criar_launcher:
        try:
            desktop.mkdir(parents=True, exist_ok=True)
            launcher = desktop / "launch R4.desktop"
            launcher.write_text(_LAUNCHER.format(ini=pasta / "R4.ini"))
            launcher.chmod(0o775)
            symlink = desktop / "R4"
            if symlink.is_symlink() or symlink.exists():
                symlink = None  # não sobrescreve o que já existe no Desktop
            else:
                symlink.symlink_to(pasta)
        except OSError as e:
            raise ErroInstalacao(f"Falha ao criar o launcher: {e}") from e

    return ResultadoInstalacao(
        pasta_config=pasta,
        backup_anterior=backup_anterior,
        launcher=launcher,
        symlink_desktop=symlink,
    )
