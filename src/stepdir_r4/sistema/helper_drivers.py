#!/usr/bin/env python3
"""Helper root mínimo — instala os drivers .so da StepDir R4.

Chamado via ``pkexec python3 helper_drivers.py <pasta_origem>``; nunca
importa nada do pacote (pkexec limpa o ambiente e o PYTHONPATH some).
Faz backup datado de cada ``.so`` existente em /usr/lib/linuxcnc/modules
e instala os novos com dono root:root e modo 644 (equivalente a
``install -m 644 -o root -g root``). Sem GUI, sem rede, sem nada além
do estritamente necessário — roda como root.
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

DRIVERS = ("encoder.so", "pwmgen.so", "STEPDIR-R4.so")
DIR_MODULOS = Path("/usr/lib/linuxcnc/modules")


def instalar(
    origem: Path, destino: Path = DIR_MODULOS, como_root: bool = True
) -> list[str]:
    """Copia os 3 drivers de `origem` para `destino`, com backup datado.

    `como_root=False` só existe para os testes (pula o chown root:root).
    Devolve o relatório, uma linha por ação.
    """
    faltando = [n for n in DRIVERS if not (origem / n).is_file()]
    if faltando:
        raise SystemExit(
            f"pasta de origem inválida ({origem}): faltam {', '.join(faltando)}"
        )

    destino.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    relatorio: list[str] = []
    for nome in DRIVERS:
        alvo = destino / nome
        if alvo.exists():
            backup = destino / f"{nome}.bak-{carimbo}"
            shutil.copy2(alvo, backup)
            relatorio.append(f"backup: {backup}")
        temporario = destino / f".{nome}.novo"
        shutil.copyfile(origem / nome, temporario)
        os.chmod(temporario, 0o644)
        if como_root:
            os.chown(temporario, 0, 0)
        os.replace(temporario, alvo)
        relatorio.append(f"instalado: {alvo}")
    return relatorio


def main(argv: list[str]) -> int:
    if os.geteuid() != 0:
        print("este helper deve rodar como root (via pkexec)", file=sys.stderr)
        return 1
    if len(argv) != 2:
        print(f"uso: {argv[0]} <pasta_com_os_drivers>", file=sys.stderr)
        return 2
    for linha in instalar(Path(argv[1]).resolve()):
        print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
