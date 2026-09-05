"""ConfigR4 — editor in-place de uma config R4 instalada.

INVARIANTE round-trip: fora das linhas dos campos efetivamente alterados,
R4.ini e R4.hal são regravados byte-idênticos ao lido — comentários do
template e edições manuais preservados.

Ordem: abrir() → ler()/definir()* → aplicar()|salvar() → [cancelar()].
Edições ficam em memória até aplicar()/salvar(). Todo mutador devolve o
delta {id: valor_novo} — canal único de refresh da GUI.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from .campos import (
    ABAS,
    ARQUIVO_HAL,
    ARQUIVO_INI,
    CAMPOS,
    EIXO_A_HAL_PADROES,
    EIXO_A_INI,
    RECURSOS,
    AbaSpec,
    Campo,
    Tipo,
    Valor,
)
from .documento import Documento
from .erros import (
    ArquivoAlteradoExternamente,
    CampoDesconhecido,
    ConfigCorrompida,
    ConfigNaoEncontrada,
    ValorInvalido,
)

_ARQUIVOS = (ARQUIVO_INI, ARQUIVO_HAL)


def _numero(bruto: str, secao: str, chave: str) -> float:
    """float do valor INI, tolerando comentário inline manual
    ('815.0  # ajustei'). Irreconhecível → ConfigCorrompida (PT-BR),
    nunca ValueError cru."""
    try:
        return float(bruto)
    except ValueError:
        sem_comentario = re.split(r"[#;]", bruto, maxsplit=1)[0].strip()
        try:
            return float(sem_comentario)
        except ValueError:
            raise ConfigCorrompida(f"[{secao}] {chave}", ARQUIVO_INI) from None


def _fmt(valor: float | int) -> str:
    """Formata número para o arquivo: inteiro sem casa decimal, float curto."""
    if isinstance(valor, bool):  # nunca deve chegar aqui
        raise TypeError("bool não é gravável direto")
    if isinstance(valor, int) or float(valor).is_integer():
        return str(int(valor))
    return repr(round(float(valor), 10))


class ConfigR4:
    """Editor in-place de ``~/linuxcnc/configs/R4`` (ou pasta dada)."""

    def __init__(self, pasta: Path | None = None) -> None:
        self.pasta = Path(pasta) if pasta else Path.home() / "linuxcnc/configs/R4"
        for nome in _ARQUIVOS:
            if not (self.pasta / nome).is_file():
                raise ConfigNaoEncontrada(
                    f"Configuração R4 não encontrada: falta {self.pasta / nome}"
                )
        self._docs: dict[str, Documento] = {}
        self._codificacoes: dict[str, str] = {}
        self._hashes: dict[str, str] = {}
        self._pendentes: dict[str, Valor] = {}
        self._fixados: set[str] = set()          # sobrescritas de derivação na sessão
        self._backups: dict[str, Path] = {}      # do último aplicar()
        self._carregar()

    # ------------------------------ catálogo ------------------------------

    @staticmethod
    def campos() -> tuple[Campo, ...]:
        """Whitelist completa, estática (não exige config aberta)."""
        return tuple(CAMPOS.values())

    @staticmethod
    def abas() -> tuple[AbaSpec, ...]:
        """Abas em ordem de exibição."""
        return tuple(sorted(ABAS, key=lambda a: a.ordem))

    @classmethod
    def abrir(cls, pasta: Path | None = None) -> "ConfigR4":
        return cls(pasta)

    # ------------------------------ leitura ------------------------------

    @property
    def alterado(self) -> bool:
        """True se há edições pendentes não gravadas."""
        return bool(self._pendentes)

    def ler(self) -> dict[str, Valor]:
        """Estado efetivo de TODOS os campos (arquivo + edições pendentes)."""
        return {cid: self._efetivo(cid) for cid in CAMPOS}

    # ------------------------------ escrita ------------------------------

    def definir(self, campo: str, valor: Valor) -> dict[str, Valor]:
        """Edita UM campo em memória e dispara as derivações. Atômico: em erro,
        nada muda. Retorna o delta {id: valor_novo} de tudo que mudou."""
        spec = self._spec(campo)
        valor = self._validar(spec, valor)
        antes = self.ler()

        novos = dict(self._pendentes)
        novos[campo] = valor
        novos_fixados = set(self._fixados) | {campo}
        self._derivar(spec, valor, novos, novos_fixados)

        # commit em memória
        self._pendentes = novos

        depois = self.ler()
        delta = {cid: v for cid, v in depois.items() if antes[cid] != v}
        # só fixa a sobrescrita de derivação se a edição mudou algo de fato
        # (GUI reemitindo o valor atual não pode congelar a regra do Z)
        if campo in delta:
            self._fixados = novos_fixados
        # pendências iguais ao disco (e com alvos espelhados em sincronia)
        # saem do staging — inclui reverter um campo ao valor original
        for cid in list(self._pendentes):
            if (
                self._pendentes[cid] == self._efetivo_no_disco(cid)
                and self._alvos_sincronizados(cid)
            ):
                del self._pendentes[cid]
        return delta

    # ------------------------- aplicar / salvar --------------------------

    def aplicar(self, apenas_aba: str | None = None) -> tuple[Path, ...]:
        """Backup datado de cada arquivo que será tocado, depois grava.
        Após aplicar(), cancelar() restaura os backups. Retorna os gravados."""
        return self._gravar(apenas_aba, com_backup=True)

    def salvar(self, apenas_aba: str | None = None) -> tuple[Path, ...]:
        """Grava direto, SEM backup (mesmo invariante round-trip)."""
        return self._gravar(apenas_aba, com_backup=False)

    def cancelar(self) -> dict[str, Valor]:
        """Descarta edições pendentes; se aplicar() foi a última gravação,
        restaura os backups dela (salvar() posterior invalida os backups).
        Erro: ArquivoAlteradoExternamente se o arquivo mudou fora do app
        depois do aplicar() — nada é restaurado. Retorna o delta."""
        antes = self.ler()
        for nome in self._backups:
            atual = hashlib.sha256((self.pasta / nome).read_bytes()).hexdigest()
            if atual != self._hashes[nome]:
                raise ArquivoAlteradoExternamente(nome)
        for nome, backup in self._backups.items():
            shutil.copy2(backup, self.pasta / nome)
        self._backups = {}
        self._pendentes = {}
        self._fixados = set()
        self._carregar()
        depois = self.ler()
        return {cid: v for cid, v in depois.items() if antes[cid] != v}

    def recarregar(self) -> dict[str, Valor]:
        """Relê os arquivos do disco, descartando edições pendentes e os
        backups de um aplicar() anterior (o estado externo passa a valer)."""
        antes = self.ler()
        self._pendentes = {}
        self._fixados = set()
        self._backups = {}
        self._carregar()
        depois = self.ler()
        return {cid: v for cid, v in depois.items() if antes[cid] != v}

    # =========================== implementação ===========================

    def _carregar(self) -> None:
        for nome in _ARQUIVOS:
            dados = (self.pasta / nome).read_bytes()
            try:
                texto, codificacao = dados.decode("utf-8"), "utf-8"
            except UnicodeDecodeError:
                # arquivo regravado por editor legado (ex. ISO-8859-1);
                # latin-1 decodifica qualquer byte e regrava idêntico
                texto, codificacao = dados.decode("latin-1"), "latin-1"
            self._docs[nome] = Documento(texto, nome)
            self._codificacoes[nome] = codificacao
            self._hashes[nome] = hashlib.sha256(dados).hexdigest()

    @staticmethod
    def _spec(campo: str) -> Campo:
        try:
            return CAMPOS[campo]
        except KeyError:
            raise CampoDesconhecido(campo) from None

    # ---- validação ----

    @staticmethod
    def _validar(spec: Campo, valor: Valor) -> Valor:
        if spec.tipo is Tipo.BOOL:
            if not isinstance(valor, bool):
                raise ValorInvalido(spec.id, "esperado verdadeiro/falso")
            return valor
        if spec.tipo is Tipo.TEXTO:
            if not isinstance(valor, str):
                raise ValorInvalido(spec.id, "esperado texto")
            return valor
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ValorInvalido(spec.id, "esperado número")
        if not math.isfinite(float(valor)):
            raise ValorInvalido(spec.id, "número inválido")
        if spec.tipo in (Tipo.INTEIRO, Tipo.PINO_ENTRADA, Tipo.PINO_SAIDA):
            if float(valor) != int(valor):
                raise ValorInvalido(spec.id, "esperado número inteiro")
            valor = int(valor)
        if spec.id.endswith(".proc_sonda"):
            valor = -abs(float(valor))  # PROC_SONDA sempre desce
        if spec.papel == "abs" and float(valor) <= 0:
            raise ValorInvalido(spec.id, "SCALE deve ser maior que zero")
        if spec.minimo is not None and float(valor) < spec.minimo:
            raise ValorInvalido(spec.id, f"mínimo permitido é {spec.minimo:g}")
        if spec.maximo is not None and float(valor) > spec.maximo:
            raise ValorInvalido(spec.id, f"máximo permitido é {spec.maximo:g}")
        return valor

    # ---- derivações ----

    def _derivar(
        self,
        spec: Campo,
        valor: Valor,
        novos: dict[str, Valor],
        fixados: set[str],
    ) -> None:
        """Regras que disparam ao editar um campo (fan-out em `novos`)."""
        if spec.papel in ("sinal", "abs"):
            eixo = spec.aba
            escala = self._efetivo_com(f"{eixo}.scale", novos)
            novos[f"{eixo}.deadband"] = round(1 / abs(float(escala)) * 0.75, 10)
            if eixo == "eixo_z" and spec.papel == "sinal":
                # sinal do HOME_SEARCH_VEL do Z oposto ao SCALE do Z (sobrescrevível)
                if "eixo_z.home_search_vel" not in fixados:
                    invertido = self._efetivo_com("eixo_z.sentido_invertido", novos)
                    hsv = float(self._efetivo_com("eixo_z.home_search_vel", novos))
                    alvo = abs(hsv) if invertido else -abs(hsv)
                    novos["eixo_z.home_search_vel"] = alvo
                    self._acompanhar_latch(alvo, novos, fixados)
        if spec.id == "eixo_z.home_search_vel":
            # HOME_LATCH_VEL acompanha o sentido do home; HOME_FINAL_VEL não
            self._acompanhar_latch(float(valor), novos, fixados)

    def _acompanhar_latch(
        self, hsv: float, novos: dict[str, Valor], fixados: set[str]
    ) -> None:
        if "eixo_z.home_latch_vel" in fixados or hsv == 0:
            return
        latch = float(self._efetivo_com("eixo_z.home_latch_vel", novos))
        novos["eixo_z.home_latch_vel"] = math.copysign(abs(latch), hsv)

    # ---- valores efetivos ----

    def _efetivo(self, cid: str) -> Valor:
        if cid in self._pendentes:
            return self._pendentes[cid]
        return self._efetivo_no_disco(cid)

    def _efetivo_com(self, cid: str, novos: dict[str, Valor]) -> Valor:
        if cid in novos:
            return novos[cid]
        return self._efetivo_no_disco(cid)

    def _alvos_sincronizados(self, cid: str) -> bool:
        """True se todas as escritas espelhadas do campo têm o mesmo valor no
        disco. O template real pode vir dessincronizado (ex.: [DISPLAY] vs
        [TRAJ]); nesse caso definir o valor exibido NÃO é no-op — a gravação
        precisa acontecer para sincronizar os espelhos."""
        spec = CAMPOS[cid]
        if spec.papel == "eixo_a":
            # sincronizado se o HAL acompanha o estado do INI (JOINTS)
            hal = self._docs[ARQUIVO_HAL]
            habilitado = bool(self._efetivo_no_disco(cid))
            return all(
                hal.hal_comentada(hal.hal_indice(p)) == (not habilitado)
                for p in EIXO_A_HAL_PADROES
            )
        if spec.recurso is not None:
            hal = self._docs[ARQUIVO_HAL]
            rec = RECURSOS[spec.recurso]
            indices = [hal.hal_indice(p) for p in rec.padroes]
            if spec.papel == "habilitado":
                estados = {hal.hal_comentada(i) for i in indices}
            elif spec.papel == "pino":
                estados = {hal.hal_token_pino(i)[1] for i in indices}
            elif spec.papel == "polaridade_par":
                # as duas linhas têm de estar em polaridades opostas
                nots = [hal.hal_token_pino(i)[2] for i in indices]
                return nots[0] is not nots[1]
            else:
                return True  # invertido: só a primeira linha define
            return len(estados) == 1
        if len(spec.alvos) <= 1:
            return True
        ini = self._docs[ARQUIVO_INI]
        valores = {
            _numero(ini.ini_ler(alvo.secao, alvo.chave), alvo.secao, alvo.chave)
            for alvo in spec.alvos
        }
        return len(valores) == 1

    def _efetivo_no_disco(self, cid: str) -> Valor:
        spec = CAMPOS[cid]
        if spec.recurso is not None:
            return self._ler_hal(spec)
        if spec.papel == "eixo_a":
            joints = self._docs[ARQUIVO_INI].ini_ler("KINS", "JOINTS")
            return int(_numero(joints, "KINS", "JOINTS")) == 4
        ini = self._docs[ARQUIVO_INI]
        alvo = spec.alvos[0]
        bruto = ini.ini_ler(alvo.secao, alvo.chave)
        if spec.tipo is Tipo.TEXTO:
            return bruto
        numero = _numero(bruto, alvo.secao, alvo.chave)
        if spec.papel == "sinal":
            return numero < 0
        if spec.papel == "abs":
            return abs(numero)
        if spec.tipo is Tipo.INTEIRO:
            return int(numero)
        return numero

    def _ler_hal(self, spec: Campo) -> Valor:
        hal = self._docs[ARQUIVO_HAL]
        rec = RECURSOS[spec.recurso]
        indices = [hal.hal_indice(p) for p in rec.padroes]
        if spec.papel == "habilitado":
            return not all(hal.hal_comentada(i) for i in indices)
        _, pino, invertido = hal.hal_token_pino(indices[0])
        if spec.papel == "pino":
            return pino
        # "invertido" e "polaridade_par" leem a mesma coisa: o .not da 1ª linha
        # (para o par home/limite, a 1ª linha é a do home).
        return invertido

    # ---- gravação ----

    def _gravar(self, apenas_aba: str | None, com_backup: bool) -> tuple[Path, ...]:
        if apenas_aba is not None and apenas_aba not in {a.id for a in ABAS}:
            raise ValorInvalido("apenas_aba", f"aba desconhecida: {apenas_aba}")
        ids = [
            cid
            for cid in self._pendentes
            if apenas_aba is None or CAMPOS[cid].aba == apenas_aba
        ]
        if not ids:
            return ()

        # detectar modificação externa antes de qualquer escrita
        for nome in _ARQUIVOS:
            atual = hashlib.sha256((self.pasta / nome).read_bytes()).hexdigest()
            if atual != self._hashes[nome]:
                raise ArquivoAlteradoExternamente(nome)

        # aplica as edições em cópias dos documentos
        docs = {
            nome: Documento(doc.texto, nome) for nome, doc in self._docs.items()
        }
        tocados: set[str] = set()
        for cid in ids:
            tocados |= self._materializar(docs, cid)

        # backup prévio (Aplicar) dos arquivos que serão tocados;
        # Salvar é definitivo: invalida os backups de um aplicar() anterior
        if com_backup:
            carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
            backups: dict[str, Path] = {}
            for nome in sorted(tocados):
                destino = self.pasta / f"{nome}.bak-{carimbo}"
                shutil.copy2(self.pasta / nome, destino)
                backups[nome] = destino
            self._backups = backups
        else:
            self._backups = {}

        # gravação atômica em duas fases: prepara TODOS os temporários e só
        # então faz os os.replace — um campo pode tocar INI e HAL juntos
        # (toggle do eixo A) e falha no meio deixaria cinemática contraditória.
        # Se um replace falhar depois do primeiro, restaura os já trocados.
        temporarios: dict[str, str] = {}
        originais: dict[str, bytes] = {}
        dados_por_nome: dict[str, bytes] = {}
        try:
            for nome in sorted(tocados):
                dados = docs[nome].texto.encode(self._codificacoes[nome])
                dados_por_nome[nome] = dados
                originais[nome] = (self.pasta / nome).read_bytes()
                fd, tmp = tempfile.mkstemp(dir=self.pasta, prefix=f".{nome}.")
                with os.fdopen(fd, "wb") as f:
                    f.write(dados)
                temporarios[nome] = tmp
        except OSError:
            for tmp in temporarios.values():
                if os.path.exists(tmp):
                    os.unlink(tmp)
            raise

        gravados: list[Path] = []
        trocados: list[str] = []
        try:
            for nome, tmp in temporarios.items():
                os.replace(tmp, self.pasta / nome)
                trocados.append(nome)
        except OSError:
            for nome in trocados:  # melhor esforço: volta o conjunto antigo
                (self.pasta / nome).write_bytes(originais[nome])
            for nome, tmp in temporarios.items():
                if nome not in trocados and os.path.exists(tmp):
                    os.unlink(tmp)
            raise
        for nome in trocados:
            self._docs[nome] = docs[nome]
            self._hashes[nome] = hashlib.sha256(dados_por_nome[nome]).hexdigest()
            gravados.append(self.pasta / nome)

        for cid in ids:
            del self._pendentes[cid]
        return tuple(gravados)

    def _materializar(self, docs: dict[str, Documento], cid: str) -> set[str]:
        """Escreve o valor efetivo de `cid` nos documentos. Retorna arquivos tocados."""
        spec = CAMPOS[cid]
        valor = self._efetivo(cid)
        if spec.papel == "eixo_a":
            habilitado = bool(valor)
            ini = docs[ARQUIVO_INI]
            for secao, chave, com_a, sem_a in EIXO_A_INI:
                ini.ini_escrever(secao, chave, com_a if habilitado else sem_a)
            hal = docs[ARQUIVO_HAL]
            for padrao in EIXO_A_HAL_PADROES:
                i = hal.hal_indice(padrao)
                if habilitado:
                    hal.hal_descomentar(i)
                else:
                    hal.hal_comentar(i)
            return {ARQUIVO_INI, ARQUIVO_HAL}
        if spec.recurso is not None:
            self._materializar_hal(docs[ARQUIVO_HAL], spec, valor)
            return {ARQUIVO_HAL}
        ini = docs[ARQUIVO_INI]
        if spec.papel in ("sinal", "abs"):
            eixo = spec.aba
            invertido = self._efetivo(f"{eixo}.sentido_invertido")
            valor_abs = float(self._efetivo(f"{eixo}.scale"))
            assinado = -valor_abs if invertido else valor_abs
            texto = _fmt(assinado)
        elif spec.tipo is Tipo.TEXTO:
            texto = str(valor)
        else:
            texto = _fmt(valor)  # type: ignore[arg-type]
        for alvo in spec.alvos:
            ini.ini_escrever(alvo.secao, alvo.chave, texto)
        return {ARQUIVO_INI}

    @staticmethod
    def _materializar_hal(hal: Documento, spec: Campo, valor: Valor) -> None:
        rec = RECURSOS[spec.recurso]
        indices = [hal.hal_indice(p) for p in rec.padroes]
        if spec.papel == "habilitado":
            for i in indices:
                if valor:
                    hal.hal_descomentar(i)
                else:
                    hal.hal_comentar(i)
        elif spec.papel == "pino":
            for i in indices:
                hal.hal_definir_pino(i, pino=int(valor))
        elif spec.papel == "polaridade_par":
            # o .not troca de lado entre as duas linhas, nunca some nem duplica
            hal.hal_definir_pino(indices[0], invertido=bool(valor))
            hal.hal_definir_pino(indices[1], invertido=not bool(valor))
        else:  # invertido — só a primeira linha define a polaridade do recurso
            hal.hal_definir_pino(indices[0], invertido=bool(valor))
