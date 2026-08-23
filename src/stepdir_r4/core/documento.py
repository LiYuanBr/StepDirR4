"""Modelo de linhas com round-trip byte-idêntico para R4.ini e R4.hal.

Interno ao núcleo. O documento guarda o texto como lista de linhas (com os
terminadores originais) e só reescreve a linha efetivamente alterada — todo o
resto (comentários, espaçamento, tabs) é regravado byte a byte como foi lido.
"""

from __future__ import annotations

import re

from .erros import ConfigCorrompida

# linha de chave INI: prefixo até o '=', espaçamento, valor, espaçamento final
_RE_CHAVE = r"^(?P<pre>\s*{chave}\s*=)(?P<sp>[ \t]*)(?P<val>.*?)(?P<fim>\s*)$"


class Documento:
    """Um arquivo de texto editável linha a linha, com round-trip garantido."""

    def __init__(self, texto: str, nome: str) -> None:
        self.nome = nome
        self._linhas: list[str] = texto.splitlines(keepends=True)

    @property
    def texto(self) -> str:
        return "".join(self._linhas)

    # ------------------------------ INI ------------------------------

    def _indice_ini(self, secao: str, chave: str) -> int:
        """Índice da linha `chave = ...` dentro de `[secao]` (primeira ocorrência)."""
        re_secao = re.compile(r"^\s*\[" + re.escape(secao) + r"\]\s*$")
        re_chave = re.compile(
            r"^\s*" + re.escape(chave) + r"\s*=", flags=re.IGNORECASE
        )
        dentro = False
        for i, linha in enumerate(self._linhas):
            corpo = linha.rstrip("\r\n")
            if re.match(r"^\s*\[.*\]\s*$", corpo):
                dentro = bool(re_secao.match(corpo))
                continue
            if dentro and not corpo.lstrip().startswith("#") and re_chave.match(corpo):
                return i
        raise ConfigCorrompida(f"[{secao}] {chave}", self.nome)

    def ini_ler(self, secao: str, chave: str) -> str:
        """Valor cru (sem espaços das pontas) de `chave` em `[secao]`."""
        i = self._indice_ini(secao, chave)
        m = self._casar_chave(self._linhas[i], chave)
        return m.group("val")

    def ini_escrever(self, secao: str, chave: str, valor: str) -> None:
        """Troca só o valor, preservando prefixo/espaçamento/terminador da linha."""
        i = self._indice_ini(secao, chave)
        linha = self._linhas[i]
        m = self._casar_chave(linha, chave)
        fim_linha = linha[len(linha.rstrip("\r\n")):]  # "\n", "\r\n" ou ""
        self._linhas[i] = (
            f"{m.group('pre')}{m.group('sp')}{valor}{m.group('fim')}{fim_linha}"
        )

    def _casar_chave(self, linha: str, chave: str) -> re.Match[str]:
        corpo = linha.rstrip("\r\n")
        m = re.match(
            _RE_CHAVE.format(chave=re.escape(chave)), corpo, flags=re.IGNORECASE
        )
        if m is None:  # não deve acontecer: _indice_ini já validou
            raise ConfigCorrompida(chave, self.nome)
        return m

    # ------------------------------ HAL ------------------------------

    def hal_indice(self, padrao: str) -> int:
        """Índice da única linha (comentada ou não) cujo corpo casa `padrao`."""
        re_padrao = re.compile(padrao)
        achados = [
            i
            for i, linha in enumerate(self._linhas)
            if re_padrao.search(self._corpo_hal(linha))
        ]
        if len(achados) != 1:
            raise ConfigCorrompida(padrao, self.nome)
        return achados[0]

    @staticmethod
    def _corpo_hal(linha: str) -> str:
        """Conteúdo da linha ignorando um `#` inicial (linha desabilitada)."""
        corpo = linha.rstrip("\r\n")
        sem_espacos = corpo.lstrip()
        if sem_espacos.startswith("#"):
            return sem_espacos[1:]
        return corpo

    def hal_comentada(self, i: int) -> bool:
        return self._linhas[i].lstrip().startswith("#")

    def hal_comentar(self, i: int) -> None:
        if not self.hal_comentada(i):
            self._linhas[i] = "#" + self._linhas[i]

    def hal_descomentar(self, i: int) -> None:
        if self.hal_comentada(i):
            linha = self._linhas[i]
            pos = linha.index("#")
            self._linhas[i] = linha[:pos] + linha[pos + 1 :]

    def hal_token_pino(self, i: int) -> tuple[str, int, bool]:
        """(direcao, pino, invertido) do token R4.input/output.N[.not] da linha."""
        m = re.search(
            r"R4\.(?P<dir>input|output)\.(?P<n>\d+)(?P<not>\.not)?",
            self._corpo_hal(self._linhas[i]),
        )
        if m is None:
            raise ConfigCorrompida("R4.input/output", self.nome)
        return m.group("dir"), int(m.group("n")), m.group("not") is not None

    def hal_definir_pino(
        self, i: int, pino: int | None = None, invertido: bool | None = None
    ) -> None:
        """Reescreve o token R4.<dir>.N[.not] da linha; None mantém o valor atual."""
        direcao, pino_atual, invertido_atual = self.hal_token_pino(i)
        novo_pino = pino_atual if pino is None else pino
        novo_not = invertido_atual if invertido is None else invertido
        token = f"R4.{direcao}.{novo_pino}" + (".not" if novo_not else "")
        linha = self._linhas[i]
        self._linhas[i] = re.sub(
            r"R4\.(?:input|output)\.\d+(?:\.not)?", token, linha, count=1
        )
