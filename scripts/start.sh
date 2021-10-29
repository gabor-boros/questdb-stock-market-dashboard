#!/bin/bash

set -o errexit
set -eo pipefail
set -o nounset

cd app
python main.py
