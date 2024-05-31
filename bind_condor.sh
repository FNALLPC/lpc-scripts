#!/bin/bash

BIND_CONDOR_CONFIG=/etc/condor/config.d/01_cmslpc_interactive
BIND_CONDOR_PY=/usr/local/bin/cmslpc-local-conf.py
export APPTAINER_BIND=${APPTAINER_BIND}${APPTAINER_BIND:+,}${BIND_CONDOR_CONFIG},${BIND_CONDOR_PY}

export APPTAINERENV_CONDOR_CONFIG=/etc/condor/config.d/01_cmslpc_interactive
