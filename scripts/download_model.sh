#!/usr/bin/env bash
# Download the MediaPipe Gesture Recognizer model into models/.
# Usage: bash scripts/download_model.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_DIR="${REPO_ROOT}/models"
MODEL_FILE="${MODEL_DIR}/gesture_recognizer.task"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task"

mkdir -p "${MODEL_DIR}"

if [[ -f "${MODEL_FILE}" ]]; then
    echo "Model already present: ${MODEL_FILE}"
    echo "Delete it and re-run this script to force a fresh download."
    exit 0
fi

TEMP_FILE="${MODEL_FILE}.tmp"

# Clean up the temp file on error so a re-run triggers a fresh download.
trap 'rm -f "${TEMP_FILE}"' ERR

echo "Downloading gesture_recognizer.task from Google MediaPipe storage..."
curl --fail --location --progress-bar \
    --output "${TEMP_FILE}" \
    "${MODEL_URL}"

mv "${TEMP_FILE}" "${MODEL_FILE}"
echo ""
echo "Saved to: ${MODEL_FILE}"
echo "Size: $(du -sh "${MODEL_FILE}" | cut -f1)"
