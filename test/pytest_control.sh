#!/bin/bash

die() {
    echo "ERROR: $*. Aborting." >&2
    exit 1
}

setup() {
    python3 -m venv test/venv
    # shellcheck disable=SC1091
    source test/venv/bin/activate
    pip install pytest six
}

teardown() {
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        die "You must call 'deactivate' before removing the virtual environment"
    fi
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        rm -rf test/venv
    fi
}

usage() {
cat <<EOF
usage: pytest_control.sh [options]

This script sets up or tears down (removes) the software needed to run the pytest unit/integration tests
on the python modules in FNALLPC/lpc-scrips.

OPTIONS:
    -o      Run with additional pytest options
    -r      Remove the virtual environment
    -s      Setup the virtual environment
EOF
}

OPTIONS=""
REMOVE="False"
SETUP="False"

#check arguments
while getopts "hors" option; do
    case "${option}" in
        o)  OPTIONS=${OPTARG}
            ;;
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
    if ! return 0 2>/dev/null; then
        echo -e "\nRemember to start the virtual environment before running any tests."
        echo "  source test/venv/bin/activate"
    fi
elif [[ "${REMOVE}" == "True" ]]; then
    teardown
else
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        die "The Python virtual environment is not setup"
    fi
    pytest test/test.py "${OPTIONS}"
fi
