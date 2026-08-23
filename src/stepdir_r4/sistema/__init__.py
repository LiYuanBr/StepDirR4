"""stepdir_r4.sistema — integração de sistema do instalador (F3).

Pré-checagens, rede dedicada da placa (nmcli), drivers (pkexec + helper)
e verificação final. Tudo atrás do seam :data:`ExecutarSistema` — a
lógica testa sem máquina real (tech-stack §Testes).
"""

from __future__ import annotations

from dataclasses import dataclass

from .checagens import Checagem, pre_checagens, texto_checagens
from .drivers import (
    EstadoDriver,
    drivers_ok,
    estado_drivers,
    instalar_drivers,
    testar_driver,
    texto_estado,
)
from .execucao import ExecutarSistema, Saida, executar_real
from .rede import (
    IP_HOST_PADRAO,
    IP_PLACA,
    NOME_CONEXAO,
    ResultadoRede,
    criar_conexao,
    detectar_overlap,
    ip_em_uso,
    listar_ethernet,
    motivo_ip_invalido,
    pingar_placa,
    texto_overlap,
)


@dataclass(frozen=True)
class Verificacao:
    """Verificação final da instalação: placa responde? drivers íntegros?"""

    ping_ok: bool
    drivers: list[EstadoDriver]


def verificar(executar: ExecutarSistema) -> Verificacao:
    return Verificacao(
        ping_ok=pingar_placa(executar).ok,
        drivers=estado_drivers(),
    )


def texto_verificacao(v: Verificacao) -> str:
    linhas = [
        ("✓ Placa respondeu ao ping em " + IP_PLACA)
        if v.ping_ok
        else (
            f"✗ Placa não respondeu ao ping em {IP_PLACA} — confira o cabo "
            "RJ45 e se a conexão StepDirR4 está ativa."
        ),
        "",
        "Drivers em /usr/lib/linuxcnc/modules:",
        texto_estado(v.drivers),
    ]
    return "\n".join(linhas)


__all__ = [
    "Checagem",
    "EstadoDriver",
    "ExecutarSistema",
    "IP_HOST_PADRAO",
    "IP_PLACA",
    "NOME_CONEXAO",
    "ResultadoRede",
    "Saida",
    "Verificacao",
    "criar_conexao",
    "detectar_overlap",
    "drivers_ok",
    "estado_drivers",
    "executar_real",
    "instalar_drivers",
    "ip_em_uso",
    "listar_ethernet",
    "motivo_ip_invalido",
    "pingar_placa",
    "pre_checagens",
    "testar_driver",
    "texto_checagens",
    "texto_estado",
    "texto_overlap",
    "texto_verificacao",
    "verificar",
]
