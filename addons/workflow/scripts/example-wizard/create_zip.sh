#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

OUTPUT_NAME="example-wizard-v0.zip"
OUTPUT_PATH="$(pwd)/${OUTPUT_NAME}"

rm -f "${OUTPUT_PATH}"

zip -r "${OUTPUT_PATH}" \
    "${OUTPUT_NAME%.zip}.json" \
    bpmn-models/ \
    form-models/ \
    -x '*.DS_Store'

echo "Created: ${OUTPUT_PATH}"
