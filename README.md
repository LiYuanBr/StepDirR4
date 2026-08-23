# StepDirR4

Automatização da instalação e configuração da placa **StepDir R4** — primeira placa controladora LinuxCNC do Brasil.

O software substitui o passo a passo manual por dois fluxos guiados (interface GTK3, PT-BR):

1. **Instalador** (roda uma vez): configura a rede ethernet dedicada da placa, instala os drivers realtime com backup dos originais e monta a configuração da máquina em `~/linuxcnc/configs/R4` com atalho na área de trabalho.
2. **Configurador** (uso contínuo): edita `R4.ini`/`R4.hal` por abas (eixos, spindle, probes, entradas/saídas estilo "ports and pins" do Mach3), com Aplicar/Salvar e reinício do LinuxCNC.

**Estado atual (F1 concluída)**: núcleo editor de configuração pronto, sem GUI — parser round-trip de `R4.ini`/`R4.hal`, whitelist de 83 campos em 8 abas, regras de derivação (DEADBAND, espelhos AXIS/JOINT e TRAJ, sinal do home do Z) e montagem da pasta R4 por linha de comando. GUI (wizard), rede e drivers chegam nas próximas fases (ver `specs/roadmap.md`).

## Requisitos

- ISO oficial do LinuxCNC (Debian 12 ou 13, kernel PREEMPT-RT) com `linuxcnc-uspace`.
- Placa StepDir R4 conectada por cabo de rede (RJ45) dedicado.
- Python 3.11+ e GTK3/PyGObject (já inclusos no ISO oficial).

## Instalação

> ⚠️ Em desenvolvimento — a entrega final será um pacote único (`sudo apt install ./stepdir-r4.deb`). Este tutorial é atualizado a cada fase.

### Tutorial (estado atual — F1, sem GUI)

O que já funciona: montar a pasta de configuração `~/linuxcnc/configs/R4` a partir dos templates embutidos da Spark V2, com as dimensões da sua mesa e launcher na área de trabalho. (Rede e drivers ainda são manuais — ver `specs-readme.md` na máquina de desenvolvimento.)

```bash
git clone <este repositório>
cd StepDirR4

# monta ~/linuxcnc/configs/R4 (mesa padrão 800x600 mm):
PYTHONPATH=src python3 -m stepdir_r4 instalar

# mesa com outras dimensões:
PYTHONPATH=src python3 -m stepdir_r4 instalar --mesa-x 1000 --mesa-y 700
```

O comando copia a configuração completa (nunca gera arquivos do zero), aplica `MAX_LIMIT = mesa + 15` nos eixos X/Y, resolve a pasta de programas (`PROGRAM_PREFIX`) via `xdg-user-dir` e cria `launch R4.desktop` + atalho da pasta no Desktop. Se já existir uma pasta `R4`, ela vira backup datado (`R4.bak-<data>`), nunca é perdida.

### Editar a configuração por código (base do futuro configurador)

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
│   ├── campos.py    #   whitelist (83 campos, 8 abas) e recursos de I/O
│   ├── documento.py #   modelo de linhas com round-trip byte-idêntico
│   └── instalador.py#   instalar_config()
├── __main__.py      # CLI: python3 -m stepdir_r4 instalar
└── data/
    ├── config_r4/   # configuração pronta da Spark V2 → copiada para ~/linuxcnc/configs/R4
    └── drivers/     # drivers realtime → instalados em /usr/lib/linuxcnc/modules (com backup)
specs/               # fonte de verdade das decisões (missão, stack, roadmap)
CONTEXT.md           # vocabulário de domínio
```

## Licença

Ver [LICENSE](LICENSE).
