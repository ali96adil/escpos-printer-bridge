#!/usr/bin/env sh
set -e

export PRINTER_IP="$(jq -r '.printer_ip' /data/options.json)"
export PRINTER_PORT="$(jq -r '.printer_port' /data/options.json)"

python /app.py