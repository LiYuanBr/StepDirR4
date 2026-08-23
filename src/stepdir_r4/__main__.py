"""CLI do StepDir R4.

`python3 -m stepdir_r4` (sem argumentos) abre o wizard GTK de instalação (F2).
`python3 -m stepdir_r4 instalar [--mesa-x 800 --mesa-y 600]` instala pelo
terminal, sem GUI (F1).
"""

from __future__ import annotations

import argparse
import sys

from .core import ErroConfigR4, instalar_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="stepdir_r4",
        description="Instalador/configurador da placa StepDir R4 (LinuxCNC).",
    )
    sub = parser.add_subparsers(dest="comando")

    sub.add_parser(
        "wizard", help="Abre o assistente gráfico de instalação (padrão)."
    )

    p_inst = sub.add_parser(
        "instalar", help="Monta ~/linuxcnc/configs/R4 a partir dos templates."
    )
    p_inst.add_argument("--mesa-x", type=float, default=800.0,
                        help="Dimensão X da mesa em mm (padrão: 800)")
    p_inst.add_argument("--mesa-y", type=float, default=600.0,
                        help="Dimensão Y da mesa em mm (padrão: 600)")
    p_inst.add_argument("--sem-launcher", action="store_true",
                        help="Não cria launcher/atalho no Desktop")

    args = parser.parse_args(argv)

    if args.comando in (None, "wizard"):
        try:
            from .gui.wizard import main as wizard_main
        except ImportError as e:
            print(
                "Erro: GTK3/PyGObject não encontrado (pacotes python3-gi e "
                f"gir1.2-gtk-3.0). Detalhe: {e}\n"
                "Alternativa sem GUI: python3 -m stepdir_r4 instalar",
                file=sys.stderr,
            )
            return 1
        return wizard_main()

    try:
        res = instalar_config(
            mesa_x=args.mesa_x,
            mesa_y=args.mesa_y,
            criar_launcher=not args.sem_launcher,
        )
    except ErroConfigR4 as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1

    print(f"Configuração criada em {res.pasta_config}")
    if res.backup_anterior:
        print(f"Configuração anterior preservada em {res.backup_anterior}")
    if res.launcher:
        print(f"Launcher criado: {res.launcher}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
