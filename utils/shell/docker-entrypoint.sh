#!/bin/bash
set -e

gradle setup \
  && export PATH="~/.local/bin:${PATH}"

exec "$@"
