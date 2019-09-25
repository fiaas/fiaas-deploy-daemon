
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
FROM python:2.7.13


ENV DEBIAN_FRONTEND noninteractive

# Python image is based on Debian Jessie
# -> Install Debian backports + Java 8 (For Gradlle)
RUN echo 'deb http://ftp.de.debian.org/debian jessie-backports main' >> /etc/apt/sources.list \
  && apt update \
  && apt install -y -t jessie-backports  \
    openjdk-8-jre-headless \
    ca-certificates-java \
    unzip


# Shamlessly copied from:
# - https://github.com/keeganwitt/docker-gradle/jdk8/Dockerfile
ENV GRADLE_HOME=/opt/gradle \
    GRADLE_VERSION=4.0

ARG GRADLE_DOWNLOAD_SHA256=56bd2dde29ba2a93903c557da1745cafd72cdd8b6b0b83c05a40ed7896b79dfe

RUN set -o errexit -o nounset \
  && echo "Downloading Gradle" \
  && wget --no-verbose --output-document=gradle.zip "https://services.gradle.org/distributions/gradle-${GRADLE_VERSION}-bin.zip" \
  \
  && echo "Checking download hash" \
  && echo "${GRADLE_DOWNLOAD_SHA256} *gradle.zip" | sha256sum --check - \
  \
  && echo "Installing Gradle" \
  && unzip gradle.zip \
  && rm gradle.zip \
  && mv "gradle-${GRADLE_VERSION}" "${GRADLE_HOME}/" \
  && ln --symbolic "${GRADLE_HOME}/bin/gradle" /usr/bin/gradle \
  \
  && echo "Adding gradle user and group" \
  && groupadd --system --gid 1000 gradle \
  && useradd --system --gid gradle --uid 1000 --shell /bin/bash --create-home gradle \
  && mkdir /home/gradle/.gradle \
  && chown --recursive gradle:gradle /home/gradle

# Create Gradle volume
USER gradle
VOLUME "/home/gradle/.gradle"
WORKDIR /home/gradle

RUN set -o errexit -o nounset \
  && echo "Testing Gradle installation" \
  && gradle --version

CMD ["gradle"]
