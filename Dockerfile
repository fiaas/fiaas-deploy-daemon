
# Copyright 2017-2019 The FIAAS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


# build image with ./bin/docker_build

FROM python:3.12-alpine AS common
LABEL org.opencontainers.image.authors="fiaas@googlegroups.com"
# Install any binary package dependencies here
RUN apk --no-cache add \
    yaml

FROM common AS build
# Install build tools, and build wheels of all dependencies
RUN apk --no-cache add \
    build-base \
    git \
    yaml-dev

COPY . /fiaas-deploy-daemon
COPY .wheel_cache/*.whl /links/
WORKDIR /fiaas-deploy-daemon

RUN pip wheel . --no-cache-dir --wheel-dir=/wheels/ --find-links=/links/

FROM common AS production

# Get rid of all build dependencies, install application using only pre-built binary wheels
COPY --from=build /wheels/ /wheels/
RUN pip install --no-index --find-links=/wheels/ --only-binary all /wheels/fiaas_deploy_daemon*.whl

RUN addgroup -g 1001 -S fiaas && \
    adduser -u 1001 -S fiaas -G fiaas

USER fiaas

EXPOSE 5000
CMD ["fiaas-deploy-daemon"]
