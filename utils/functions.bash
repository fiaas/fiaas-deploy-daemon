#
# Bash wrappers for 'docker run' commands
# Inspired by https://github.com/jfrazelle/dotfiles/
#
#
# vim: set syntax=shell ts=2 :
#

# == Vars
#
PROJECT_DIR="$(git rev-parse --show-toplevel)"



# == Containers Aliases
#
echo "--> Importing 'python' container"
python() {
  docker run --rm \
    --log-driver none \
    --volume='/tmp:/tmp' \
    --volume=$(pwd):/project \
    --workdir=/project \
    --name python_27 \
    --entrypoint 'python' \
    python:3.6.1 "$@"
}
export -f python


echo "--> Importing 'pip' function"
pip() {
  python pip "$@"
}
export -f pip


echo "--> Importing 'gradle' container"
#
# https://hub.docker.com/_/gradle/
#
GRADLE_IMAGE_TAG='jdk8-python'

# Build the docker image if needed
if [[ "$(docker images | grep -i gradle | grep -i ${GRADLE_IMAGE_TAG} 2> /dev/null)" == "" ]]; then
  echo -e "\t * Building Docker image for '${GRADLE_IMAGE_TAG}'"
  docker build \
    -t gradle:${GRADLE_IMAGE_TAG} \
    -f ${PROJECT_DIR}/utils/gradle/Dockerfile \
    ${PROJECT_DIR}/utils/gradle/
fi

gradle(){
  local GRADLE_USER_HOME=${GRADLE_USER_HOME:-${HOME}/.gradle}

  set +e
    if [ ! -d ${GRADLE_USER_HOME} ]; then
      local GRADLE_USER_HOME=${PROJECT_DIR}/.gradle
    fi

    if [ ! -d ${GRADLE_USER_HOME} ]; then
      mkdir -p ${GRADLE_USER_HOME}
    fi
  set +e
  (>&2 echo "INFO: $FUNCNAME - ENV variable 'GRADLE_USER_HOME': ${GRADLE_USER_HOME}")

  docker run --rm \
    --log-driver none \
    --volume="/var/run/docker.sock:/var/run/docker.sock" \
    --volume=$(pwd):/project \
    --workdir=/project \
    --volume="${GRADLE_USER_HOME}:/home/gradle/.gradle" \
    --user=$(echo $UID) \
    --name gradle \
    gradle:${GRADLE_IMAGE_TAG} \
    gradle "$@"
}
export -f gradle


echo "--> Importing 'fiaas-dpld-shell' container"

# Build the docker image if needed
if [[ "$(docker images | grep -i fiaas-dpld-shell 2> /dev/null)" == "" ]]; then
  echo -e "\t * Building Docker image for 'fiaas-dpld-shell'"

  docker build \
    -t fiaas-dpld-shell \
    -f ${PROJECT_DIR}/utils/shell/Dockerfile \
    ${PROJECT_DIR}
fi

fiaas-dpld-shell(){
  local GRADLE_USER_HOME=${GRADLE_USER_HOME:-${HOME}/.gradle}

  set +e
    if [ ! -d ${GRADLE_USER_HOME} ]; then
      local GRADLE_USER_HOME=${PROJECT_DIR}/.gradle
    fi

    if [ ! -d ${GRADLE_USER_HOME} ]; then
      mkdir -p ${GRADLE_USER_HOME}
    fi
  set +e
  (>&2 echo "INFO: $FUNCNAME - ENV variable 'GRADLE_USER_HOME': ${GRADLE_USER_HOME}")

  docker run --rm \
    -it \
    --log-driver none \
    --volume="/var/run/docker.sock:/var/run/docker.sock" \
    --volume=$(pwd):/project \
    --workdir=/project \
    --volume="${GRADLE_USER_HOME}:/home/gradle/.gradle" \
    -P \
    --user=$(echo $UID) \
    fiaas-dpld-shell "$@"
}
export -f fiaas-dpld-shell



echo "--> DONE"
echo "Notes: Please type 'type FUNCTION' to get the definition of the docker container call."

