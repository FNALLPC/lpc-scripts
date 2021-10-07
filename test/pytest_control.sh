#!/bin/bash

error_pytest_control() {
    echo "ERROR: $*. Aborting." >&2
    return 1
}

setup_pytest_venv() {
    python3 -m venv test/venv
    echo "Starting the virtual env now ..."
    # shellcheck disable=SC1091
    source test/venv/bin/activate
    echo -e "In the future:\n" \
            "\t1. Enter the virtual environment using 'source test/venv/bin/activate'\n"\
            "\t2. To leave the virtual environment use the command 'deactivate'\n"
    pip install pytest six
}

teardown_pytest_venv() {
    if [[ "$VIRTUAL_ENV" != "" ]]; then
        deactivate
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

OPTIND=1
OPTIONS=""
REMOVE="False"
SETUP="False"

#check arguments
while getopts "ho:rs" option; do
    case "${option}" in
        o)  OPTIONS=${OPTARG}
            ;;
        r)  [[ "${SETUP}" == "True" ]] && error_pytest_control "Cannot specify option -r after specifying option -s"
            REMOVE="True"
            ;;
        s)  [[ "${REMOVE}" == "True" ]] && error_pytest_control "Cannot specify option -s after specifying option -r"
            SETUP="True"
            ;;
        h)  usage
            return 2
            ;;
        \?) echo "Invalid option: -$OPTARG" >&2
            usage
            return 3
            ;;
        :)  echo "Option -$OPTARG requires an argument." >&2
            return 4
            ;;
    esac
done

if [[ "${SETUP}" == "True" ]]; then
    setup_pytest_venv
elif [[ "${REMOVE}" == "True" ]]; then
    teardown_pytest_venv
else
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        error_pytest_control "The Python virtual environment is not setup"
    else
        pytest test/test.py "${OPTIONS}"
    fi
fi
