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
    # Recursos de duas linhas em polaridades opostas (home/limites): expõe
    # `.polaridade_invertida`, que troca o `.not` de lado entre as duas.
    com_polaridade_par: bool = False


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
    # papel especial: "sinal" | "abs" (visões do SCALE) | "habilitado" | "pino"
    #                 | "invertido" | "polaridade_par"
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
            com_polaridade_par=True,
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


# ---- eixo A opcional (F4) -------------------------------------------------
# O toggle mexe em dois arquivos de uma vez (por isso não usa alvos/recurso):
#   R4.ini — [KINS]JOINTS 4↔3, [KINS]KINEMATICS coordinates XYZA↔XYZ,
#            [TRAJ]COORDINATES "X Y Z A"↔"X Y Z";
#   R4.hal — comenta/descomenta as linhas que usam pinos joint.3.* (só elas
#            quebram o load quando JOINTS=3; pid3/encoder3/R4.joint.3 existem
#            sempre). Validação halrun/máquina real pendente (junto da F5).

EIXO_A_INI: tuple[tuple[str, str, str, str], ...] = (
    # (secao, chave, valor com eixo A, valor sem eixo A)
    ("KINS", "JOINTS", "4", "3"),
    ("KINS", "KINEMATICS",
     "trivkins coordinates=XYZA", "trivkins coordinates=XYZ"),
    ("TRAJ", "COORDINATES", "X Y Z A", "X Y Z"),
)

EIXO_A_HAL_PADROES: tuple[str, ...] = (
    r"net\s+JOINT3enable\s+<=",
    r"net\s+JOINT3pos-fb\s+=>",
    r"net\s+JOINT3pos-cmd",
)


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
              descricao="Menor posição que o eixo pode alcançar (início da "
                        "área útil). O LinuxCNC não executa movimentos além "
                        "deste valor."),
        Campo(f"{eixo}.max_limit", "Limite máximo", eixo, Classe.BASICA,
              Tipo.NUMERO, u_pos, alvos=ambos("MAX_LIMIT"),
              descricao="Maior posição que o eixo pode alcançar (fim da "
                        "área útil). Definido na instalação como a dimensão "
                        "da mesa + 15."),
        Campo(f"{eixo}.max_velocity", "Velocidade máxima do eixo", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, minimo=0,
              alvos=ambos("MAX_VELOCITY"),
              descricao="Velocidade máxima deste eixo. Valores acima da "
                        "capacidade do motor causam perda de passos."),
        Campo(f"{eixo}.max_acceleration", "Aceleração máxima", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_acel, minimo=0,
              alvos=ambos("MAX_ACCELERATION"),
              descricao="Taxa de aceleração e desaceleração do eixo. "
                        "Valores altos tornam os movimentos mais ágeis, mas "
                        "podem causar perda de passos."),
        Campo(f"{eixo}.max_maxaccel", "Aceleração máxima do driver", eixo,
              Classe.AVANCADA, Tipo.NUMERO, alvos=so_joint("MAX_MAXACCEL"),
              descricao="Limite de aceleração do driver do motor "
                        "(MAX_MAXACCEL). Padrão: 5000; raramente requer "
                        "ajuste."),
        Campo(f"{eixo}.sentido_invertido", "Inverter sentido do movimento", eixo,
              Classe.BASICA, Tipo.BOOL, alvos=so_joint("SCALE"), papel="sinal",
              descricao="Inverte o sentido de deslocamento do eixo, "
                        "trocando o sinal do SCALE — equivalente à inversão "
                        "de direção do Mach3."),
        Campo(f"{eixo}.scale", "SCALE (valor absoluto)", eixo, Classe.BASICA,
              Tipo.NUMERO, u_scale, alvos=so_joint("SCALE"), papel="abs",
              descricao="Quantidade de pulsos necessária para deslocar o "
                        "eixo em uma unidade. Depende da transmissão mecânica "
                        "(fuso de esferas ou cremalheira). Alterar o SCALE "
                        "recalcula o DEADBAND automaticamente."),
        Campo(f"{eixo}.home_offset", "Afastamento após o home", eixo,
              Classe.BASICA, Tipo.NUMERO, u_pos, alvos=so_joint("HOME_OFFSET"),
              descricao="Distância que o eixo se afasta do sensor ao "
                        "concluir o home. O sinal depende da máquina "
                        "(Spark V2: -1 em X/Y, +1 em Z)."),
        Campo(f"{eixo}.home_search_vel", "Velocidade de busca do home", eixo,
              Classe.BASICA, Tipo.NUMERO, u_vel,
              alvos=so_joint("HOME_SEARCH_VEL"),
              descricao="Velocidade com que o eixo se aproxima do sensor "
                        "de home. No eixo Z, o sinal é oposto ao do SCALE — "
                        "ajustado automaticamente, com possibilidade de "
                        "sobrescrever."),
        Campo(f"{eixo}.home_latch_vel", "Velocidade de referenciamento", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, alvos=so_joint("HOME_LATCH_VEL"),
              descricao="Velocidade reduzida com que o eixo se afasta do "
                        "sensor para registrar a referência — a calibração "
                        "ocorre no afastamento do sensor, não no "
                        "acionamento."),
        Campo(f"{eixo}.home_sequence", "Sequência do home", eixo,
              Classe.AVANCADA, Tipo.INTEIRO, alvos=so_joint("HOME_SEQUENCE"),
              descricao="Ordem de referenciamento dos eixos (valores "
                        "menores primeiro). Padrão da Spark V2: Z=0, X=1, "
                        "Y=2."),
        Campo(f"{eixo}.home_final_vel", "Velocidade final do home", eixo,
              Classe.AVANCADA, Tipo.NUMERO, u_vel, alvos=so_joint("HOME_FINAL_VEL"),
              descricao="Velocidade do trecho final do home, do sensor "
                        "até a posição de afastamento (HOME_OFFSET)."),
        Campo(f"{eixo}.deadband", "DEADBAND", eixo, Classe.AVANCADA, Tipo.NUMERO,
              alvos=so_joint("DEADBAND"),
              descricao="Zona morta do controle de posição. Recalculado "
                        "automaticamente (1/SCALE×0,75) quando o SCALE é "
                        "alterado; normalmente não requer ajuste manual."),
    ]


_CONVENCAO_RECURSO = {
    "emergencia": "Convenção da placa: entrada 1.",
    "home_limites": "Convenção da placa: entrada 2. O mesmo pino atende "
                    "home e fim de curso (o par usa as duas polaridades).",
    "probe_1": "Entrada genérica de sonda no HAL; os parâmetros dos probes "
               "ficam na aba Probes.",
    "probe_2": "Entrada genérica de sonda no HAL; os parâmetros dos probes "
               "ficam na aba Probes.",
    "spindle_cw": "Convenção da placa: saída 0.",
    "spindle_ccw": "Convenção da placa: saída 1.",
    "esquadro_refrigeracao": "Convenção da placa: saída 2.",
}


def _campos_io() -> list[Campo]:
    campos: list[Campo] = []
    for rid, rec in RECURSOS.items():
        classe = Classe.AVANCADA if rid in _RECURSOS_AVANCADOS else Classe.BASICA
        rotulo = _ROTULO_RECURSO[rid]
        tipo_pino = Tipo.PINO_ENTRADA if rec.direcao == "entrada" else Tipo.PINO_SAIDA
        maximo = 6 if rec.direcao == "entrada" else 2
        convencao = _CONVENCAO_RECURSO[rid]
        campos.append(Campo(f"io.{rid}.habilitado", f"{rotulo} — habilitado",
                            "io", classe, Tipo.BOOL, papel="habilitado", recurso=rid,
                            descricao="Ativa ou desativa o recurso no "
                                      "R4.hal, descomentando ou comentando "
                                      "as linhas correspondentes. "
                                      + convencao))
        campos.append(Campo(f"io.{rid}.pino", f"{rotulo} — pino", "io", classe,
                            tipo_pino, minimo=0, maximo=maximo,
                            papel="pino", recurso=rid,
                            descricao=("Número da entrada da placa (0 a 6) "
                                       if rec.direcao == "entrada" else
                                       "Número da saída da placa (0 a 2) ")
                                      + "à qual o fio está conectado. "
                                      + convencao))
        if rec.com_invertido:
            campos.append(Campo(f"io.{rid}.invertido",
                                f"{rotulo} — inverter sinal (normal fechado)",
                                "io", classe, Tipo.BOOL,
                                papel="invertido", recurso=rid,
                                descricao="Para sensores ou botões do tipo "
                                          "normal fechado (NF): acrescenta o "
                                          "sufixo .not ao pino, invertendo o "
                                          "sinal."))
        if rec.com_polaridade_par:
            campos.append(Campo(f"io.{rid}.polaridade_invertida",
                                f"{rotulo} — sensor desliga ao detectar",
                                "io", classe, Tipo.BOOL,
                                papel="polaridade_par", recurso=rid,
                                descricao="Marque para sensores que ficam "
                                          "ligados em repouso e desligam ao "
                                          "detectar (indutivo NPN normal "
                                          "aberto). O mesmo pino serve ao home "
                                          "e ao fim de curso em polaridades "
                                          "opostas, então o .not troca de lado "
                                          "entre as duas linhas em vez de "
                                          "entrar nas duas."))
    return campos


def _montar() -> dict[str, Campo]:
    campos: list[Campo] = [
        Campo("geral.max_linear_velocity", "Velocidade linear máxima", "geral",
              Classe.BASICA, Tipo.NUMERO, "mm/s", minimo=0,
              # [TRAJ] primeiro: é o limite efetivo da máquina (o de
              # [DISPLAY] só limita a interface) e o template de fábrica
              # traz os dois divergentes — a GUI lê o alvo [0]
              alvos=(AlvoIni("TRAJ", "MAX_LINEAR_VELOCITY"),
                     AlvoIni("DISPLAY", "MAX_LINEAR_VELOCITY")),
              descricao="Velocidade máxima da máquina, em mm/s — divida o "
                        "valor em mm/min por 60 (ex.: 9000/60 = 150 mm/s). "
                        "Ao salvar, o valor é gravado nas seções [TRAJ] e "
                        "[DISPLAY] do R4.ini."),
        Campo("geral.default_linear_velocity", "Velocidade linear padrão", "geral",
              Classe.BASICA, Tipo.NUMERO, "mm/s", minimo=0,
              # aqui o [DISPLAY] é a fonte certa (50 = 30% de 150); o
              # [TRAJ] de fábrica traz 150, defasado — sincronizado ao salvar
              alvos=(AlvoIni("DISPLAY", "DEFAULT_LINEAR_VELOCITY"),
                     AlvoIni("TRAJ", "DEFAULT_LINEAR_VELOCITY")),
              descricao="Velocidade inicial do movimento manual (jog), em "
                        "mm/s. Valor recomendado: cerca de 30% da velocidade "
                        "máxima (ex.: 3000/60 = 50 mm/s)."),
        Campo("geral.max_angular_velocity", "Velocidade angular máxima", "geral",
              Classe.AVANCADA, Tipo.NUMERO, "graus/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "MAX_ANGULAR_VELOCITY"),),
              descricao="Velocidade máxima de rotação do eixo A exibida "
                        "no LinuxCNC (valor usual: 100 graus/s)."),
        Campo("geral.default_angular_velocity", "Velocidade angular padrão", "geral",
              Classe.AVANCADA, Tipo.NUMERO, "graus/s", minimo=0,
              alvos=(AlvoIni("DISPLAY", "DEFAULT_ANGULAR_VELOCITY"),),
              descricao="Velocidade inicial do movimento manual (jog) do "
                        "eixo A (valor usual: 15 graus/s)."),
        Campo("geral.program_prefix", "Pasta padrão de programas", "geral",
              Classe.AVANCADA, Tipo.TEXTO,
              alvos=(AlvoIni("DISPLAY", "PROGRAM_PREFIX"),),
              descricao="Pasta onde o LinuxCNC busca os programas "
                        "G-code. Definida na instalação como a Área de "
                        "Trabalho do usuário."),
        # spindle
        Campo("spindle.on_delay", "Atraso ao ligar", "spindle", Classe.BASICA,
              Tipo.NUMERO, "s", minimo=0, alvos=(AlvoIni("SPINDLE", "ON_DELAY"),),
              descricao="Tempo, em segundos, que a máquina aguarda após "
                        "ligar o spindle antes de iniciar o corte, "
                        "permitindo que ele atinja a rotação programada "
                        "(Spark V2: 5 s)."),
        Campo("spindle.off_delay", "Atraso ao desligar", "spindle", Classe.BASICA,
              Tipo.NUMERO, "s", minimo=0, alvos=(AlvoIni("SPINDLE", "OFF_DELAY"),),
              descricao="Tempo, em segundos, que a máquina aguarda após "
                        "desligar o spindle antes de prosseguir."),
        Campo("spindle.max_rpm", "Rotação máxima", "spindle", Classe.BASICA,
              Tipo.NUMERO, "rpm", minimo=0, alvos=(AlvoIni("SPINDLE", "MAX_RPM"),),
              descricao="Rotação máxima do spindle, conforme o modelo "
                        "instalado (Spark V2: 24000 rpm)."),
        # probes (valores INI; as entradas físicas ficam na aba io)
        Campo("probes.proc_sonda", "Descida de procura da sonda", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FLUTUANTE", "PROC_SONDA"),),
              descricao="Distância máxima que o eixo Z desce à procura "
                        "do contato com a sonda flutuante. Valor sempre "
                        "negativo (movimento de descida); o sinal é aplicado "
                        "automaticamente."),
        Campo("probes.espessura_do_probe", "Espessura do probe", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm", minimo=0,
              alvos=(AlvoIni("PROBE_FLUTUANTE", "ESPESSURA_DO_PROBE"),),
              descricao="Espessura da sonda flutuante. Após o toque, o "
                        "eixo Z desconta este valor para zerar exatamente na "
                        "superfície da peça (Spark V2: 19,4 mm)."),
        Campo("probes.posi_seguro_z", "Altura segura do Z", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm", minimo=-20, maximo=-10,
              alvos=(AlvoIni("PROBE_FIXO", "POSI_SEGURO_Z"),),
              descricao="Altura do eixo Z durante o deslocamento até o "
                        "probe fixo. Aceita somente valores entre -10 e "
                        "-20."),
        Campo("probes.posi_probe_x", "Posição X do probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_X"),),
              descricao="Coordenada X da mesa em que o probe fixo está "
                        "instalado (Spark V2: 740)."),
        Campo("probes.posi_probe_y", "Posição Y do probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_Y"),),
              descricao="Coordenada Y da mesa em que o probe fixo está "
                        "instalado (Spark V2: 584)."),
        Campo("probes.posi_probe_z", "Descida até o probe fixo", "probes",
              Classe.BASICA, Tipo.NUMERO, "mm",
              alvos=(AlvoIni("PROBE_FIXO", "POSI_PROBE_Z"),),
              descricao="Distância que o eixo Z desce até tocar o probe "
                        "fixo. Valor negativo, como a descida de procura "
                        "(Spark V2: -30)."),
    ]
    campos += _campos_eixo("eixo_x", "AXIS_X", "JOINT_0", angular=False)
    campos += _campos_eixo("eixo_y", "AXIS_Y", "JOINT_1", angular=False)
    campos += _campos_eixo("eixo_z", "AXIS_Z", "JOINT_2", angular=False)
    campos.append(
        Campo("eixo_a.habilitado", "Eixo A habilitado", "eixo_a",
              Classe.BASICA, Tipo.BOOL, papel="eixo_a",
              descricao="O 4º eixo (rotativo) é opcional. Desabilitá-lo "
                        "ajusta a cinemática ([KINS]/[TRAJ]) e comenta as "
                        "ligações do joint 3 no R4.hal.")
    )
    campos += _campos_eixo("eixo_a", "AXIS_A", "JOINT_3", angular=True)
    campos += _campos_io()
    resultado = {c.id: c for c in campos}
    assert len(resultado) == len(campos), "ids de campo duplicados na whitelist"
    return resultado


CAMPOS: dict[str, Campo] = _montar()
