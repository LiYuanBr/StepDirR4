"""Drivers da placa (F3) — estado por hash, instalação via pkexec, teste halrun.

Risco documentado (tech-stack §Sistema): ``encoder.so``/``pwmgen.so``
sobrescrevem componentes stock e um ``apt upgrade`` do linuxcnc-uspace
restaura os originais em silêncio. Por isso o estado é comparado por
hash SHA-256 com os `.so` embutidos — é a base do "verificar/reinstalar".
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .execucao import ExecutarSistema, Saida
from .helper_drivers import DIR_INSTALADO, DIR_MODULOS, DRIVERS, ORIGEM_INSTALADA


@contextmanager
def dir_drivers_embutidos():
    """Caminho real (Path) da pasta com os 3 `.so` embutidos.

    Instalado pelo .deb, os drivers ficam fora do pacote Python (o
    dh_python3 renomearia/pinaria qualquer `.so` em dist-packages) em
    ORIGEM_INSTALADA — a única origem que o helper instalado aceita.
    """
    if ORIGEM_INSTALADA.is_dir():
        yield ORIGEM_INSTALADA
        return
    origem = resources.files("stepdir_r4").joinpath("data/drivers")
    with resources.as_file(origem) as pasta:
        yield pasta


def _sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


@dataclass(frozen=True)
class EstadoDriver:
    """Situação de um `.so` instalado frente ao embutido no app."""

    nome: str
    estado: str  # "instalado" | "diferente" | "ausente"


def estado_drivers(dir_modulos: Path = DIR_MODULOS) -> list[EstadoDriver]:
    """Compara hash dos `.so` em `dir_modulos` com os embutidos.

    "diferente" cobre tanto o componente stock quanto um driver antigo —
    nos dois casos a ação é a mesma: (re)instalar.
    """
    resultado: list[EstadoDriver] = []
    with dir_drivers_embutidos() as origem:
        for nome in DRIVERS:
            instalado = dir_modulos / nome
            if not instalado.is_file():
                estado = "ausente"
            elif _sha256(instalado) == _sha256(origem / nome):
                estado = "instalado"
            else:
                estado = "diferente"
            resultado.append(EstadoDriver(nome, estado))
    return resultado


def drivers_ok(estados: list[EstadoDriver]) -> bool:
    return all(e.estado == "instalado" for e in estados)


HELPER_INSTALADO = DIR_INSTALADO / "helper_drivers.py"
"""Caminho do helper quando instalado pelo .deb (F5). O polkit casa a ação
da `.policy` pelo caminho do PROGRAMA executado — por isso o pkexec deve
executar o helper direto (shebang + executável), nunca `pkexec python3
helper`, que resolveria para o python3 e cairia no prompt genérico."""


def instalar_drivers(executar: ExecutarSistema) -> Saida:
    """Instala os `.so` embutidos via pkexec + helper (prompt de senha).

    O helper faz backup datado dos originais e ``install -m 644 -o root
    -g root``. pkexec devolve 126/127 quando o usuário cancela/nega.
    Instalado pelo .deb, o helper roda direto (ação da `.policy`, prompt
    PT-BR); rodando do código-fonte, via python3 (prompt genérico).
    """
    with dir_drivers_embutidos() as origem:
        if HELPER_INSTALADO.is_file():
            return executar(["pkexec", str(HELPER_INSTALADO), str(origem)])
        helper = Path(__file__).with_name("helper_drivers.py")
        return executar(
            ["pkexec", sys.executable, str(helper), str(origem)]
        )


def testar_driver(executar: ExecutarSistema) -> Saida:
    """``halrun`` de teste: loadrt STEPDIR-R4 num RTAPI descartável.

    Validação real de compatibilidade (os binários não expõem versão):
    "RTAPI version mismatch" no stderr = driver incompatível com o
    LinuxCNC instalado. Falha também se o LinuxCNC estiver aberto
    (RTAPI já em uso) — a mensagem do halrun explica.
    """
    with tempfile.NamedTemporaryFile(
        "w", suffix=".hal", prefix="stepdir-r4-teste-", delete=False
    ) as arquivo:
        arquivo.write("loadrt STEPDIR-R4\n")
        caminho = arquivo.name
    try:
        return executar(["halrun", "-f", caminho])
    finally:
        Path(caminho).unlink(missing_ok=True)


def texto_estado(estados: list[EstadoDriver]) -> str:
    """Relatório PT-BR do estado dos drivers, uma linha por `.so`."""
    rotulos = {
        "instalado": "✓ instalado (idêntico ao embutido)",
        "diferente": "✗ diferente do embutido (stock ou desatualizado)",
        "ausente": "✗ ausente",
    }
    return "\n".join(f"{e.nome}: {rotulos[e.estado]}" for e in estados)
