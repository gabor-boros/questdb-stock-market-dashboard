#!/bin/bash

set -o errexit
set -eo pipefail
set -o nounset

python -m celery --app app.worker.celery_app worker --beat -l info -c 1
