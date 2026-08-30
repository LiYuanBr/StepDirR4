#!/bin/sh
# Gera o pacote .deb da StepDir R4 (F5) em dist/.
# Requer: build-essential debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools
#   sudo apt install build-essential debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools lintian
set -eu
cd "$(dirname "$0")"

for dep in build-essential debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools; do
    if ! dpkg -s "$dep" >/dev/null 2>&1; then
        echo "Falta o pacote $dep. Instale com:" >&2
        echo "  sudo apt install build-essential debhelper dh-python pybuild-plugin-pyproject python3-all python3-setuptools lintian" >&2
        exit 1
    fi
done

versao=$(dpkg-parsechangelog -S Version)
dpkg-buildpackage -us -uc -b
mkdir -p dist
mv ../stepdir-r4_"$versao"_*.deb ../stepdir-r4_"$versao"_*.buildinfo ../stepdir-r4_"$versao"_*.changes dist/

echo
echo "Pacote gerado:"
ls -1 dist/stepdir-r4_"$versao"_*.deb
if command -v lintian >/dev/null 2>&1; then
    echo
    lintian dist/stepdir-r4_"$versao"_*.deb || true
fi
echo
echo "Instalar: sudo apt install ./dist/stepdir-r4_${versao}_amd64.deb"
