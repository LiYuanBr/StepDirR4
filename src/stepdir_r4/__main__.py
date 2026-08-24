"""CLI do StepDir R4.

`python3 -m stepdir_r4` (sem argumentos) abre o wizard GTK de instalação.
`configurar [--pasta ...]` abre o configurador GTK da config instalada (F4).
Sem GUI:
  `instalar [--mesa-x 800 --mesa-y 600]`  monta ~/linuxcnc/configs/R4 (F1)
  `checar`                                pré-checagens + estado dos drivers (F3)
  `rede [--dispositivo eth0] [--ip ...]`  cria a conexão StepDirR4 via nmcli (F3)
  `drivers`                               instala os .so via pkexec (F3)
  `verificar [--com-halrun]`              ping na placa + hash dos drivers (F3)
"""

from __future__ import annotations

import argparse
import os
import sys

from . import sistema
from .core import ErroConfigR4, instalar_config


def _cmd_instalar(args: argparse.Namespace) -> int:
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


def _cmd_checar(_args: argparse.Namespace) -> int:
    checagens = sistema.pre_checagens(sistema.executar_real)
    print(sistema.texto_checagens(checagens))
    if sistema.precisa_tutorial_linuxcnc(checagens):
        print()
        print(sistema.TUTORIAL_LINUXCNC)
    print()
    print("Drivers em /usr/lib/linuxcnc/modules:")
    print(sistema.texto_estado(sistema.estado_drivers()))
    return 0 if all(c.ok for c in checagens) else 1


def _cmd_rede(args: argparse.Namespace) -> int:
    executar = sistema.executar_real
    dispositivo = args.dispositivo
    if not dispositivo:
        dispositivos = sistema.listar_ethernet(executar)
        if len(dispositivos) == 1:
            dispositivo = dispositivos[0][0]
        else:
            nomes = ", ".join(d for d, _ in dispositivos) or "nenhum encontrado"
            print(
                f"Escolha a porta com --dispositivo (ethernet: {nomes})",
                file=sys.stderr,
            )
            return 1

    conflitos = sistema.detectar_overlap(executar, dispositivo)
    if conflitos:
        print(sistema.texto_overlap(conflitos), file=sys.stderr)

    if sistema.ip_em_uso(executar, dispositivo, args.ip) == "em_uso":
        print(
            f"Erro: o IP {args.ip} já está em uso no link da placa (arping). "
            "Escolha outro com --ip.",
            file=sys.stderr,
        )
        return 1

    resultado = sistema.criar_conexao(executar, dispositivo, args.ip)
    print(resultado.detalhe, file=None if resultado.ok else sys.stderr)
    return 0 if resultado.ok else 1


def _cmd_drivers(_args: argparse.Namespace) -> int:
    saida = sistema.instalar_drivers(sistema.executar_real)
    if saida.ok:
        print(saida.stdout.strip())
        return 0
    if saida.codigo in (126, 127):
        print("Instalação cancelada (senha não confirmada).", file=sys.stderr)
    else:
        print(f"Falha ao instalar os drivers:\n{saida.stderr.strip()}",
              file=sys.stderr)
    return 1


def _cmd_verificar(args: argparse.Namespace) -> int:
    v = sistema.verificar(sistema.executar_real)
    print(sistema.texto_verificacao(v))
    ok = v.ping_ok and sistema.drivers_ok(v.drivers)
    if args.com_halrun:
        print()
        teste = sistema.testar_driver(sistema.executar_real)
        if teste.ok:
            print("✓ halrun carregou o STEPDIR-R4 (driver compatível).")
        else:
            print(
                "✗ halrun não carregou o STEPDIR-R4 (LinuxCNC aberto? "
                f"versão incompatível?):\n{teste.stderr.strip()}"
            )
            ok = False
    return 0 if ok else 1


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

    p_conf = sub.add_parser(
        "configurar",
        help="Abre o configurador gráfico da config R4 instalada (F4).",
    )
    p_conf.add_argument("--pasta", default=None,
                        help="Pasta da config (padrão: ~/linuxcnc/configs/R4)")

    sub.add_parser(
        "checar", help="Pré-checagens do sistema + estado dos drivers."
    )

    p_rede = sub.add_parser(
        "rede", help="Cria a conexão de rede dedicada StepDirR4 (nmcli)."
    )
    p_rede.add_argument("--dispositivo", default=None,
                        help="Porta ethernet do cabo da placa (auto se só houver uma)")
    p_rede.add_argument("--ip", default=sistema.IP_HOST_PADRAO,
                        help=f"IP deste PC no link (padrão: {sistema.IP_HOST_PADRAO})")

    sub.add_parser(
        "drivers",
        help="Instala os drivers .so em /usr/lib/linuxcnc/modules (pkexec).",
    )

    p_verif = sub.add_parser(
        "verificar", help="Ping na placa + hash dos drivers instalados."
    )
    p_verif.add_argument("--com-halrun", action="store_true",
                         help="Também testa carregar o STEPDIR-R4 no halrun")

    args = parser.parse_args(argv)

    # vale para TODOS os comandos: rodar como root manda a config para
    # /root/linuxcnc (Path.home) e o LinuxCNC do usuário real nunca a vê;
    # o que precisa de root (drivers) já pede senha via pkexec
    if os.geteuid() == 0:
        print(
            "Erro: não execute como root/sudo. Rode como usuário normal; "
            "o sistema pedirá a senha quando for necessário.",
            file=sys.stderr,
        )
        return 1

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

    if args.comando == "configurar":
        try:
            from .gui.configurador import main as configurador_main
        except ImportError as e:
            print(
                "Erro: GTK3/PyGObject não encontrado (pacotes python3-gi e "
                f"gir1.2-gtk-3.0). Detalhe: {e}",
                file=sys.stderr,
            )
            return 1
        return configurador_main(args.pasta)

    comandos = {
        "instalar": _cmd_instalar,
        "checar": _cmd_checar,
        "rede": _cmd_rede,
        "drivers": _cmd_drivers,
        "verificar": _cmd_verificar,
    }
    return comandos[args.comando](args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # Ctrl+C no terminal (o GTK reergue como KeyboardInterrupt):
        # sair limpo, sem traceback. 130 = convenção 128+SIGINT.
        raise SystemExit(130) from None
