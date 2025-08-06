#!/usr/bin/env bash
set -euo pipefail

# Simple build script for crd-syncer.  Override IMAGE_NAME and IMAGE_TAG
# when calling this script to customise the image name or tag.

IMAGE_NAME=${IMAGE_NAME:-crd-syncer}
IMAGE_TAG=${IMAGE_TAG:-latest}

echo "Building Docker image ${IMAGE_NAME}:${IMAGE_TAG}"
docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" .

echo "Build complete.  To push your image, run:"
echo "  docker push ${IMAGE_NAME}:${IMAGE_TAG}"