#!/usr/bin/env bash

# This script compiles the service into a Python Lambda build artifact

set -ex

SERVICE_NAME=titiler

# VERSION
if [ "$TRAVIS" = "true" ]; then
  # Explicitly checkout git branch for versioning:
  git checkout ${TRAVIS_BRANCH}
fi
VERSION=$(wget -O - https://github.com/SenteraLLC/build-support/raw/v1.2.0/version.sh | bash)
VERSION_TAG=$(printf $VERSION | perl -pe 's/[^\w.-]/_/g')
DOCKER_TAG=${SERVICE_NAME}:${VERSION_TAG}

PROJ_DIR=$(git rev-parse --show-toplevel)
BUILD_DIR=${PROJ_DIR}/build
LAMBDA_PATH=${PROJ_DIR}/package.zip

cd ${PROJ_DIR}
rm -rf ${BUILD_DIR}
mkdir -p $(dirname ${BUILD_DIR})
rm -f ${LAMBDA_PATH}
mkdir -p $(dirname ${LAMBDA_PATH})

# Build Docker image and copy build assets out:
cd ${PROJ_DIR}/deployment/aws
docker build -f ${PROJ_DIR}/deployment/aws/lambda/Dockerfile -t ${DOCKER_TAG} .
docker run --rm -it -v ${BUILD_DIR}:/asset-output --entrypoint /bin/bash ${DOCKER_TAG} -c 'cp -R /asset/. /asset-output/.'

# Package up into .zip:
cd ${BUILD_DIR}
zip -r ${LAMBDA_PATH} .
