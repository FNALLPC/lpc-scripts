#!/bin/bash

# default values
if [ -z "$PIPE_CONDOR_DIR" ]; then
	export PIPE_CONDOR_DIR=~/nobackup/pipes
fi
export PIPE_CONDOR_DIR=$(readlink -f $PIPE_CONDOR_DIR)
mkdir -p $PIPE_CONDOR_DIR
# ensure the pipe dir is bound
export APPTAINER_BIND=${APPTAINER_BIND}${APPTAINER_BIND:+,}${PIPE_CONDOR_DIR}

# concept based on https://stackoverflow.com/questions/32163955/how-to-run-shell-script-on-host-from-docker-container

# execute command sent to host pipe; send output to container pipe; store exit code
listenhost(){
	# stop when host pipe is removed
	while [ -e $1 ]; do
		# "|| true" is necessary to stop "Interrupted system call"
		# must be *inside* eval to ensure EOF once command finishes
		# now replaced with assignment of exit code to local variable (which also returns true)
		tmpexit=0
		eval "$(cat $1) || tmpexit="'$?' >& $2
		echo $tmpexit > $3
	done
}
export -f listenhost

# creates randomly named pipe and prints the name
makepipe(){
	PREFIX=$1
	PIPETMP=${PIPE_CONDOR_DIR}/${PREFIX}_$(uuidgen)
	mkfifo $PIPETMP
	echo $PIPETMP
}
export -f makepipe

# to be run on host before launching each apptainer session
startpipe(){
	HOSTPIPE=$(makepipe HOST)
	CONTPIPE=$(makepipe CONT)
	EXITPIPE=$(makepipe EXIT)
	# export pipes to apptainer
	echo "export APPTAINERENV_HOSTPIPE=$HOSTPIPE; export APPTAINERENV_CONTPIPE=$CONTPIPE; export APPTAINERENV_EXITPIPE=$EXITPIPE"
}
export -f startpipe

# sends function to host, then listens for output, and provides exit code from function
call_host(){
	if [ "$FUNCNAME" = "call_host" ]; then
		FUNCTMP=
	else
		FUNCTMP=$FUNCNAME
	fi
	echo "cd $PWD; $FUNCTMP $@" > $HOSTPIPE
	cat < $CONTPIPE
	return $(cat < $EXITPIPE)
}
export -f call_host

# from https://stackoverflow.com/questions/1203583/how-do-i-rename-a-bash-function
copy_function() {
	test -n "$(declare -f "$1")" || return
	eval "${_/$1/$2}"
	eval "export -f $2"
}
export -f copy_function

# set this default on host, but not in container (in case overridden)
if [ -z "$APPTAINER_CONTAINER" ]; then
	export PIPE_CONDOR_DISABLE=0
fi
if [ -z "$APPTAINER_ORIG" ]; then
	export APPTAINER_ORIG=$(which apptainer)
fi
# always set this (in case of nested containers)
export APPTAINERENV_APPTAINER_ORIG=$APPTAINER_ORIG
apptainer(){
	if [ "$PIPE_CONDOR_DISABLE" -eq 1 ]; then
		(
		export APPTAINERENV_PIPE_CONDOR_DISABLE=1
		$APPTAINER_ORIG "$@"
		)
	else
		# in subshell to contain exports
		(
		eval $(startpipe)
		listenhost $APPTAINERENV_HOSTPIPE $APPTAINERENV_CONTPIPE $APPTAINERENV_EXITPIPE &
		LISTENER=$!
		$APPTAINER_ORIG "$@"
		# avoid dangling cat process after exiting container
		pkill -P $LISTENER
		rm -f $APPTAINERENV_HOSTPIPE $APPTAINERENV_CONTPIPE $APPTAINERENV_EXITPIPE
		)
	fi
}
export -f apptainer

# on host: get list of condor executables
if [ -z "$APPTAINER_CONTAINER" ]; then
	export APPTAINERENV_HOSTFNS=$(compgen -c | grep ^condor_)
# in container: replace with call_host versions
elif [ "$PIPE_CONDOR_DISABLE" -ne 1 ]; then
	for HOSTFN in $HOSTFNS; do
		copy_function call_host $HOSTFN
	done
	# cleanup
	trap "rm -f $HOSTPIPE $CONTPIPE $EXITPIPE" EXIT
fi
