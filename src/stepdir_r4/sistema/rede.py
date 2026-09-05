"""Rede dedicada da placa (F3) — conexão NetworkManager ``StepDirR4``.

Link RJ45 direto com a placa, não é internet. ``192.168.1.177`` é o IP
da placa (hardcoded no STEPDIR-R4.so) — nunca gateway: a conexão é criada
SEM gateway + ``never-default`` para não roubar a rota de internet do PC.
Sub-rede imposta pela placa; se outra conexão ativa do PC já usa
192.168.1.0/24 (roteador doméstico comum), o instalador avisa o overlap.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass

from .execucao import ExecutarSistema, Saida

IP_PLACA = "192.168.1.177"
"""IP fixo da placa (hardcoded no STEPDIR-R4.so)."""

IP_HOST_PADRAO = "192.168.1.10"
"""IP padrão do PC no link dedicado — editável em campo avançado."""

PREFIXO_SUBREDE = "192.168.1."
NOME_CONEXAO = "StepDirR4"
NOME_TEMPORARIO = "StepDirR4-nova"
"""Nome de palco da recriação: a conexão antiga só cai depois que a nova sobe."""


def motivo_ip_invalido(ip: str) -> str | None:
    """None se o IP serve como host do PC no link da placa; senão o motivo.

    Comparações numéricas via `ipaddress` (rejeita octetos > 255 e zeros
    à esquerda — '192.168.1.0177' seria o IP da placa disfarçado)."""
    try:
        endereco = ipaddress.IPv4Address(ip.strip())
    except ValueError:
        return "não é um endereço IPv4 válido"
    rede = ipaddress.IPv4Network(PREFIXO_SUBREDE + "0/24")
    if endereco not in rede:
        return f"precisa estar na sub-rede da placa ({rede})"
    if endereco in (rede.network_address, rede.broadcast_address):
        return "é endereço de rede/broadcast, não de host"
    if endereco == ipaddress.IPv4Address(IP_PLACA):
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


ESTADOS_PT = {
    "connected": "em uso",
    "disconnected": "livre",
    "unavailable": "sem cabo",
    "unmanaged": "fora do NetworkManager",
    "connecting": "conectando",
    "deactivating": "desligando",
}
"""Estados do nmcli em PT-BR. 'disconnected' NÃO é cabo solto: é porta
sem conexão ativa — a tradução literal fazia o usuário achar que o link
da placa estava caído."""


@dataclass(frozen=True)
class PortaRede:
    """Porta ethernet candidata a receber o link da placa."""

    nome: str
    estado: str
    internet: bool
    """True se a rota default do PC sai por ela — não é a porta da placa."""

    @property
    def rotulo(self) -> str:
        if self.internet:
            return f"{self.nome} — sua internet (não é a placa)"
        return f"{self.nome} — {ESTADOS_PT.get(self.estado, self.estado)}"


def interfaces_rota_default(executar: ExecutarSistema) -> set[str]:
    """Interfaces por onde sai a rota default (a internet do PC)."""
    saida = executar(["ip", "-o", "-4", "route", "show", "default"])
    if not saida.ok:
        return set()
    nomes = set()
    for linha in saida.stdout.split("\n"):
        partes = linha.split()
        if "dev" in partes:
            nomes.add(partes[partes.index("dev") + 1])
    return nomes


def listar_portas(executar: ExecutarSistema) -> list[PortaRede]:
    """Portas ethernet, com as da internet no fim da lista.

    A porta da placa nunca é a da rota default; ordenar assim faz o
    primeiro item ser um palpite seguro para pré-seleção na GUI.
    """
    internet = interfaces_rota_default(executar)
    portas = [
        PortaRede(nome, estado, nome in internet)
        for nome, estado in listar_ethernet(executar)
    ]
    return sorted(portas, key=lambda p: p.internet)


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
    'desconhecido' (arping ausente/falhou — não bloqueia a instalação).

    Os códigos de saída (0=livre, 1=em uso) valem só para o arping do
    iputils; o arping de Habets (pacote Debian 'arping') INVERTE o
    sentido e usa outras flags. Sem confirmar a variante, 'desconhecido'."""
    versao = executar(["arping", "-V"])
    if "iputils" not in (versao.stdout + versao.stderr).lower():
        return "desconhecido"
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


def _campo(executar: ExecutarSistema, alvo: str, campo: str) -> str:
    """Um campo da conexão `alvo` (nome ou UUID); "" se o nmcli não souber."""
    saida = executar(["nmcli", "-g", campo, "connection", "show", alvo])
    return saida.stdout.strip() if saida.ok else ""


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

    # monta a nova conexão sob nome temporário: uma StepDirR4 que já
    # funcione só é apagada DEPOIS que a substituta subir (sem rollback
    # manual, uma falha no add/up destruiria o link bom da placa)
    executar(["nmcli", "connection", "delete", NOME_TEMPORARIO])  # sobra antiga, ok falhar

    criar = executar([
        "nmcli", "connection", "add",
        "type", "ethernet",
        "con-name", NOME_TEMPORARIO,
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

    # a partir daqui usamos o UUID: o nome ainda vai mudar, e depois de
    # apagar a StepDirR4 antiga pode haver dois perfis com o mesmo nome
    # por um instante (o NetworkManager permite id repetido)
    alvo = _campo(executar, NOME_TEMPORARIO, "connection.uuid") or NOME_TEMPORARIO

    ativar = executar(["nmcli", "connection", "up", alvo])
    if not ativar.ok:
        executar(["nmcli", "connection", "delete", alvo])
        return ResultadoRede(
            False,
            f"Conexão criada, mas não ativou (cabo conectado?): "
            f"{ativar.stderr.strip()} — a conexão {NOME_CONEXAO} anterior, "
            f"se existia, foi mantida.",
        )

    executar(["nmcli", "connection", "delete", NOME_CONEXAO])  # ok falhar
    executar([
        "nmcli", "connection", "modify", alvo,
        "connection.id", NOME_CONEXAO,
    ])
    # confere no sistema em vez de confiar no código de saída do modify
    nome_final = _campo(executar, alvo, "connection.id") or NOME_TEMPORARIO
    detalhe = (
        f"Conexão {nome_final} ativa em {dispositivo} com IP {ip}/24 "
        f"(sem gateway — sua internet não é afetada)."
    )
    if nome_final != NOME_CONEXAO:
        detalhe += (
            f" Atenção: o nome ficou {nome_final} em vez de {NOME_CONEXAO}. "
            f"A rede funciona, mas renomeie em Configurações → Rede (ou "
            f"`nmcli connection modify {nome_final} connection.id "
            f"{NOME_CONEXAO}`): com o nome temporário, uma próxima execução "
            f"deste passo apaga esta conexão antes de criar a substituta."
        )
    return ResultadoRede(True, detalhe)


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
