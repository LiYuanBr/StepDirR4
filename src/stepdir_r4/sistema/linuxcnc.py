"""Processo do LinuxCNC — detectar, parar e reabrir (botão Reiniciar da F4).

Detecção/parada passam pelo seam :data:`ExecutarSistema` (testável sem
máquina). A reabertura é fire-and-forget (Popen desanexado) — não cabe no
seam, que espera o processo terminar. Validação em máquina real pendente
(junto da F5), como o resto da integração de sistema.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .execucao import ExecutarSistema

MARCADORES_PROCESSO: tuple[str, ...] = ("linuxcncsvr", "milltask")
"""Processos que só existem com o LinuxCNC aberto (o nome genérico
"linuxcnc" casaria com o próprio configurador via caminho da config)."""


def linuxcnc_rodando(executar: ExecutarSistema) -> bool:
    return any(
        executar(["pgrep", "-f", m]).codigo == 0 for m in MARCADORES_PROCESSO
    )


def parar_linuxcnc(executar: ExecutarSistema) -> None:
    """SIGTERM nos processos do LinuxCNC (o script oficial trata e limpa)."""
    for m in MARCADORES_PROCESSO:
        executar(["pkill", "-TERM", "-f", m])


def abrir_linuxcnc(pasta_config: Path) -> bool:
    """Reabre o LinuxCNC com a config da pasta, desanexado do configurador.
    False se o comando `linuxcnc` não existe no sistema."""
    if shutil.which("linuxcnc") is None:
        return False
    subprocess.Popen(
        ["linuxcnc", str(pasta_config / "R4.ini")],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True
