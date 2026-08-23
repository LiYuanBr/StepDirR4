"""Pré-checagens do instalador (F3).

Verifica o ambiente antes de tocar no sistema: linuxcnc-uspace instalado,
kernel PREEMPT-RT, GTK3/PyGObject e versão do LinuxCNC na whitelist dos
drivers. Os `.so` não expõem versão — a validação real é o `halcmd
loadrt` de teste, feito na verificação final (ver `drivers.testar_driver`),
porque só faz sentido com o driver já instalado.
"""

from __future__ import annotations

from dataclasses import dataclass

from .execucao import ExecutarSistema

VERSOES_SUPORTADAS: tuple[str, ...] = ("2.9",)
"""Prefixos de versão do linuxcnc-uspace suportados pelos .so embutidos
(compilados para o ISO Debian 12, LinuxCNC 2.9.x)."""


@dataclass(frozen=True)
class Checagem:
    """Resultado de uma pré-checagem, pronto para listar na GUI."""

    id: str
    rotulo: str
    ok: bool
    detalhe: str


def _versao_linuxcnc(executar: ExecutarSistema) -> str | None:
    """Versão do pacote linuxcnc-uspace, ou None se não instalado."""
    saida = executar(
        ["dpkg-query", "-W", "-f=${db:Status-Status} ${Version}",
         "linuxcnc-uspace"]
    )
    if not saida.ok:
        return None
    partes = saida.stdout.strip().split()
    if len(partes) != 2 or partes[0] != "installed":
        return None
    return partes[1]


def _tem_gtk() -> bool:
    try:
        import gi

        gi.require_version("Gtk", "3.0")
        return True
    except (ImportError, ValueError):
        return False


def pre_checagens(executar: ExecutarSistema) -> list[Checagem]:
    """Roda todas as pré-checagens. Nenhuma altera o sistema."""
    resultados: list[Checagem] = []

    versao = _versao_linuxcnc(executar)
    resultados.append(Checagem(
        "linuxcnc",
        "LinuxCNC instalado (linuxcnc-uspace)",
        versao is not None,
        f"versão {versao}" if versao else
        "não encontrado — no Debian 12/13: sudo apt install linuxcnc-uspace; "
        "em outras distros (Ubuntu/Pop!_OS não têm o pacote) use o ISO "
        "oficial: https://linuxcnc.org/downloads/",
    ))

    uname = executar(["uname", "-v"])
    rt = uname.ok and (
        "PREEMPT_RT" in uname.stdout or "PREEMPT RT" in uname.stdout
    )
    resultados.append(Checagem(
        "kernel_rt",
        "Kernel de tempo real (PREEMPT-RT)",
        rt,
        uname.stdout.strip() if rt else
        "no Debian: sudo apt install linuxcnc-uspace e reinicie pelo "
        "kernel RT (o pacote traz o kernel PREEMPT-RT junto); em outras "
        "distros use o ISO oficial: https://linuxcnc.org/downloads/",
    ))

    gtk = _tem_gtk()
    resultados.append(Checagem(
        "gtk",
        "GTK3/PyGObject (python3-gi + gir1.2-gtk-3.0)",
        gtk,
        "presente" if gtk else "pacotes python3-gi/gir1.2-gtk-3.0 ausentes",
    ))

    suportada = versao is not None and versao.startswith(VERSOES_SUPORTADAS)
    resultados.append(Checagem(
        "versao_suportada",
        "Versão do LinuxCNC suportada pelos drivers",
        suportada,
        f"versão {versao} — suportadas: "
        + ", ".join(f"{v}.x" for v in VERSOES_SUPORTADAS)
        if versao else "LinuxCNC não instalado",
    ))

    return resultados


TUTORIAL_LINUXCNC = """\
Como instalar o LinuxCNC

Opção 1 — ISO oficial (recomendada):
  1. Baixe o ISO em https://linuxcnc.org/downloads/
     (Debian 13 com kernel PREEMPT-RT e LinuxCNC 2.9 já prontos).
  2. Grave o ISO em um pendrive (ex.: balenaEtcher) e instale no
     computador que vai comandar a máquina.
  3. Rode este instalador de novo — as pendências somem.

Opção 2 — Debian 12 ou 13 já instalado:
  1. Configure o repositório oficial do LinuxCNC:
       wget https://www.linuxcnc.org/linuxcnc-install.sh
       chmod +x linuxcnc-install.sh
       sudo ./linuxcnc-install.sh
  2. Se o script não instalar tudo: sudo apt install linuxcnc-uspace
  3. Reinicie e escolha o kernel PREEMPT-RT no menu de boot.

Atenção: Ubuntu e Pop!_OS não têm o pacote linuxcnc-uspace nem kernel
realtime disponível — nessas distros, use a Opção 1."""
"""Tutorial PT-BR de instalação do LinuxCNC (fontes: linuxcnc.org/downloads
e docs oficiais; verificado em 2026-08-23)."""


def precisa_tutorial_linuxcnc(checagens: list[Checagem]) -> bool:
    """True se alguma pendência é resolvida instalando o LinuxCNC."""
    return any(
        not c.ok and c.id in ("linuxcnc", "kernel_rt", "versao_suportada")
        for c in checagens
    )


def texto_checagens(checagens: list[Checagem]) -> str:
    """Relatório PT-BR das pré-checagens (uma linha por item)."""
    linhas = [
        f"{'✓' if c.ok else '✗'} {c.rotulo} — {c.detalhe}" for c in checagens
    ]
    if all(c.ok for c in checagens):
        linhas.append("")
        linhas.append("Tudo pronto para instalar.")
    else:
        linhas.append("")
        linhas.append(
            "Há pendências. Você pode continuar mesmo assim, mas a "
            "instalação pode não funcionar até resolvê-las."
        )
    return "\n".join(linhas)
