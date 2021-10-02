#!/bin/bash -e

clean(){
    local args=("$@")
    local tarball=${args[0]}
    local list_of_cache_files=("${args[@]:1}")
    echo -e "Cleaning the temporary files made while building the images ..."
    echo -e "\tRemoving the tarball ${tarball} ..."
    rm "${tarball}"
    for f in "${list_of_cache_files[@]}"; do
        echo -e "\tRemoving the cache file ${f} ..."
        rm "${f}"
    done
}

splitpath(){
    local ret
    ret="-C $(dirname "${1}") $(basename "${1}")"
    echo "${ret}"
}

CWD=${PWD}
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

BASE=
KEEPCACHE="--exclude-caches-all"
CLEAN="false"
DIR="/home/cmsusr"
FILE="${SCRIPTPATH}/Dockerfile"
INCLUDE=""
JSON="${SCRIPTPATH}/cache.json"
MAXTARSIZE=104857600
ROOT="/scratch/containers/$(whoami)/"
TAG="analysis"
TAR=""
USER="cmsusr"
VCS="--exclude-vcs"

usage(){
    EXIT=$1

    echo "containerize.sh [options]"
    echo ""
    echo "-b [base]           the base image to use (default = ${BASE})"
    echo "-c                  keep the cached files when making the tarball (default = False)"
    echo "-C                  cleanup the temporary files when finished making the image (default = ${CLEAN})"
    echo "-d [dir]            project installation area inside the container (default = ${DIR})"
    echo "-f [file]           the Dockerfile to use to build the image (default = ${FILE})"
    echo "-t [include]        list specific files or directories (absolute path) to include in the tarball (default = ${INCLUDE})"
    echo "-j [json]           path to the json file containing the path to cache (default = ${JSON})"
    echo "-m [maxsize]        the maximum size (in bytes) of the tarball before returning an error (defaul = ${MAXTARSIZE})"
    echo "-r [root]           change the 'root' and 'runroot' locations for buildah (default = ${ROOT})"
    echo "-t [tag]            the tag to use for the image (default = ${TAG})"
    echo "-T [tar]            path to an existing tarball to use (default = ${TAR})"
    echo "-u [user]           override the default username in the container (default = ${USER})"
    echo "-v                  include the vcs directories (default = False)"
    echo "-h                  display this message and exit"
    echo
    echo "Examples:"
    echo "./containerize.sh -t <name>:<tag> -b docker://docker.io/cmscloud/cc7-cms"
    echo "podman run --rm -it -v /cvmfs/cms.cern.ch/:/cvmfs/cms.cern.ch/:ro <name>:<tag>"
    echo "./containerize.sh -t <name>:<tag> -b docker://docker.io/aperloff/cms-cvmfs-docker:light -C -v"
    echo "podman run --rm -it <name>:<tag>"

    exit "${EXIT}"
}

# process options
while getopts "b:cCd:f:i:j:m:r:t:T:u:vh" opt; do
    case "$opt" in
    b) BASE=$OPTARG
    ;;
    c) KEEPCACHE=""
    ;;
    C) CLEAN="true"
    ;;
    d) DIR=$OPTARG
    ;;
    f) FILE=$OPTARG
    ;;
    i) INCLUDE+=("$OPTARG")
    ;;
    j) JSON=$OPTARG
    ;;
    m) MAXTARSIZE=$OPTARG
    ;;
    r) ROOT=$OPTARG
    ;;
    t) TAG=$OPTARG
    ;;
    T) TAR=$OPTARG
    ;;
    u) USER=$OPTARG
    ;;
    v) VCS=""
    ;;
    h) usage 0
    ;;
    *) usage 1
    ;;
    esac
done

dependency_check() {
    subuid=$(< /etc/subuid grep "^$(id -u):")
    subgid=$(< /etc/subgid grep "^$(id -u):")
    if ! command -v buildah &> /dev/null; then
        EXIT=$?
        echo "Buildah could not be found!"
        exit ${EXIT}
    elif ! command -v jq &> /dev/null; then
        EXIT=$?
        echo "jq could not be found!"
        exit ${EXIT}
    elif [[ ! -d ${ROOT} ]]; then
        EXIT=$?
        echo "The directory ${ROOT} does not exist and cannot be used for buildah's 'root' or 'runroot' directory."
        exit "${EXIT}"
    elif [[ -z "${subuid}" ]] || [[ -z "${subgid}" ]]; then
        echo "Unable to find a subuid or subgid for id=$(id -u) in /etc/subuid and /etc/subgid."
        echo "Contact user support or your sysadmin for further assistance."
    elif [[ ! -d /cvmfs/cms.cern.ch ]] || ! cvmfs_config probe cms.cern.ch &> /dev/null; then
        EXIT=$?
        echo "/cvmfs/cms.cern.ch must be mounted on the host to proceed."
        exit "${EXIT}"
    fi

    if ! command -v podman &> /dev/null ; then
        echo "Podman could not be found. While this is not strictly necessary, you will not be able to create a container from the resulting image."
    fi
}
dependency_check

# cache unneeded files
CACHEDIR=" \
Signature: 8a477f597d28d172789f06886806bc55\n
# This file is a cache directory tag.\n
# For information about cache directory tags, see:\n
#       http://www.brynosaurus.com/cachedir/
"
IFS=$'\n'
list_of_cache_files=()
# https://stackoverflow.com/questions/1955505/parsing-json-with-unix-tools
for dir in $(jq -r '.Directories[] | .Path + " " + (.Cache|tostring)' "${JSON}"); do
    IFS=' '
    dirarray=("$dir")
    path=${dirarray[0]}
    path=$(eval echo "${path}")
    cache=${dirarray[1]}
    cache_file=${path}/CACHEDIR.TAG
    if [[ "${cache}" == "1" ]] && [[ ! -f ${cache_file} ]]; then
        echo -e "Cache ${path}"
        echo "${CACHEDIR} > ${cache_file}"
        list_of_cache_files=("${list_of_cache_files[@]}" "${cache_file}")
    elif [[ "${cache}" == "1" ]] && [[ -f "${cache_file}" ]]; then
        echo -e "Already cached ${path}"
    elif [[ "${cache}" == "0" ]] && [[ -f "${cache_file}" ]]; then
        echo -e "Uncache ${path}"
        rm "${cache_file}"
    elif [[ "${cache}" == "0" ]] && [[ ! -f "${cache_file}" ]]; then
        echo "Already uncached ${path}"
    fi
done

# tarball of CMSSW area
if [ -z "${TAR}" ]; then
    echo -e "Making the ${CMSSW_VERSION} tarball ... "
    cd "${CMSSW_BASE}/.."

    INDIVIDUAL_FILES=""
    for f in "${INCLUDE[@]}"; do
        if [[ "${f}" == "" ]]; then
            continue
        fi
        INDIVIDUAL_FILES="${INDIVIDUAL_FILES} $(splitpath "${f}")"
    done

    tar "${KEEPCACHE}" "${VCS}" -zcf "${CMSSW_VERSION}".tar.gz -C "${CMSSW_BASE}"/.. "${CMSSW_VERSION}" "${INDIVIDUAL_FILES}"
    TAR="${CMSSW_VERSION}.tar.gz"
fi

# show the tarball
if [ -e "${TAR}" ]; then
    ls -lth "${TAR}"
fi

# Output an error and exit if the tarball is too large
TARSIZE=$(stat -c%s "$TAR")
if (( TARSIZE > MAXTARSIZE )); then
    echo "ERROR::The tarball generated is too large ($TARSIZE bytes)."
    echo "A large tarball can lead to really large image sizes."
    echo "Either cache unneeded directories or increase the allowable tarball size (-m [maxsize])."

    # Even though the code is stopped early, we still want to cleanup the temporary files
    if [[ "${CLEAN}" == "true" ]]; then
        clean "${TAR}" "${list_of_cache_files[@]}"
    fi

    exit 2
fi

# select the correct build image based on the SCRAM_ARCH of the CMSSW release
ARCH=${SCRAM_ARCH%%_*}
ARCH_VER=${ARCH: -1}
BUILDIMAGE=docker://docker.io/cmscloud/
if [[ "${ARCH_VER}" == "5" ]] || [[ "${ARCH_VER}" == "6" ]]; then
    BUILDIMAGE=${BUILDIMAGE}slc${ARCH_VER}-cms
elif [[ "${ARCH_VER}" == "7" ]]; then
    BUILDIMAGE=${BUILDIMAGE}cc${ARCH_VER}-cms
else
    echo -e "Unknown CMSSW architecture version (${SCRAM_ARCH} -- > ${ARCH} -- > ${ARCH_VER}). Defaulting to cc7."
    BUILDIMAGE=${BUILDIMAGE}cc${ARCH_VER}-cms
fi

# build the image
echo -e "Building the image ..."
buildah --root "${ROOT}" --runroot "${ROOT}" bud -f "${FILE}" -t "${TAG}" -v /cvmfs/cms.cern.ch:/cvmfs/cms.cern.ch \
        --build-arg BUILDIMAGE="${BUILDIMAGE}" --build-arg BASEIMAGE="${BASE}" --build-arg BUILD_DATE="$(date -u +%Y-%m-%d)" --build-arg ANALYSIS_NAME="${NAME}" \
        --build-arg CMSSW_VERSION="${CMSSW_VERSION}" --build-arg TAR="$(realpath --relative-to="${PWD}" "${TAR}")" --build-arg NONPRIVILEGED_USER="${USER}"

# Cleanup the temporary files
if [[ "${CLEAN}" == "true" ]]; then
    clean "${TAR}" "${list_of_cache_files[@]}"
fi

# Return to the original working directory
cd "${CWD}"
