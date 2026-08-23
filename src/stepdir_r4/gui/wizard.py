"""Wizard GTK3 de instalação (F2).

Casca fina sobre `instalacao.py` + `core.instalar_config()`:
boas-vindas → modelo → dimensões da mesa → resumo → resultado.
Proibido rodar como root (tech-stack §Privilégios).
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..core import ErroConfigR4, instalar_config  # noqa: E402
from . import instalacao  # noqa: E402

_MARGEM = 18


def _pagina(titulo: str) -> Gtk.Box:
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    caixa.set_margin_top(_MARGEM)
    caixa.set_margin_bottom(_MARGEM)
    caixa.set_margin_start(_MARGEM)
    caixa.set_margin_end(_MARGEM)
    rotulo = Gtk.Label()
    rotulo.set_markup(f"<b><big>{titulo}</big></b>")
    rotulo.set_xalign(0)
    caixa.pack_start(rotulo, False, False, 0)
    return caixa


def _texto(conteudo: str) -> Gtk.Label:
    rotulo = Gtk.Label(label=conteudo)
    rotulo.set_xalign(0)
    rotulo.set_line_wrap(True)
    return rotulo


def _spin_mesa(valor: float) -> Gtk.SpinButton:
    ajuste = Gtk.Adjustment(
        value=valor, lower=1, upper=10000, step_increment=10, page_increment=100
    )
    spin = Gtk.SpinButton(adjustment=ajuste, digits=0, numeric=True)
    spin.set_hexpand(False)
    return spin


class WizardInstalacao(Gtk.Assistant):
    """Assistente de instalação da configuração R4 (usa o núcleo da F1)."""

    def __init__(self) -> None:
        super().__init__(title="Instalador StepDir R4")
        self.set_default_size(640, 480)

        self._resultado_texto: str | None = None
        self._sucesso = False

        self._montar_boas_vindas()
        self._montar_modelo()
        self._montar_dimensoes()
        self._montar_resumo()
        self._montar_final()

        self.connect("prepare", self._ao_preparar)
        self.connect("apply", self._ao_aplicar)
        self.connect("cancel", self._sair)
        self.connect("close", self._sair)

    # ---- páginas -------------------------------------------------------

    def _montar_boas_vindas(self) -> None:
        caixa = _pagina("Bem-vindo ao instalador da StepDir R4")
        caixa.pack_start(
            _texto(
                "Este assistente cria a configuração do LinuxCNC para a sua "
                "CNC com a placa StepDir R4.\n\n"
                "Você escolhe o modelo da máquina e as dimensões da mesa; o "
                "restante vem da configuração pronta do fabricante — nada é "
                "gerado do zero.\n\n"
                "A pasta criada é ~/linuxcnc/configs/R4. Se ela já existir, "
                "a versão atual é preservada em um backup datado."
            ),
            False,
            False,
            0,
        )
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.INTRO)
        self.set_page_title(caixa, "Boas-vindas")
        self.set_page_complete(caixa, True)

    def _montar_modelo(self) -> None:
        caixa = _pagina("Modelo da CNC")
        caixa.pack_start(
            _texto("Escolha o modelo da sua máquina:"), False, False, 0
        )
        self._combo_modelo = Gtk.ComboBoxText()
        for ident, rotulo in instalacao.MODELOS:
            self._combo_modelo.append(ident, rotulo)
        self._combo_modelo.set_active(0)
        self._combo_modelo.connect("changed", self._ao_trocar_modelo)
        caixa.pack_start(self._combo_modelo, False, False, 0)
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONTENT)
        self.set_page_title(caixa, "Modelo")
        self.set_page_complete(caixa, True)

    def _montar_dimensoes(self) -> None:
        caixa = _pagina("Dimensões da mesa")
        caixa.pack_start(
            _texto(
                "Informe o tamanho útil da mesa em milímetros. O curso "
                "máximo de cada eixo é a dimensão da mesa mais uma folga "
                "de 15 mm."
            ),
            False,
            False,
            0,
        )

        mesa_x, mesa_y = instalacao.MESA_PADRAO["spark_v2"]
        grade = Gtk.Grid(column_spacing=12, row_spacing=8)
        self._spin_x = _spin_mesa(mesa_x)
        self._spin_y = _spin_mesa(mesa_y)
        for linha, (nome, spin) in enumerate(
            (("Mesa X (mm):", self._spin_x), ("Mesa Y (mm):", self._spin_y))
        ):
            rotulo = Gtk.Label(label=nome)
            rotulo.set_xalign(0)
            grade.attach(rotulo, 0, linha, 1, 1)
            grade.attach(spin, 1, linha, 1, 1)
            spin.connect("value-changed", self._ao_mudar_mesa)
        caixa.pack_start(grade, False, False, 0)

        self._rotulo_curso = _texto("")
        caixa.pack_start(self._rotulo_curso, False, False, 0)

        self._check_launcher = Gtk.CheckButton(
            label="Criar atalho “launch R4” na Área de Trabalho"
        )
        self._check_launcher.set_active(True)
        caixa.pack_start(self._check_launcher, False, False, 0)

        self._ao_mudar_mesa(None)
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONTENT)
        self.set_page_title(caixa, "Dimensões")
        self.set_page_complete(caixa, True)

    def _montar_resumo(self) -> None:
        caixa = _pagina("Confirme antes de instalar")
        self._rotulo_resumo = _texto("")
        caixa.pack_start(self._rotulo_resumo, False, False, 0)
        self._pagina_resumo = caixa
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONFIRM)
        self.set_page_title(caixa, "Resumo")
        self.set_page_complete(caixa, True)

    def _montar_final(self) -> None:
        caixa = _pagina("Resultado")
        self._rotulo_final = _texto("")
        self._rotulo_final.set_selectable(True)
        caixa.pack_start(self._rotulo_final, False, False, 0)
        self._pagina_final = caixa
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.SUMMARY)
        self.set_page_title(caixa, "Conclusão")
        self.set_page_complete(caixa, True)

    # ---- estado --------------------------------------------------------

    def _parametros(self) -> instalacao.ParametrosWizard:
        return instalacao.ParametrosWizard(
            modelo=self._combo_modelo.get_active_id() or "spark_v2",
            mesa_x=self._spin_x.get_value(),
            mesa_y=self._spin_y.get_value(),
            criar_launcher=self._check_launcher.get_active(),
        )

    # ---- sinais --------------------------------------------------------

    def _ao_trocar_modelo(self, _combo: Gtk.ComboBoxText) -> None:
        padrao = instalacao.MESA_PADRAO.get(
            self._combo_modelo.get_active_id() or ""
        )
        if padrao:
            self._spin_x.set_value(padrao[0])
            self._spin_y.set_value(padrao[1])

    def _ao_mudar_mesa(self, _spin: Gtk.SpinButton | None) -> None:
        self._rotulo_curso.set_text(
            instalacao.texto_curso(
                self._spin_x.get_value(), self._spin_y.get_value()
            )
        )

    def _ao_preparar(self, _assistente: Gtk.Assistant, pagina: Gtk.Widget) -> None:
        if pagina is self._pagina_resumo:
            self._rotulo_resumo.set_text(
                instalacao.texto_resumo(self._parametros())
            )
        elif pagina is self._pagina_final and self._resultado_texto is not None:
            self._rotulo_final.set_text(self._resultado_texto)

    def _ao_aplicar(self, _assistente: Gtk.Assistant) -> None:
        params = self._parametros()
        try:
            resultado = instalar_config(
                mesa_x=params.mesa_x,
                mesa_y=params.mesa_y,
                criar_launcher=params.criar_launcher,
            )
        except (ErroConfigR4, OSError) as erro:
            self._sucesso = False
            self._resultado_texto = instalacao.texto_erro(erro)
        else:
            self._sucesso = True
            self._resultado_texto = instalacao.texto_resultado(resultado)

    def _sair(self, _assistente: Gtk.Assistant) -> None:
        Gtk.main_quit()


def main() -> int:
    if os.geteuid() == 0:
        print(
            "Erro: não execute o instalador como root. Rode como usuário "
            "normal; o sistema pedirá a senha quando for necessário.",
            file=sys.stderr,
        )
        return 1
    wizard = WizardInstalacao()
    wizard.show_all()
    Gtk.main()
    return 0 if wizard._sucesso or wizard._resultado_texto is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
