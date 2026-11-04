#!/data/data/com.termux/files/usr/bin/bash
# Roda o LeilãoIA no próprio tablet Android (app Termux, versão da F-Droid).
set -e
pkg update -y
pkg install -y python git libxml2 libxslt libjpeg-turbo freetype rust binutils clang make
[ -d projetoml ] || git clone -b ccr-bb50d683-tfo7gg https://github.com/vivianescaastro/projetoml.git
cd projetoml
pip install -r requirements.txt
export APP_PASSWORD="${APP_PASSWORD:-}"            # opcional: exija senha se outros aparelhos acessarem
echo "Abra no navegador do tablet: http://localhost:8000   (outros aparelhos na mesma Wi-Fi: http://IP-DO-TABLET:8000)"
uvicorn leilaoia.main:app --host 0.0.0.0 --port 8000
