"""Rede dedicada da placa (F3) — conexão NetworkManager ``StepDirR4``.

Link RJ45 direto com a placa, não é internet. ``192.168.1.177`` é o IP
da placa (hardcoded no STEPDIR-R4.so) — nunca gateway: a conexão é criada
SEM gateway + ``never-default`` para não roubar a rota de internet do PC.
Sub-rede imposta pela placa; se outra conexão ativa do PC já usa
192.168.1.0/24 (roteador doméstico comum), o instalador avisa o overlap.
"""

from __future__ import annotations

from dataclasses import dataclass

from .execucao import ExecutarSistema, Saida

IP_PLACA = "192.168.1.177"
"""IP fixo da placa (hardcoded no STEPDIR-R4.so)."""

IP_HOST_PADRAO = "192.168.1.10"
"""IP padrão do PC no link dedicado — editável em campo avançado."""

PREFIXO_SUBREDE = "192.168.1."
NOME_CONEXAO = "StepDirR4"


def motivo_ip_invalido(ip: str) -> str | None:
    """None se o IP serve como host do PC no link da placa; senão o motivo."""
    partes = ip.strip().split(".")
    if len(partes) != 4 or not all(p.isdigit() for p in partes):
        return "não é um endereço IPv4 válido"
    if ".".join(partes[:3]) + "." != PREFIXO_SUBREDE:
        return f"precisa estar na sub-rede da placa ({PREFIXO_SUBREDE}0/24)"
    final = int(partes[3])
    if final == 0 or final == 255:
        return "é endereço de rede/broadcast, não de host"
    if ip.strip() == IP_PLACA:
        return f"é o IP da própria placa ({IP_PLACA})"
    return None


def listar_ethernet(executar: ExecutarSistema) -> list[tuple[str, str]]:
    """Dispositivos ethernet vistos pelo NetworkManager: (nome, estado)."""
    saida = executar(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status"])
    if not saida.ok:
        return []
    dispositivos = []
    for linha in saida.stdout.splitlines():
        partes = linha.split(":")
        if len(partes) >= 3 and partes[1] == "ethernet":
            dispositivos.append((partes[0], partes[2]))
    return dispositivos


def detectar_overlap(executar: ExecutarSistema, dispositivo: str) -> list[str]:
    """Interfaces ≠ `dispositivo` com IP ativo em 192.168.1.0/24.

    Overlap = rota ambígua: a placa pode ficar inacessível. O instalador
    avisa e recomenda mudar a faixa do roteador.
    """
    saida = executar(["ip", "-o", "-4", "addr", "show"])
    if not saida.ok:
        return []
    conflitos = []
    for linha in saida.stdout.splitlines():
        partes = linha.split()
        if len(partes) < 4 or partes[2] != "inet":
            continue
        iface, endereco = partes[1], partes[3]
        if iface != dispositivo and endereco.startswith(PREFIXO_SUBREDE):
            conflitos.append(f"{iface}: {endereco}")
    return conflitos


def ip_em_uso(executar: ExecutarSistema, dispositivo: str, ip: str) -> str:
    """Sonda o link dedicado com arping (modo DAD): 'livre', 'em_uso' ou
    'desconhecido' (arping ausente/falhou — não bloqueia a instalação)."""
    saida = executar(
        ["arping", "-D", "-q", "-c", "2", "-w", "3", "-I", dispositivo, ip]
    )
    if saida.codigo == 0:
        return "livre"
    if saida.codigo == 1:
        return "em_uso"
    return "desconhecido"


@dataclass(frozen=True)
class ResultadoRede:
    """O que a criação da conexão fez, pronto para a GUI/terminal."""

    ok: bool
    detalhe: str


def criar_conexao(
    executar: ExecutarSistema, dispositivo: str, ip: str = IP_HOST_PADRAO
) -> ResultadoRede:
    """Cria (recriando se existir) e ativa a conexão ``StepDirR4``.

    IPv4 manual `ip`/24, SEM gateway + never-default, IPv6 ignorado,
    autoconnect prioridade 999, sem restrição de usuário (permissions
    vazio é o padrão do nmcli). Pode gerar prompt polkit — aceitável.
    """
    motivo = motivo_ip_invalido(ip)
    if motivo:
        return ResultadoRede(False, f"IP {ip} inválido: {motivo}")

    executar(["nmcli", "connection", "delete", NOME_CONEXAO])  # ok falhar

    criar = executar([
        "nmcli", "connection", "add",
        "type", "ethernet",
        "con-name", NOME_CONEXAO,
        "ifname", dispositivo,
        "ipv4.method", "manual",
        "ipv4.addresses", f"{ip}/24",
        "ipv4.never-default", "yes",
        "ipv6.method", "ignore",
        "connection.autoconnect", "yes",
        "connection.autoconnect-priority", "999",
    ])
    if not criar.ok:
        return ResultadoRede(
            False, f"nmcli não criou a conexão: {criar.stderr.strip()}"
        )

    ativar = executar(["nmcli", "connection", "up", NOME_CONEXAO])
    if not ativar.ok:
        return ResultadoRede(
            False,
            f"Conexão criada, mas não ativou (cabo conectado?): "
            f"{ativar.stderr.strip()}",
        )
    return ResultadoRede(
        True,
        f"Conexão {NOME_CONEXAO} ativa em {dispositivo} com IP {ip}/24 "
        f"(sem gateway — sua internet não é afetada).",
    )


def pingar_placa(executar: ExecutarSistema) -> Saida:
    """Um ping na placa (192.168.1.177), timeout 2 s."""
    return executar(["ping", "-c", "1", "-W", "2", IP_PLACA])


def texto_overlap(conflitos: list[str]) -> str:
    return (
        "Atenção: outra conexão deste PC já usa a faixa 192.168.1.x ("
        + "; ".join(conflitos)
        + "). Isso cria rota ambígua e a placa pode ficar inacessível. "
        "Recomendado: mudar a faixa do roteador (ex. 192.168.0.x). "
        "A conexão da placa será ancorada na interface dedicada mesmo assim."
    )
