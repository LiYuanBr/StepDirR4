"""Wizard GTK3 de instalação (F2 + páginas de sistema da F3).

Casca fina sobre `instalacao.py`, `core.instalar_config()` e
`stepdir_r4.sistema`. Ordem (roadmap §F3): boas-vindas → pré-checagens →
rede → drivers → modelo → dimensões da mesa → resumo → resultado com
verificação (ping na placa + hash dos drivers). As páginas de sistema
podem ser puladas (máquina sem placa conectada ainda gera a config).
Proibido rodar como root (tech-stack §Privilégios).
"""

from __future__ import annotations

import os
import sys

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

from ..core import ErroConfigR4, instalar_config  # noqa: E402
from .. import sistema  # noqa: E402
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
    """Assistente de instalação completa (config + rede + drivers)."""

    def __init__(self, executar: sistema.ExecutarSistema | None = None) -> None:
        super().__init__(title="Instalador StepDir R4")
        self.set_default_size(680, 520)

        self._executar = executar or sistema.executar_real
        self._resultado_texto: str | None = None
        self._sucesso = False
        self._checagens_ok = False
        self._rede_feita = False
        self._drivers_feitos = False

        self._montar_boas_vindas()
        self._montar_checagens()
        self._montar_rede()
        self._montar_drivers()
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
                "Este assistente prepara o computador para a placa StepDir "
                "R4: verifica o sistema, configura a rede dedicada da placa, "
                "instala os drivers e cria a configuração do LinuxCNC.\n\n"
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

    def _montar_checagens(self) -> None:
        caixa = _pagina("Verificação do sistema")
        self._rotulo_checagens = _texto("Verificando…")
        caixa.pack_start(self._rotulo_checagens, False, False, 0)
        self._tutorial_linuxcnc = Gtk.Expander(
            label="Como instalar o LinuxCNC (passo a passo)"
        )
        self._tutorial_linuxcnc.add(_texto(sistema.TUTORIAL_LINUXCNC))
        self._tutorial_linuxcnc.set_no_show_all(True)
        caixa.pack_start(self._tutorial_linuxcnc, False, False, 0)
        self._check_ignorar = Gtk.CheckButton(
            label="Continuar mesmo com pendências (não recomendado)"
        )
        self._check_ignorar.set_no_show_all(True)
        self._check_ignorar.connect("toggled", self._ao_ignorar_pendencias)
        caixa.pack_start(self._check_ignorar, False, False, 0)
        self._pagina_checagens = caixa
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONTENT)
        self.set_page_title(caixa, "Sistema")
        self.set_page_complete(caixa, False)

    def _montar_rede(self) -> None:
        caixa = _pagina("Rede dedicada da placa")
        caixa.pack_start(
            _texto(
                "A placa conversa com o PC por um cabo de rede exclusivo "
                "(não é a internet). Escolha a porta de rede onde o cabo da "
                "placa está conectado. A conexão criada não tem gateway — "
                "sua internet continua funcionando normalmente."
            ),
            False,
            False,
            0,
        )

        grade = Gtk.Grid(column_spacing=12, row_spacing=8)
        rotulo_dev = Gtk.Label(label="Porta de rede:")
        rotulo_dev.set_xalign(0)
        self._combo_dispositivo = Gtk.ComboBoxText()
        grade.attach(rotulo_dev, 0, 0, 1, 1)
        grade.attach(self._combo_dispositivo, 1, 0, 1, 1)
        caixa.pack_start(grade, False, False, 0)

        avancado = Gtk.Expander(label="Avançado")
        grade_av = Gtk.Grid(column_spacing=12, row_spacing=8)
        grade_av.set_margin_top(8)
        rotulo_ip = Gtk.Label(label="IP deste PC no link da placa:")
        rotulo_ip.set_xalign(0)
        self._entrada_ip = Gtk.Entry(text=sistema.IP_HOST_PADRAO)
        self._entrada_ip.set_width_chars(16)
        grade_av.attach(rotulo_ip, 0, 0, 1, 1)
        grade_av.attach(self._entrada_ip, 1, 0, 1, 1)
        avancado.add(grade_av)
        caixa.pack_start(avancado, False, False, 0)

        self._botao_rede = Gtk.Button(label="Criar conexão de rede")
        self._botao_rede.connect("clicked", self._ao_criar_rede)
        caixa.pack_start(self._botao_rede, False, False, 0)

        self._rotulo_rede = _texto("")
        caixa.pack_start(self._rotulo_rede, False, False, 0)

        self._check_pular_rede = Gtk.CheckButton(
            label="Pular esta etapa (configurar a rede depois)"
        )
        self._check_pular_rede.connect("toggled", self._ao_pular_rede)
        caixa.pack_start(self._check_pular_rede, False, False, 0)

        self._pagina_rede = caixa
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONTENT)
        self.set_page_title(caixa, "Rede")
        self.set_page_complete(caixa, False)

    def _montar_drivers(self) -> None:
        caixa = _pagina("Drivers da placa")
        caixa.pack_start(
            _texto(
                "Os drivers (encoder.so, pwmgen.so, STEPDIR-R4.so) são "
                "instalados em /usr/lib/linuxcnc/modules, com backup datado "
                "dos originais. O sistema pedirá a senha de administrador."
            ),
            False,
            False,
            0,
        )
        self._rotulo_drivers = _texto("")
        caixa.pack_start(self._rotulo_drivers, False, False, 0)

        self._botao_drivers = Gtk.Button(label="Instalar drivers…")
        self._botao_drivers.connect("clicked", self._ao_instalar_drivers)
        caixa.pack_start(self._botao_drivers, False, False, 0)

        self._check_pular_drivers = Gtk.CheckButton(
            label="Pular esta etapa (instalar os drivers depois)"
        )
        self._check_pular_drivers.connect("toggled", self._ao_pular_drivers)
        caixa.pack_start(self._check_pular_drivers, False, False, 0)

        self._pagina_drivers = caixa
        self.append_page(caixa)
        self.set_page_type(caixa, Gtk.AssistantPageType.CONTENT)
        self.set_page_title(caixa, "Drivers")
        self.set_page_complete(caixa, False)

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

    def _linhas_sistema(self) -> tuple[str, ...]:
        return (
            "Rede da placa: "
            + ("configurada" if self._rede_feita else "pulada (fazer depois)"),
            "Drivers: "
            + ("instalados" if self._drivers_feitos else "pulados (fazer depois)"),
        )

    # ---- sinais: sistema (F3) -----------------------------------------

    def _ao_ignorar_pendencias(self, check: Gtk.CheckButton) -> None:
        if check.get_active():
            self.set_page_complete(self._pagina_checagens, True)
        elif not self._checagens_ok:
            self.set_page_complete(self._pagina_checagens, False)

    def _preparar_checagens(self) -> None:
        checagens = sistema.pre_checagens(self._executar)
        self._checagens_ok = all(c.ok for c in checagens)
        self._rotulo_checagens.set_text(sistema.texto_checagens(checagens))
        if sistema.precisa_tutorial_linuxcnc(checagens):
            self._tutorial_linuxcnc.show_all()
        else:
            self._tutorial_linuxcnc.hide()
        if self._checagens_ok:
            self._check_ignorar.hide()
            self.set_page_complete(self._pagina_checagens, True)
        else:
            self._check_ignorar.show()
            self.set_page_complete(
                self._pagina_checagens, self._check_ignorar.get_active()
            )

    def _preparar_rede(self) -> None:
        ativo = self._combo_dispositivo.get_active_id()
        self._combo_dispositivo.remove_all()
        dispositivos = sistema.listar_ethernet(self._executar)
        for nome, estado in dispositivos:
            self._combo_dispositivo.append(nome, f"{nome} ({estado})")
        if dispositivos:
            if ativo and not self._combo_dispositivo.set_active_id(ativo):
                self._combo_dispositivo.set_active(0)
            elif not ativo:
                self._combo_dispositivo.set_active(0)
        else:
            self._rotulo_rede.set_text(
                "Nenhuma porta de rede ethernet encontrada. Conecte o cabo "
                "da placa ou pule esta etapa."
            )

    def _ao_pular_rede(self, check: Gtk.CheckButton) -> None:
        self.set_page_complete(
            self._pagina_rede, check.get_active() or self._rede_feita
        )

    def _ao_criar_rede(self, _botao: Gtk.Button) -> None:
        dispositivo = self._combo_dispositivo.get_active_id()
        if not dispositivo:
            self._rotulo_rede.set_text("Escolha a porta de rede primeiro.")
            return
        ip = self._entrada_ip.get_text().strip()
        motivo = sistema.motivo_ip_invalido(ip)
        if motivo:
            self._rotulo_rede.set_text(f"IP {ip} inválido: {motivo}")
            return

        avisos: list[str] = []
        conflitos = sistema.detectar_overlap(self._executar, dispositivo)
        if conflitos:
            avisos.append(sistema.texto_overlap(conflitos))
        if sistema.ip_em_uso(self._executar, dispositivo, ip) == "em_uso":
            self._rotulo_rede.set_text(
                f"O IP {ip} já está em uso no link da placa (arping). "
                "Escolha outro em Avançado."
            )
            return

        resultado = sistema.criar_conexao(self._executar, dispositivo, ip)
        self._rede_feita = resultado.ok
        self._rotulo_rede.set_text(
            "\n\n".join([*avisos, resultado.detalhe])
        )
        if resultado.ok:
            self.set_page_complete(self._pagina_rede, True)

    def _preparar_drivers(self) -> None:
        estados = sistema.estado_drivers()
        self._drivers_feitos = sistema.drivers_ok(estados)
        self._rotulo_drivers.set_text(sistema.texto_estado(estados))
        if self._drivers_feitos:
            self.set_page_complete(self._pagina_drivers, True)

    def _ao_pular_drivers(self, check: Gtk.CheckButton) -> None:
        self.set_page_complete(
            self._pagina_drivers, check.get_active() or self._drivers_feitos
        )

    def _ao_instalar_drivers(self, _botao: Gtk.Button) -> None:
        saida = sistema.instalar_drivers(self._executar)
        if saida.ok:
            estados = sistema.estado_drivers()
            self._drivers_feitos = sistema.drivers_ok(estados)
            self._rotulo_drivers.set_text(
                sistema.texto_estado(estados)
                + "\n\n"
                + saida.stdout.strip()
            )
            self.set_page_complete(self._pagina_drivers, self._drivers_feitos)
        elif saida.codigo in (126, 127):
            self._rotulo_drivers.set_text(
                "Instalação cancelada (senha não confirmada)."
            )
        else:
            self._rotulo_drivers.set_text(
                f"Falha ao instalar os drivers:\n{saida.stderr.strip()}"
            )

    # ---- sinais: config (F2) ------------------------------------------

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
        if pagina is self._pagina_checagens:
            self._preparar_checagens()
        elif pagina is self._pagina_rede:
            self._preparar_rede()
        elif pagina is self._pagina_drivers:
            self._preparar_drivers()
        elif pagina is self._pagina_resumo:
            self._rotulo_resumo.set_text(
                instalacao.texto_resumo(
                    self._parametros(), self._linhas_sistema()
                )
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
            verificacao = sistema.texto_verificacao(
                sistema.verificar(self._executar)
            )
            self._resultado_texto = instalacao.texto_resultado(
                resultado, verificacao
            )

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
