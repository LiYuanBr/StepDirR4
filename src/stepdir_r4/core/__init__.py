"""stepdir_r4.core — núcleo do instalador/configurador (interface pública).

Dois pontos de entrada: :func:`instalar_config` e :class:`ConfigR4`.
Todo o resto é vocabulário passivo (dataclasses, enums, exceções).
Decisão de interface: specs/tech-stack.md §Interface do núcleo F1 + docs/adr/0001.
"""

from .campos import AbaSpec, AlvoIni, Campo, Classe, Tipo, Valor
from .config import ConfigR4
from .erros import (
    ArquivoAlteradoExternamente,
    CampoDesconhecido,
    ConfigCorrompida,
    ConfigNaoEncontrada,
    ErroConfigR4,
    ErroInstalacao,
    ValorInvalido,
)
from .instalador import Executar, ResultadoInstalacao, instalar_config

__all__ = [
    "AbaSpec",
    "AlvoIni",
    "ArquivoAlteradoExternamente",
    "Campo",
    "CampoDesconhecido",
    "Classe",
    "ConfigCorrompida",
    "ConfigNaoEncontrada",
    "ConfigR4",
    "ErroConfigR4",
    "ErroInstalacao",
    "Executar",
    "ResultadoInstalacao",
    "Tipo",
    "Valor",
    "ValorInvalido",
    "instalar_config",
]
