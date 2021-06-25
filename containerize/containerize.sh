#!/bin/bash -e

CWD=${PWD}
SCRIPTPATH="$( cd -- "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P )"

BASE=
KEEPCACHE="--exclude-caches-all"
CLEAN="false"
DIR="/home/cmsusr"
FILE="Dockerfile"
JSON="${SCRIPTPATH}/cache.json"
TAG="analysis"
TAR=""
VCS="--exclude-vcs"
XRDIR=""

usage(){
    EXIT=$1

    echo "containerize.sh [options]"
    echo ""
	echo "-b [base]           the base image to use (default = ${BASE})"
	echo "-c                  keep the cached files when making the tarball (default = False)"
	echo "-C                  cleanup the temporary files when finished making the image (default = ${ClEAN})"
    echo "-d [dir]            project installation area inside the container (default = ${DIR})"
    echo "-f [file]           the Dockerfile to use to build the image (default = ${FILE})"
    echo "-j [json]           path to the json file containing the path to cache (default = ${JSON})"
    echo "-t [tag]            the tag to use for the image (default = ${TAG})"
	echo "-T [tar]            path to an existing tarball to use (default = ${TAR})"
	echo "-v                  include the vcs directories (default = False)"
	echo "-x [XRDIR]          the path to the tarball on an XRootD accessible device (default = ${XRDIR})"
    echo "-h                  display this message and exit"
	echo
	echo "Examples:"
	echo "./containerize.sh -t <tag> -b docker://docker.io/cmscloud/cc7-cms"
	echo "podman run --rm -it -v /cvmfs/cms.cern.ch/:/cvmfs/cms.cern.ch/:ro 4a73e8eb3bf5f2a3ab84e2eedfb314e3489529e2b02a464cd7eeb0d2782091ff"
	echo "./containerize.sh -t <tag> -b docker://docker.io/aperloff/cms-cvmfs-docker:light -C -v"
	echo "podman run --rm -it <tag>"

    exit $EXIT
}

# process options
while getopts "b:cCd:f:j:t:T:vx:h" opt; do
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
    j) JSON=$OPTARG
    ;;
    t) TAG=$OPTARG
    ;;
    T) TAR=$OPTARG
    ;;
	v) VCS=""
    ;;
    x) XRDIR=$OPTARG
    ;;
    h) usage 0
    ;;
    esac
done

dependency_check() {
	subuid=$(cat /etc/subuid | grep "^`id -u`:")
	subgid=$(cat /etc/subgid | grep "^`id -u`:")
	if [ ! command -v buildah &> /dev/null ]; then
		EXIT=$?
		echo "Buildah could not be found!"
		exit $EXIT
	elif [[ -z "${subuid}" ]] || [[ -z "${subgid}" ]]; then
		echo "Unable to find a subuid or subgid for id=`id -u` in /etc/subuid and /etc/subgid."
		echo "Contact user support or your sysadmin for further assistance."
	fi

	if [ ! command -v podman &> /dev/null ]; then
		echo "Podman could not be found. While this is not strictly necessary, you will not be able to create a container from the resulting image."
	fi
}
dependency_check

# cache unneeded files
CACHEDIR="""\
Signature: 8a477f597d28d172789f06886806bc55\n
# This file is a cache directory tag.\n
# For information about cache directory tags, see:\n
#       http://www.brynosaurus.com/cachedir/
"""
IFS=$'\n'
list_of_cache_files=()
# https://stackoverflow.com/questions/1955505/parsing-json-with-unix-tools
for dir in $(jq -r '.Directories[] | .Path + " " + (.Cache|tostring)' ${JSON}); do
	IFS=' '
	dirarray=($dir)
	path=${dirarray[0]}
	path=`eval echo ${path}`
	cache=${dirarray[1]}
	cache_file=${path}/CACHEDIR.TAG
	if [[ "${cache}" == "1" ]] && [[ ! -f ${cache_file} ]]; then
		echo -e "Cache ${path}"
		echo ${CACHEDIR} > ${cache_file}
		list_of_cache_files=(${list_of_cache_files[@]} ${cache_file})
	elif [[ "${cache}" == "1" ]] && [[ -f ${cache_file} ]]; then
		echo -e "Already cached ${path}"
	elif [[ "${cache}" == "0" ]] && [[ -f ${cache_file} ]]; then
		echo -e "Uncache ${path}"
		rm ${cache_file}
	elif [[ "${cache}" == "0" ]] && [[ ! -f ${cache_file} ]]; then
		echo "Already uncached ${path}"
	fi
done

# tarball of CMSSW area
if [ -z "${TAR}" ]; then
	echo -e "Making the ${CMSSW_VERSION} tarball ... "
	cd ${CMSSW_BASE}/..
    tar ${KEEPCACHE} ${VCS} -zcf ${CMSSW_VERSION}.tar.gz -C ${CMSSW_BASE}/.. ${CMSSW_VERSION}
	TAR="${CMSSW_VERSION}.tar.gz"
fi

# show the tarball
if [ -e "${TAR}" ]; then
	ls -lth ${TAR}
fi

# transfer the tarball if necessary
XRD_TAR=""
CMD_CP=""
CMD_RM=""
if [[ ! -z "${XRDIR}" ]]; then
	if [[ "${XRDIR}" == *"root://"* ]]; then
        CMD_CP="xrdcp"
		CMD_RM="xrdrm"
	elif [[ "${XRDIR}" == *"gsiftp://"* ]]; then
        CMD_CP="env -i X509_USER_PROXY=${X509_USER_PROXY} gfal-copy"
		CMD_RM="env -i X509_USER_PROXY=${X509_USER_PROXY} gfal-rm"
	elif [[ -n "${XRDIR}" ]]; then
        echo "ERROR Unknown transfer protocol for the tarball"
        exit 1
	fi

	if [ -n "$XRDIR" ] && [ -n "$CMD" ]; then
        ${CMD_CP} -f ${TAR} ${XRDIR}/${CMSSW_VERSION}.tar.gz
		XRD_TAR=${XRDIR}/${CMSSW_VERSION}.tar.gz
	fi

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
buildah --root /scratch/containers/`whoami`/ --runroot /scratch/containers/`whoami`/ bud -f ${FILE} -t ${TAG} -v /cvmfs/cms.cern.ch:/cvmfs/cms.cern.ch \
		--build-arg BUILDIMAGE=${BUILDIMAGE} --build-arg BASEIMAGE=${BASE} --build-arg BUILD_DATE=`date -u +%Y-%m-%d` --build-arg ANALYSIS_NAME=${NAME} \
		--build-arg CMSSW_VERSION=${CMSSW_VERSION} --build-arg TAR=`realpath --relative-to="${PWD}" "${TAR}"`

# Cleanup the temporary files
if [[ "${CLEAN}" == "true" ]]; then
	echo -e "Cleaning the temporary files made while building the images ..."
	echo -e "\tRemoving the tarball ${TAR} ..."
	rm ${TAR}
	if [[ ! -z "${XRDIR}" ]]; then
		echo -e "\tRemoving the remote tarball ${XRD_TAR} ..."
		${CMD_RM} ${XRD_TAR}
	fi
	for f in "${list_of_cache_files[@]}"; do
		echo -e "\tRemoving the cache file ${f} ..."
		rm ${f}
	done
fi

# Return to the original working directory
cd ${CWD}
