#!/bin/bash

LPC_CONDOR_CONFIG=/etc/condor/config.d/01_cmslpc_interactive
LPC_CONDOR_LOCAL=/usr/local/bin/cmslpc-local-conf.py

# not all containers have /usr/bin/python3
COMMAND_NAME=$(basename -- "$0")
COMMAND_PATH=$(readlink -f "${BASH_SOURCE[0]}")
if [ "$COMMAND_NAME" = "$(basename $LPC_CONDOR_LOCAL)" ]; then
	python3 ${LPC_CONDOR_LOCAL}.orig | grep -v "LOCAL_CONFIG_FILE"
	exit $?
fi

OSG_CONDOR_CONFIG=/etc/condor/condor_config
OSG_CONDOR_LOCAL=/usr/share/condor/config.d,/etc/condor/config.d

LXP_CONDOR_CONFIG=/etc/condor/condor_config
LXP_CONDOR_LOCAL=/etc/condor/config.d,/usr/bin/myschedd.sh,/usr/bin/myschedd,/etc/myschedd

if [[ "$(uname -a)" == *cms*.fnal.gov* ]]; then
	export APPTAINER_BIND=${APPTAINER_BIND}${APPTAINER_BIND:+,}${LPC_CONDOR_CONFIG},${LPC_CONDOR_LOCAL}:${LPC_CONDOR_LOCAL}.orig,${COMMAND_PATH}:${LPC_CONDOR_LOCAL}
	export APPTAINERENV_CONDOR_CONFIG=${LPC_CONDOR_CONFIG}
elif [[ "$(uname -a)" == *.uscms.org* ]] || [[ "$(uname -a)" == *.osg-htc.org* ]]; then
	export APPTAINER_BIND=${APPTAINER_BIND}${APPTAINER_BIND:+,}${OSG_CONDOR_CONFIG},${OSG_CONDOR_LOCAL}
	export APPTAINERENV_CONDOR_CONFIG=${OSG_CONDOR_CONFIG}
elif [[ "$(uname -a)" == *lxplus*.cern.ch* ]]; then
	export APPTAINER_BIND=${APPTAINER_BIND}${APPTAINER_BIND:+,}${LXP_CONDOR_CONFIG},${LXP_CONDOR_LOCAL}
	export APPTAINERENV_CONDOR_CONFIG=${LXP_CONDOR_CONFIG}
fi
