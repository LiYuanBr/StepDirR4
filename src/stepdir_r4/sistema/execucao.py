"""Seam de execução de comandos de sistema (F3).

Diferente do seam ``Executar`` do núcleo (que levanta exceção em falha),
os passos de sistema precisam do código de retorno: "ping falhou" e
"nmcli recusou" são resultados esperados, não exceções. Adapter de
produção: :func:`executar_real`. Adapter de teste: lambda que devolve
:class:`Saida` montada à mão.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Saida:
    """Resultado de um comando: código de retorno + stdout/stderr."""

    codigo: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.codigo == 0


ExecutarSistema = Callable[[list[str]], Saida]
"""Recebe argv, devolve Saida. Nunca levanta exceção."""


def executar_real(argv: list[str], timeout: float = 30) -> Saida:
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return Saida(127, "", f"comando não encontrado: {argv[0]}")
    except subprocess.TimeoutExpired:
        return Saida(124, "", f"tempo esgotado: {' '.join(argv)}")
    return Saida(proc.returncode, proc.stdout, proc.stderr)
