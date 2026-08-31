# StepDirR4

Automatização da instalação e configuração da placa **StepDir R4** — primeira placa controladora LinuxCNC do Brasil.

O software substitui o passo a passo manual por dois fluxos guiados (interface GTK3, PT-BR):

1. **Instalador** (roda uma vez): configura a rede ethernet dedicada da placa, instala os drivers realtime com backup dos originais e monta a configuração da máquina em `~/linuxcnc/configs/R4` com atalho na área de trabalho.
2. **Configurador** (uso contínuo): edita `R4.ini`/`R4.hal` por abas (eixos, spindle, probes, entradas/saídas estilo "ports and pins" do Mach3), com Aplicar/Salvar e reinício do LinuxCNC.

**Estado atual (F4 concluída)**: núcleo editor de configuração (parser round-trip de `R4.ini`/`R4.hal`, whitelist de 84 campos em 8 abas, regras de derivação — DEADBAND, espelhos AXIS/JOINT e TRAJ, sinal do home do Z, toggle do eixo A) **+ wizard gráfico de instalação completo** (pré-checagens → rede dedicada → drivers → modelo → dimensões → verificação) **+ configurador gráfico por abas** (estilo "ports and pins": eixos X/Y/Z/A, spindle, probes, entradas/saídas; Aplicar com backup / Salvar / Cancelar; Reiniciar LinuxCNC). **F5**: pacote `.deb` (`./empacotar.sh`), testado nas duas versões do ISO do LinuxCNC.

## Requisitos

- ISO oficial do LinuxCNC (Debian 12 ou 13, kernel PREEMPT-RT) com `linuxcnc-uspace`.
- Placa StepDir R4 conectada por cabo de rede (RJ45) dedicado.
- Python 3.11+ e GTK3/PyGObject (já inclusos no ISO oficial).

## Instalação

### Pacote `.deb` (recomendado)

Um único pacote instala o aplicativo (`/usr/bin/stepdir-r4`), o helper de drivers e os 3 `.so` (`/usr/libexec/stepdir-r4/`), a política polkit, os atalhos do menu e os templates da Spark V2.

Baixe o `.deb` mais recente em **[Releases](https://github.com/LiYuanBr/StepDirR4/releases)** e, na máquina do LinuxCNC:

```bash
sudo apt install ./stepdir-r4_0.1.0_amd64.deb
```

Depois abra **StepDir R4 — Setup** no menu de aplicativos (categoria Sistema) ou rode `stepdir-r4` no terminal. O configurador fica em **StepDir R4 — Config** (`stepdir-r4 configurar`). Todos os subcomandos da CLI abaixo funcionam trocando `PYTHONPATH=src python3 -m stepdir_r4` por `stepdir-r4`.

O `.deb` **não** grava os drivers em `/usr/lib/linuxcnc/modules` na instalação do pacote (conflitaria com o `linuxcnc-uspace`): eles ficam em `/usr/libexec/stepdir-r4/drivers/` e são copiados pelo wizard/`stepdir-r4 drivers`, com senha e backup datado. Instalado pelo pacote, o helper root só aceita essa pasta como origem (e a autorização polkit não fica em cache).

**Gerar o pacote** (em qualquer Debian/Ubuntu, a partir do código-fonte):

```bash
sudo apt install build-essential debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools lintian
./empacotar.sh            # → dist/stepdir-r4_<versão>_amd64.deb (+ relatório do lintian)
```

O pacote é `Architecture: amd64` porque os drivers `.so` são binários amd64. Versão em `pyproject.toml` e `debian/changelog` (o teste `tests/test_empacotamento_f5.py` cobra que batam).


### Instalando o LinuxCNC (pré-requisito)

O software (e o wizard, na verificação do sistema) mostra este mesmo passo a passo quando o LinuxCNC ou o kernel realtime estão faltando:

**Opção 1 — ISO oficial (recomendada):**

1. Baixe o ISO em <https://linuxcnc.org/downloads/> (Debian 13 com kernel PREEMPT-RT e LinuxCNC 2.9 já prontos).
2. Grave o ISO em um pendrive (ex.: balenaEtcher) e instale no computador que vai comandar a máquina.
3. Rode este instalador de novo.

**Opção 2 — Debian 12 ou 13 já instalado:**

```bash
wget https://www.linuxcnc.org/linuxcnc-install.sh
chmod +x linuxcnc-install.sh
sudo ./linuxcnc-install.sh          # configura o repositório oficial
sudo apt install linuxcnc-uspace    # se o script não instalar tudo
```

Depois reinicie e escolha o kernel PREEMPT-RT no menu de boot.

> Ubuntu e Pop!_OS **não têm** o pacote `linuxcnc-uspace` nem kernel realtime disponível — nessas distros, use a Opção 1.

### Rodando do código-fonte (sem instalar o pacote)

A instalação completa funciona pelo assistente gráfico: verificação do sistema, rede dedicada da placa, drivers e a pasta de configuração `~/linuxcnc/configs/R4` a partir dos templates embutidos da Spark V2.

```bash
git clone <este repositório>
cd StepDirR4

# assistente gráfico (recomendado)
PYTHONPATH=src python3 -m stepdir_r4
```

O wizard guia em 8 passos: boas-vindas → **verificação do sistema** (LinuxCNC, kernel PREEMPT-RT, GTK) → **rede da placa** (escolha a porta ethernet do cabo e siga; a conexão `StepDirR4` é criada ao avançar, com IP do PC `192.168.1.10/24` sem gateway — a internet do PC não é afetada; IP editável em "Avançado". A lista mostra a porta da internet marcada como tal e nunca a pré-seleciona) → **drivers** (instala `encoder.so`, `pwmgen.so` e `STEPDIR-R4.so` em `/usr/lib/linuxcnc/modules` com backup datado; pede a senha de administrador) → modelo da CNC (Spark V2) → dimensões da mesa (padrão 800×600 mm, atalho opcional no Desktop) → resumo → instalação + **verificação final** (ping na placa em `192.168.1.177` e integridade dos drivers). As etapas de rede e drivers podem ser puladas e feitas depois. Não execute como root — o assistente recusa.

Alternativa sem GUI (mesmos passos, pelo terminal):

```bash
# pré-checagens do sistema + estado dos drivers:
PYTHONPATH=src python3 -m stepdir_r4 checar

# rede dedicada da placa (porta detectada automaticamente se só uma não for a da internet):
PYTHONPATH=src python3 -m stepdir_r4 rede            # ou --dispositivo enp3s0 --ip 192.168.1.10

# drivers (pede a senha via pkexec, faz backup datado dos originais):
PYTHONPATH=src python3 -m stepdir_r4 drivers

# pasta de configuração (mesa padrão 800x600 mm):
PYTHONPATH=src python3 -m stepdir_r4 instalar        # ou --mesa-x 1000 --mesa-y 700

# verificação final (ping na placa + hash dos drivers; --com-halrun testa o loadrt):
PYTHONPATH=src python3 -m stepdir_r4 verificar
```

O passo `instalar` copia a configuração completa (nunca gera arquivos do zero), aplica `MAX_LIMIT = mesa + 15` nos eixos X/Y, resolve a pasta de programas (`PROGRAM_PREFIX`) via `xdg-user-dir` e cria `launch R4.desktop` + atalho da pasta no Desktop. Se já existir uma pasta `R4`, ela vira backup datado (`R4.bak-<data>`), nunca é perdida.

> Nota sobre a rede: `192.168.1.177` é o IP fixo da placa (não é gateway). Se o seu roteador também usa a faixa `192.168.1.x`, o instalador avisa o conflito — recomendado mudar a faixa do roteador. Um `apt upgrade` do LinuxCNC pode restaurar os drivers originais em silêncio; rode `verificar` (ou a página de drivers do wizard) para conferir e reinstalar.

### Configurador gráfico (uso contínuo)

Depois de instalada, a configuração é editada pelo configurador — sem abrir arquivo na mão:

```bash
PYTHONPATH=src python3 -m stepdir_r4 configurar          # ou --pasta /outra/pasta
```

Oito abas geradas da whitelist (Geral, Eixos X/Y/Z/A, Spindle, Probes, Entradas/Saídas estilo "ports and pins" do Mach3): campos básicos em evidência, avançados no expander "Avançado". O eixo A tem um toggle de habilitar/desabilitar (ajusta `[KINS]`/`[TRAJ]` e as ligações do joint 3 no HAL). Regras derivadas (ex.: `DEADBAND` a partir do `SCALE`) são recalculadas na hora e refletidas na tela.

Botões: **Aplicar** grava a aba atual com backup prévio (**Cancelar** restaura); **Salvar** grava direto; **Reiniciar LinuxCNC** fecha a instância aberta (com aviso) e reabre com a nova configuração. Comentários dos arquivos e edições manuais são preservados — o configurador só toca as variáveis da whitelist.

### Editar a configuração por código (mesma base do configurador)

```python
from stepdir_r4.core import ConfigR4

cfg = ConfigR4.abrir()                                # ~/linuxcnc/configs/R4
delta = cfg.definir("eixo_x.sentido_invertido", False)  # derivações voltam no delta
cfg.definir("io.emergencia.pino", 1)
cfg.aplicar()      # grava com backup (cfg.cancelar() restaura)
# cfg.salvar()     # grava direto, sem backup
```

Só variáveis da whitelist são alteradas; comentários dos arquivos e edições manuais são preservados byte a byte (edição *in-place*).

## Estrutura do projeto

```
src/stepdir_r4/
├── core/            # núcleo F1: editor in-place + instalador da pasta R4
│   ├── config.py    #   ConfigR4 (ler/definir/aplicar/salvar/cancelar)
│   ├── campos.py    #   whitelist (84 campos, 8 abas) e recursos de I/O
│   ├── documento.py #   modelo de linhas com round-trip byte-idêntico
│   └── instalador.py#   instalar_config()
├── gui/             # F2/F4: interfaces GTK3
│   ├── instalacao.py#   lógica pura do wizard (modelos, resumo, textos, markup)
│   ├── wizard.py    #   Gtk.Assistant (8 passos, inclui páginas de sistema)
│   ├── configurador_logica.py  # lógica pura do configurador (abas, faixas, textos)
│   └── configurador.py         # janela de abas (Notebook) gerada da whitelist
├── sistema/         # F3: integração de sistema
│   ├── checagens.py #   pré-checagens (LinuxCNC, kernel RT, GTK, versão)
│   ├── rede.py      #   conexão StepDirR4 via nmcli (sem gateway, overlap, arping)
│   ├── drivers.py   #   estado por hash, instalação via pkexec, teste halrun
│   ├── linuxcnc.py  #   detectar/parar/reabrir o LinuxCNC (botão Reiniciar)
│   ├── helper_drivers.py  # helper root mínimo (chamado por pkexec; no .deb em /usr/libexec/stepdir-r4)
│   └── *.policy     #   política polkit (instalada pelo .deb em /usr/share/polkit-1/actions)
├── __main__.py      # CLI: python3 -m stepdir_r4 / stepdir-r4 [wizard|configurar|instalar|checar|rede|drivers|verificar]
└── data/
    ├── config_r4/   # configuração pronta da Spark V2 → copiada para ~/linuxcnc/configs/R4
    └── drivers/     # drivers realtime (no .deb: /usr/libexec/stepdir-r4/drivers) → /usr/lib/linuxcnc/modules (com backup)
debian/              # F5: empacotamento (control, rules, .desktop ×2, ícone SVG)
empacotar.sh         # gera dist/stepdir-r4_<versão>_amd64.deb
```

## Licença

Ver [LICENSE](LICENSE).
