"""Configurador GTK3 (F4) — segunda cara do app: edita uma config R4 existente.

Casca fina sobre `configurador_logica.py` e `core.ConfigR4`: as abas são
geradas do catálogo (`ConfigR4.abas()`/`campos()`), básicas em evidência e
avançadas num expander, estilo ports-and-pins do Mach3. Aplicar/Salvar agem
na aba atual (aplicar faz backup; Cancelar restaura); Reiniciar LinuxCNC
avisa antes de fechar uma instância aberta. Toda edição passa pelo editor
in-place da F1 — comentários e edições manuais preservados.
Proibido rodar como root (tech-stack §Privilégios).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..core import ConfigNaoEncontrada, ConfigR4, ErroConfigR4  # noqa: E402
from ..core.campos import Campo, Tipo  # noqa: E402
from .. import sistema  # noqa: E402
from . import configurador_logica as logica  # noqa: E402

_MARGEM = 18


class JanelaConfigurador(Gtk.Window):
    """Notebook com uma aba por AbaSpec; widgets gerados do catálogo."""

    def __init__(
        self,
        cfg: ConfigR4,
        executar: sistema.ExecutarSistema | None = None,
    ) -> None:
        super().__init__(title="Configurador StepDir R4")
        self.set_default_size(760, 560)
        self._cfg = cfg
        self._executar = executar or sistema.executar_real
        self._widgets: dict[str, Gtk.Widget] = {}
        self._campos_por_widget: dict[Gtk.Widget, Campo] = {}
        self._sincronizando = False

        raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add(raiz)

        self._notebook = Gtk.Notebook()
        self._notebook.set_scrollable(True)
        raiz.pack_start(self._notebook, True, True, 0)
        for aba in ConfigR4.abas():
            pagina = self._montar_aba(aba.id)
            self._notebook.append_page(pagina, Gtk.Label(label=aba.rotulo))

        raiz.pack_start(self._montar_barra(), False, False, 0)
        self._refresh(self._cfg.ler())
        self._atualizar_status()
        self.connect("destroy", Gtk.main_quit)

    # ------------------------------ montagem ------------------------------

    def _montar_aba(self, aba_id: str) -> Gtk.Widget:
        basicos, avancados = logica.campos_da_aba(aba_id)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        caixa.set_margin_top(_MARGEM)
        caixa.set_margin_bottom(_MARGEM)
        caixa.set_margin_start(_MARGEM)
        caixa.set_margin_end(_MARGEM)
        if basicos:
            caixa.pack_start(self._grade(basicos), False, False, 0)
        if avancados:
            expander = Gtk.Expander(label="Avançado")
            expander.add(self._grade(avancados))
            caixa.pack_start(expander, False, False, 0)
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rolagem.add(caixa)
        return rolagem

    def _grade(self, campos: list[Campo]) -> Gtk.Grid:
        grade = Gtk.Grid(column_spacing=12, row_spacing=6)
        for linha, campo in enumerate(campos):
            widget = self._criar_widget(campo)
            self._widgets[campo.id] = widget
            self._campos_por_widget[widget] = campo
            if campo.descricao:
                widget.set_tooltip_text(campo.descricao)
            if campo.tipo is Tipo.BOOL:
                grade.attach(widget, 0, linha, 2, 1)
            else:
                rotulo = Gtk.Label(label=logica.rotulo_widget(campo))
                rotulo.set_xalign(0)
                if campo.descricao:
                    rotulo.set_tooltip_text(campo.descricao)
                grade.attach(rotulo, 0, linha, 1, 1)
                grade.attach(widget, 1, linha, 1, 1)
        return grade

    def _criar_widget(self, campo: Campo) -> Gtk.Widget:
        if campo.tipo is Tipo.BOOL:
            check = Gtk.CheckButton(label=campo.rotulo)
            check.connect("toggled", self._ao_mudar_bool)
            return check
        if campo.tipo is Tipo.TEXTO:
            entrada = Gtk.Entry()
            entrada.set_hexpand(True)
            entrada.connect("changed", self._ao_mudar_texto)
            return entrada
        minimo, maximo, passo, digitos = logica.faixa(campo)
        ajuste = Gtk.Adjustment(
            value=0, lower=minimo, upper=maximo,
            step_increment=passo, page_increment=passo * 10,
        )
        spin = Gtk.SpinButton(adjustment=ajuste, digits=digitos, numeric=True)
        spin.set_width_chars(12)
        spin.connect("value-changed", self._ao_mudar_numero)
        return spin

    def _montar_barra(self) -> Gtk.Widget:
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.set_margin_top(6)
        barra.set_margin_bottom(6)
        barra.set_margin_start(_MARGEM)
        barra.set_margin_end(_MARGEM)

        self._rotulo_status = Gtk.Label(label="")
        self._rotulo_status.set_xalign(0)
        barra.pack_start(self._rotulo_status, True, True, 0)

        botao_cancelar = Gtk.Button(label="Cancelar")
        botao_cancelar.set_tooltip_text(
            "Descarta edições pendentes; se a última gravação foi um "
            "Aplicar, restaura o backup dela."
        )
        botao_cancelar.connect("clicked", self._ao_cancelar)
        barra.pack_start(botao_cancelar, False, False, 0)

        botao_aplicar = Gtk.Button(label="Aplicar (aba atual)")
        botao_aplicar.set_tooltip_text(
            "Grava as mudanças da aba atual com backup prévio."
        )
        botao_aplicar.connect("clicked", self._ao_gravar, True)
        barra.pack_start(botao_aplicar, False, False, 0)

        botao_salvar = Gtk.Button(label="Salvar (aba atual)")
        botao_salvar.set_tooltip_text("Grava direto, sem backup.")
        botao_salvar.connect("clicked", self._ao_gravar, False)
        barra.pack_start(botao_salvar, False, False, 0)

        botao_reiniciar = Gtk.Button(label="Reiniciar LinuxCNC")
        botao_reiniciar.connect("clicked", self._ao_reiniciar)
        barra.pack_start(botao_reiniciar, False, False, 0)
        return barra

    # ------------------------------ edição --------------------------------

    def _ao_mudar_bool(self, check: Gtk.CheckButton) -> None:
        self._definir(check, check.get_active())

    def _ao_mudar_texto(self, entrada: Gtk.Entry) -> None:
        self._definir(entrada, entrada.get_text())

    def _ao_mudar_numero(self, spin: Gtk.SpinButton) -> None:
        self._definir(spin, spin.get_value())

    def _definir(self, widget: Gtk.Widget, valor) -> None:
        if self._sincronizando:
            return
        campo = self._campos_por_widget[widget]
        try:
            delta = self._cfg.definir(campo.id, valor)
        except ErroConfigR4 as e:
            self._refresh({campo.id: self._cfg.ler()[campo.id]})
            self._alerta(str(e))
            return
        self._refresh(delta)
        self._atualizar_status()

    def _refresh(self, valores: dict) -> None:
        """Atualiza widgets a partir de um delta, sem reemitir sinais."""
        self._sincronizando = True
        try:
            for cid, valor in valores.items():
                widget = self._widgets.get(cid)
                if widget is None:
                    continue
                if isinstance(widget, Gtk.CheckButton):
                    widget.set_active(bool(valor))
                elif isinstance(widget, Gtk.Entry) and not isinstance(
                    widget, Gtk.SpinButton
                ):
                    widget.set_text(str(valor))
                else:
                    widget.set_value(float(valor))
        finally:
            self._sincronizando = False
        self._atualizar_sensibilidade()

    def _atualizar_sensibilidade(self) -> None:
        atuais = self._cfg.ler()
        for widget in self._widgets.values():
            campo = self._campos_por_widget[widget]
            widget.set_sensitive(logica.sensivel(campo, atuais))

    def _atualizar_status(self, extra: str | None = None) -> None:
        texto = logica.texto_pendencias(self._cfg.alterado)
        if extra:
            texto = f"{extra}  —  {texto}"
        self._rotulo_status.set_text(texto)

    # ------------------------------ botões --------------------------------

    def _aba_atual_id(self) -> str:
        return ConfigR4.abas()[self._notebook.get_current_page()].id

    def _ao_gravar(self, _botao: Gtk.Button, com_backup: bool) -> None:
        try:
            if com_backup:
                arquivos = self._cfg.aplicar(self._aba_atual_id())
            else:
                arquivos = self._cfg.salvar(self._aba_atual_id())
        except ErroConfigR4 as e:
            self._alerta(str(e))
            return
        self._atualizar_status(logica.texto_gravado(arquivos, com_backup))

    def _ao_cancelar(self, _botao: Gtk.Button) -> None:
        try:
            delta = self._cfg.cancelar()
        except ErroConfigR4 as e:
            self._alerta(str(e))
            return
        self._refresh(delta)
        self._atualizar_status("Edições descartadas.")

    def _ao_reiniciar(self, _botao: Gtk.Button) -> None:
        dialogo = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text=logica.TEXTO_AVISO_REINICIAR,
        )
        resposta = dialogo.run()
        dialogo.destroy()
        if resposta != Gtk.ResponseType.OK:
            return
        if sistema.linuxcnc_rodando(self._executar):
            sistema.parar_linuxcnc(self._executar)
            # o unload do HAL/RTAPI leva segundos; reabrir antes mata a
            # instância nova com "RTAPI already in use"
            if not sistema.aguardar_linuxcnc_parar(self._executar):
                self._alerta(logica.TEXTO_NAO_FECHOU)
                return
        if sistema.abrir_linuxcnc(self._cfg.pasta):
            self._atualizar_status(
                "LinuxCNC abrindo com a nova configuração…"
            )
        else:
            self._alerta(logica.TEXTO_SEM_LINUXCNC)

    def _alerta(self, texto: str) -> None:
        dialogo = Gtk.MessageDialog(
            transient_for=self,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=texto,
        )
        dialogo.run()
        dialogo.destroy()


def main(pasta: str | None = None) -> int:
    if os.geteuid() == 0:
        print(
            "Erro: não execute o configurador como root. Rode como usuário "
            "normal.",
            file=sys.stderr,
        )
        return 1
    try:
        # JanelaConfigurador lê a config na montagem — ConfigCorrompida
        # (âncora destruída por edição manual) sobe de ler(), não de abrir()
        cfg = ConfigR4.abrir(Path(pasta) if pasta else None)
        janela = JanelaConfigurador(cfg)
    except ConfigNaoEncontrada as e:
        print(
            f"Erro: {e}\n"
            "Instale a configuração primeiro (assistente 'StepDir R4 — "
            "Instalação' ou `stepdir-r4 instalar`).",
            file=sys.stderr,
        )
        return 1
    except ErroConfigR4 as e:
        print(f"Erro: {e}", file=sys.stderr)
        return 1
    janela.show_all()
    Gtk.main()
    return 0
