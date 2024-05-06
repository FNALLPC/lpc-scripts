#!/bin/bash

# concept based on https://stackoverflow.com/questions/32163955/how-to-run-shell-script-on-host-from-docker-container

# execute command sent to host pipe; send output to container pipe; send terminating string when command finishes
listenhost(){
	# stop when host pipe is removed
	while [ -e $1 ]; do
		# "|| true" is necessary to stop "Interrupted system call"
		# must be *inside* eval to ensure EOF once command finishes
		eval "$(cat $1) || true" >& $2
	done
}
export -f listenhost

# creates randomly named pipe and prints the name
makepipe(){
	PREFIX=$1
	PIPETMP=$(readlink -f ~/nobackup/${PREFIX}_$(uuidgen))
	mkfifo $PIPETMP
	echo $PIPETMP
}
export -f makepipe

# to be run on host before launching each apptainer session
startpipe(){
	HOSTPIPE=$(makepipe HOST)
	CONTPIPE=$(makepipe CONT)
	# export HOSTPIPE and CONTPIPE to apptainer
	echo "export APPTAINERENV_HOSTPIPE=$HOSTPIPE; export APPTAINERENV_CONTPIPE=$CONTPIPE"
}
export -f startpipe

# sends function to host, then listens for output
call_host(){
	if [ "$FUNCNAME" = "call_host" ]; then
		FUNCTMP=
	else
		FUNCTMP=$FUNCNAME
	fi
	echo "cd $PWD; $FUNCTMP $@" > $HOSTPIPE
	cat < $CONTPIPE
}
export -f call_host

# from https://stackoverflow.com/questions/1203583/how-do-i-rename-a-bash-function
copy_function() {
	test -n "$(declare -f "$1")" || return
	eval "${_/$1/$2}"
}
export -f copy_function

# set this default on host, but not in container (in case overridden)
if [ -z "$APPTAINER_CONTAINER" ]; then
	export DISABLE_PIPE_CONDOR=0
fi
if [ -z "$APPTAINER_ORIG" ]; then
	export APPTAINER_ORIG=$(which apptainer)
fi
apptainer(){
	if [ "$DISABLE_PIPE_CONDOR" -eq 1 ]; then
		(
		export APPTAINERENV_DISABLE_PIPE_CONDOR=1
		$APPTAINER_ORIG "$@"
		)
	else
		# in subshell to contain exports
		(
		eval $(startpipe)
		listenhost $APPTAINERENV_HOSTPIPE $APPTAINERENV_CONTPIPE &
		LISTENER=$!
		$APPTAINER_ORIG "$@"
		# avoid dangling cat process after exiting container
		pkill -P $LISTENER
		rm -f $APPTAINERENV_HOSTPIPE $APPTAINERENV_CONTPIPE
		)
	fi
}
export -f apptainer

# on host: get list of condor executables
if [ -z "$APPTAINER_CONTAINER" ]; then
	export APPTAINERENV_HOSTFNS=$(compgen -c | grep ^condor_)
# in container: replace with call_host versions
elif [ "$DISABLE_PIPE_CONDOR" -ne 1 ]; then
	for HOSTFN in $HOSTFNS; do
		copy_function call_host $HOSTFN
	done
	# cleanup
	trap "rm -f $HOSTPIPE $CONTPIPE" EXIT
fi
