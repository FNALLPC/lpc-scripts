#!/bin/bash

die() {
    echo "ERROR: $*. Aborting." >&2
    exit 1
}

setup() {
    git clone https://github.com/bats-core/bats-core.git test/bats
    git clone https://github.com/bats-core/bats-support.git test/test_helper/bats-support
    git clone https://github.com/bats-core/bats-assert.git test/test_helper/bats-assert
}

teardown() {
    rm -rf test/bats
    rm -rf test/test_helper
}

usage() {
cat <<EOF
usage: bats_control.sh [options]

This script sets up or tears down (removes) the software needed to run the Bats tests
on the shell scripts in FNALLPC/lpc-scrips.

OPTIONS:
    -r      Remove the Bats software
    -s      Setup the Bats software
EOF
}

REMOVE="False"
SETUP="False"

#check arguments
while getopts "hrs" option; do
    case "${option}" in
        r)  [[ "${SETUP}" == "True" ]] && die "Cannot specify option -r after specifying option -s"
            REMOVE="True"
            ;;
        s)  [[ "${REMOVE}" == "True" ]] && die "Cannot specify option -s after specifying option -r"
            SETUP="True"
            ;;
        h)  usage
            exit 2
            ;;
        \?) echo "Invalid option: -$OPTARG" >&2
            usage
            exit 3
            ;;
        :)  echo "Option -$OPTARG requires an argument." >&2
            exit 4
            ;;
    esac
done

if [[ "${SETUP}" == "True" ]]; then
    setup
elif [[ "${REMOVE}" == "True" ]]; then
    teardown
else
    ./test/bats/bin/bats test/test.bats
fi
