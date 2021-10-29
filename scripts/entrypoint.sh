#!/bin/bash

set -o errexit
set -eo pipefail
set -o nounset

exec "$@"
