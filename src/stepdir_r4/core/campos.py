"""Catálogo estático da whitelist: abas, campos e recursos de I/O.

A GUI (F2/F4) é gerada destes dados. Variável editável nova = 1 entrada aqui,
zero mudança de interface. Classificação básica/avançada vem do specs-readme
(revisada em specs/tech-stack.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

Valor = bool | int | float | str

ARQUIVO_INI = "R4.ini"
ARQUIVO_HAL = "R4.hal"


class Classe(Enum):
    """Destaque na GUI: básica em evidência, avançada recolhida."""

    BASICA = "basica"
    AVANCADA = "avancada"


class Tipo(Enum):
    """Tipo do campo — a GUI escolhe o widget por ele."""

    NUMERO = "numero"          # float
    INTEIRO = "inteiro"        # int
    BOOL = "bool"              # habilitar/desabilitar, inverter sentido, .not
    PINO_ENTRADA = "pino_in"   # int 0..6 (placa)
    PINO_SAIDA = "pino_out"    # int 0..2 (placa)
    TEXTO = "texto"


@dataclass(frozen=True)
class AbaSpec:
    id: str
    rotulo: str
    ordem: int


@dataclass(frozen=True)
class AlvoIni:
    secao: str
    chave: str


@dataclass(frozen=True)
class RecursoHal:
    """Um recurso do R4.hal estilo Mach3 ports-and-pins.

    `padroes`: regex, um por linha física do recurso (comentada ou não).
    A primeira linha é a referência de pino/inversão; pino novo é reescrito
    em todas as linhas, preservando o `.not` próprio de cada uma.
    """

    id: str
    direcao: str  # "entrada" | "saida"
    padroes: tuple[str, ...]
    com_invertido: bool = True  # expõe campo `.invertido` (troca o .not da 1ª linha)


@dataclass(frozen=True)
class Campo:
    """Descritor de um campo editável da whitelist."""

    id: str
    rotulo: str
    aba: str
    classe: Classe
    tipo: Tipo
    unidade: str | None = None
    minimo: float | None = None
    maximo: float | None = None
    descricao: str = ""
    # campos INI: seções/chaves espelhadas (1 edição → escrita em todos os alvos)
    alvos: tuple[AlvoIni, ...] = ()
    # papel especial: "sinal" | "abs" (visões do SCALE) | "habilitado" | "pino" | "invertido"
    papel: str | None = None
    recurso: str | None = None  # id do RecursoHal, para campos io.*


ABAS: tuple[AbaSpec, ...] = (
    AbaSpec("geral", "Geral", 0),
    AbaSpec("eixo_x", "Eixo X", 1),
    AbaSpec("eixo_y", "Eixo Y", 2),
    AbaSpec("eixo_z", "Eixo Z", 3),
    AbaSpec("eixo_a", "Eixo A", 4),
    AbaSpec("spindle", "Spindle", 5),
    AbaSpec("probes", "Probes", 6),
    AbaSpec("io", "Entradas/Saídas", 7),
)


RECURSOS: dict[str, RecursoHal] = {
    r.id: r
    for r in (
        RecursoHal(
            "emergencia",
            "entrada",
            (r"net\s+emergengia-in\s",),
        ),
        RecursoHal(
            "home_limites",
            "entrada",
            (r"net\s+all-home\s", r"net\s+all-limit\s"),
            com_invertido=False,  # o par home/limite usa as duas polaridades do pino
        ),
        RecursoHal("probe_1", "entrada", (r"net\s+probe-in0-pre\s",)),
        RecursoHal("probe_2", "entrada", (r"net\s+probe-in1-pre\s",)),
        RecursoHal(
            "spindle_cw", "saida", (r"net\s+spindle-cw\s.*R4\.output",),
            com_invertido=False,
        ),
        RecursoHal(
            "spindle_ccw", "saida", (r"net\s+spindle-ccw\s.*R4\.output",),
            com_invertido=False,
        ),
        RecursoHal(
            "esquadro_refrigeracao", "saida", (r"net\s+coolant-flood\s",),
            com_invertido=False,
        ),
    )
}

_ROTULO_RECURSO = {
    "emergencia": "Botão de emergência",
    "home_limites": "Home e fins de curso",
    "probe_1": "Probe 1",
    "probe_2": "Probe 2",
    "spindle_cw": "Spindle horário (CW)",
    "spindle_ccw": "Spindle anti-horário (CCW)",
    "esquadro_refrigeracao": "Esquadro / refrigeração",
}

# recursos cuja configuração é avançada (convenção da placa; ver CLAUDE.md)
_RECURSOS_AVANCADOS = {"home_limites"}


def _campos_eixo(eixo: str, axis: str, joint: str, angular: bool) -> list[Campo]:
    u_pos = "graus" if angular else "mm"
    u_vel = "graus/s" if angular else "mm/s"
    u_acel = "graus/s²" if angular else "mm/s²"
    u_scale = "pulsos/grau" if angular else "pulsos/mm"

    def ambos(chave: str) -> tuple[AlvoIni, ...]:
        return (AlvoIni(axis, chave), AlvoIni(joint, chave))

    def so_joint(chave: str) -> tuple[AlvoIni, ...]:
        return (AlvoIni(joint, chave),)

    return [
        Campo(f"{eixo}.min_limit", "Limite mínimo", eixo, Classe.BASICA,
              Tipo.NUMERO, u_pos, alvos=ambos("MIN_LIMIT"),
              descricao="Limite mínimo do eixo (área útil)"),
        Campo(f"{eixo}.max_limit", "Limite máximo", eixo, Classe.BASICA,
              Tipo.NUMERO, u_pos, alvos=ambos("MAX_LIMIT"),
              descricao="Limite máximo do eixo (área útil). Mesa + 15 na instalação."),
        Campo(f"{eixo}.max_velocity", "Velocidade máxima do eixo", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, minimo=0,
              alvos=ambos("MAX_VELOCITY")),
        Campo(f"{eixo}.max_acceleration", "Aceleração máxima", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_acel, minimo=0,
              alvos=ambos("MAX_ACCELERATION")),
        Campo(f"{eixo}.max_maxaccel", "Aceleração máxima do driver", eixo,
              Classe.AVANCADA, Tipo.NUMERO, alvos=so_joint("MAX_MAXACCEL")),
        Campo(f"{eixo}.sentido_invertido", "Inverter sentido do movimento", eixo,
              Classe.BASICA, Tipo.BOOL, alvos=so_joint("SCALE"), papel="sinal",
              descricao="Sinal do SCALE: como no Mach3, inverte o lado do movimento."),
        Campo(f"{eixo}.scale", "SCALE (valor absoluto)", eixo, Classe.AVANCADA,
              Tipo.NUMERO, u_scale, alvos=so_joint("SCALE"), papel="abs",
              descricao="Pulsos por unidade; depende de fuso/cremalheira."),
        Campo(f"{eixo}.home_offset", "Afastamento após o home", eixo,
              Classe.BASICA, Tipo.NUMERO, u_pos, alvos=so_joint("HOME_OFFSET"),
              descricao="Distância que o eixo se afasta do sensor no home. "
                        "Sinal livre — depende da máquina."),
        Campo(f"{eixo}.home_search_vel", "Velocidade de busca do home", eixo,
              Classe.BASICA, Tipo.NUMERO, u_vel,
              alvos=so_joint("HOME_SEARCH_VEL"),
              descricao="No eixo Z o sinal é oposto ao SCALE (sobrescrevível)."),
        Campo(f"{eixo}.home_latch_vel", "Velocidade de referenciamento", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, alvos=so_joint("HOME_LATCH_VEL")),
        Campo(f"{eixo}.home_sequence", "Sequência do home", eixo,
              Classe.AVANCADA, Tipo.INTEIRO, alvos=so_joint("HOME_SEQUENCE")),
        Campo(f"{eixo}.home_final_vel", "Velocidade final do home", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, alvos=so_joint("HOME_FINAL_VEL")),
        Campo(f"{eixo}.deadband", "DEADBAND", eixo, Classe.BASICA, Tipo.NUMERO,
              alvos=so_joint("DEADBAND"),
              descricao="Derivado: 1/ABS(SCALE)*0,75. Recalculado ao mudar o SCALE."),
    ]


def _campos_io() -> list[Campo]:
    campos: list[Campo] = []
    for rid, rec in RECURSOS.items():
        classe = Classe.AVANCADA if rid in _RECURSOS_AVANCADOS else Classe.BASICA
        rotulo = _ROTULO_RECURSO[rid]
        tipo_pino = Tipo.PINO_ENTRADA if rec.direcao == "entrada" else Tipo.PINO_SAIDA
        maximo = 6 if rec.direcao == "entrada" else 2
        campos.append(Campo(f"io.{rid}.habilitado", f"{rotulo} — habilitado",
                            "io", classe, Tipo.BOOL, papel="habilitado", recurso=rid))
        campos.append(Campo(f"io.{rid}.pino", f"{rotulo} — pino", "io", classe,
                            tipo_pino, minimo=0, maximo=maximo,
                            papel="pino", recurso=rid))
        if rec.com_invertido:
            campos.append(Campo(f"io.{rid}.invertido",
                                f"{rotulo} — inverter sinal (normal fechado)",
                                "io", classe, Tipo.BOOL,
                                papel="invertido", recurso=rid,
                                descricao="Sufixo .not no pino: inverte o sinal."))
    return campos


def _montar() -> dict[str, Campo]:
    campos: list[Campo] = [
        Campo("geral.max_linear_velocity", "Velocidade linear máxima", "geral",
              Classe.BASICA, Tipo.NUMERO, "mm/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "MAX_LINEAR_VELOCITY"),
                     AlvoIni("TRAJ", "MAX_LINEAR_VELOCITY")),
              descricao="Padrão Spark V2: 150 mm/s. Espelhado em [DISPLAY] e [TRAJ]."),
        Campo("geral.default_linear_velocity", "Velocidade linear padrão", "geral",
              Classe.BASICA, Tipo.NUMERO, "mm/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "DEFAULT_LINEAR_VELOCITY"),
                     AlvoIni("TRAJ", "DEFAULT_LINEAR_VELOCITY")),
              descricao="≈30% da máxima; velocidade do jog manual."),
        Campo("geral.max_angular_velocity", "Velocidade angular máxima", "geral",
              Classe.AVANCADA, Tipo.NUMERO, "graus/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "MAX_ANGULAR_VELOCITY"),)),
        Campo("geral.default_angular_velocity", "Velocidade angular padrão", "geral",
              Classe.AVANCADA, Tipo.NUMERO, "graus/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "DEFAULT_ANGULAR_VELOCITY"),)),
        Campo("geral.program_prefix", "Pasta padrão de programas", "geral",
              Classe.AVANCADA, Tipo.TEXTO,
              alvos=(AlvoIni("DISPLAY", "PROGRAM_PREFIX"),),
              descricao="Resolvida na instalação via xdg-user-dir DESKTOP."),
        # spindle
        Campo("spindle.on_delay", "Atraso ao ligar", "spindle", Classe.BASICA,
              Tipo.NUMERO, "s", minimo=0, alvos=(AlvoIni("SPINDLE", "ON_DELAY"),),
              descricao="Espera até o spindle atingir a rotação."),
        Campo("spindle.off_delay", "Atraso ao desligar", "spindle", Classe.BASICA,
              Tipo.NUMERO, "s", minimo=0, alvos=(AlvoIni("SPINDLE", "OFF_DELAY"),)),
        Campo("spindle.max_rpm", "Rotação máxima", "spindle", Classe.BASICA,
              Tipo.NUMERO, "rpm", minimo=0, alvos=(AlvoIni("SPINDLE", "MAX_RPM"),)),
        # probes (valores INI; as entradas físicas ficam na aba io)
        Campo("probes.proc_sonda", "Descida de procura da sonda", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FLUTUANTE", "PROC_SONDA"),),
              descricao="Sempre negativa (desce). O sinal é forçado."),
        Campo("probes.espessura_do_probe", "Espessura do probe", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm", minimo=0,
              alvos=(AlvoIni("PROBE_FLUTUANTE", "ESPESSURA_DO_PROBE"),)),
        Campo("probes.posi_seguro_z", "Altura segura do Z", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm", minimo=-20, maximo=-10,
              alvos=(AlvoIni("PROBE_FIXO", "POSI_SEGURO_Z"),),
              descricao="Somente valores entre -10 e -20."),
        Campo("probes.posi_probe_x", "Posição X do probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_X"),)),
        Campo("probes.posi_probe_y", "Posição Y do probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_Y"),)),
        Campo("probes.posi_probe_z", "Descida até o probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_Z"),)),
    ]
    campos += _campos_eixo("eixo_x", "AXIS_X", "JOINT_0", angular=False)
    campos += _campos_eixo("eixo_y", "AXIS_Y", "JOINT_1", angular=False)
    campos += _campos_eixo("eixo_z", "AXIS_Z", "JOINT_2", angular=False)
    campos += _campos_eixo("eixo_a", "AXIS_A", "JOINT_3", angular=True)
    campos += _campos_io()
    resultado = {c.id: c for c in campos}
    assert len(resultado) == len(campos), "ids de campo duplicados na whitelist"
    return resultado


CAMPOS: dict[str, Campo] = _montar()
