#!/bin/bash
# shellcheck disable=SC2155,SC2223

# check for configuration
CALL_HOST_CONFIG=~/.callhostrc
if [ -f "$CALL_HOST_CONFIG" ]; then
	# shellcheck source=/dev/null
	source "$CALL_HOST_CONFIG"
fi

# zsh / bash compatibility helpers
is_zsh(){
	# detect the current shell process name (portable ps usage)
	if command -v ps >/dev/null 2>&1; then
		# get last path component if ps returns full path
		p="$(ps -p $$ -o comm= 2>/dev/null | awk -F/ '{print $NF}')"
		case "$p" in
			zsh) return 0 ;;
			bash) return 1 ;;
		esac
	fi

	# fallback: check common names for $0 or $ZSH_NAME (login shells may have a leading dash)
	case "$(basename -- "${ZSH_NAME:-$0}" 2>/dev/null)" in
		zsh|-zsh) return 0 ;;
	esac

	return 1
}

if is_zsh; then
	# export a function to the environment for child shells (zsh)
	export_func(){
		typeset -fx "$1" 2>/dev/null || true
	}
	# declare an associative array (zsh)
	declare_assoc(){
		typeset -A "$1"
	}
	# get current function name in zsh (be tolerant if indices differ)
	current_funcname(){
		# Ensure standard zsh array indexing (1-based) regardless of user options
		emulate -L zsh
		# funcstack[1] is current function in zsh (1-indexed by default)
		# Handle potential edge cases with fallbacks
		printf '%s' "${funcstack[2]:-}"
	}
	# get function definition (zsh)
	get_function(){
		functions "$1" 2>/dev/null
	}
else
	# bash
	export_func(){
		[ -n "$1" ] || return
		# shellcheck disable=SC2163
		export -f "$1" 2>/dev/null || true
	}
	declare_assoc(){
		# create named associative array in bash
		declare -gA "$1"
	}
	current_funcname(){
		# return the caller function name if available (FUNCNAME[1]), otherwise fall back to FUNCNAME[0]
		if [ -n "${FUNCNAME[1]:-}" ]; then
			echo "${FUNCNAME[1]}"
		else
			echo "${FUNCNAME[0]:-}"
		fi
	}
	# get function definition (bash)
	get_function(){
		declare -f "$1" 2>/dev/null
	}
fi

# portable indirect variable access (works in both bash and zsh)
getvar(){
	eval "printf '%s' \"\${$1:-}\""
}

# validation
call_host_valid(){
	VAR_TO_VALIDATE="$1"
	# retrieve the value of the named variable
	VARVAL="$(getvar "$VAR_TO_VALIDATE")"
	# check allowed values using portable case statement
	case "$VARVAL" in
		enable|disable)
			# valid value, do nothing
			;;
		*)
			echo "Warning: unsupported value $VARVAL for $VAR_TO_VALIDATE; disabling"
			eval "export $VAR_TO_VALIDATE=disable"
			;;
	esac
}
export_func call_host_valid

# default values
: ${CALL_HOST_STATUS:=enable}
call_host_valid CALL_HOST_STATUS
: ${CALL_HOST_DEBUG:=disable}
call_host_valid CALL_HOST_DEBUG
if [ -z "$CALL_HOST_DIR" ]; then
	if [[ "$(uname -a)" == *cms*.fnal.gov* ]]; then
		export CALL_HOST_DIR=~/nobackup/pipes
	elif [[ "$(uname -a)" == *.uscms.org* ]] || [[ "$(uname -a)" == *.osg-htc.org* ]] || [[ "$(uname -a)" == *cmscon.hep.wisc.edu* ]]; then
		export CALL_HOST_DIR=/scratch/$(whoami)/pipes
	elif [[ "$(uname -a)" == *lxplus*.cern.ch* ]]; then
		export CALL_HOST_DIR=/tmp/$(whoami)/pipes
	else
		echo "Warning: no default CALL_HOST_DIR for $(uname -a), please set your own manually. disabling"
		export CALL_HOST_STATUS=disable
	fi
fi
CALL_HOST_DIR_ORIG="$CALL_HOST_DIR"
export CALL_HOST_DIR=$(readlink -f "$CALL_HOST_DIR_ORIG")
if [ -z "$CALL_HOST_DIR" ]; then
	echo "Warning: readlink -f failed for CALL_HOST_DIR $CALL_HOST_DIR_ORIG. disabling"
	export CALL_HOST_STATUS=disable
fi
mkdir -p "$CALL_HOST_DIR"
if [ ! -d "$CALL_HOST_DIR" ]; then
	echo "Warning: could not create specified dir CALL_HOST_DIR $CALL_HOST_DIR. disabling"
	export CALL_HOST_STATUS=disable
fi

# helper: add value to a PATH-like variable only if not already present
add_path_unique(){
	# args: varname value [sep]
	varname="$1"; val="$2"; sep="${3:-:}"
	# retrieve current value portably
	cur="$(getvar "$varname")"
	# if empty, set and export
	if [ -z "$cur" ]; then
		eval "export $varname=\"\$val\""
		return
	fi
	# check for whole-element match using separators to avoid substrings
	case "${sep}${cur}${sep}" in
		*"${sep}${val}${sep}"*)
			# already present
			return
			;;
	esac
	# append with separator
	eval "export $varname=\"${cur}${sep}${val}\""
}

# ensure the pipe dir is bound (use comma separator for APPTAINER_BIND)
add_path_unique APPTAINER_BIND "$CALL_HOST_DIR" ","

# enable/disable toggles
call_host_enable(){
	export CALL_HOST_STATUS=enable
}
export_func call_host_enable
call_host_disable(){
	export CALL_HOST_STATUS=disable
}
export_func call_host_disable
# single toggle for debug printouts
call_host_debug(){
	if [ "$CALL_HOST_DEBUG" = "enable" ]; then
		export CALL_HOST_DEBUG=disable
	else
		export CALL_HOST_DEBUG=enable
	fi
}
export_func call_host_debug
# helper for debug printouts
call_host_debug_print(){
	if [ "$CALL_HOST_DEBUG" = "enable" ]; then
		echo "$@"
	fi
}
export_func call_host_debug_print

call_host_plugin_01(){
	# provide htcondor-specific info in container
	# portable associative-array declaration
	declare_assoc CONDOR_OS
	CONDOR_OS[7]="SL7"
	CONDOR_OS[8]="EL8"
	CONDOR_OS[9]="EL9"

	# todo: only activate if function name (call_host args) includes condor?
	if [[ "$(uname -a)" == *cms*.fnal.gov* ]]; then
		OS_VERSION=$(sed -nr 's/[^0-9]*([0-9]+).*/\1/p' /etc/redhat-release 2>&1)
		CONDOR_OS_VAL="${CONDOR_OS[$OS_VERSION]}"
		if [ -n "$CONDOR_OS_VAL" ]; then
			echo "export FERMIHTC_OS_OVERRIDE=$CONDOR_OS_VAL;"
		else
			call_host_debug_print "echo \"could not determine condor OS from $OS_VERSION\";"
		fi
	fi
}
export_func call_host_plugin_01

# concept based on https://stackoverflow.com/questions/32163955/how-to-run-shell-script-on-host-from-docker-container

# execute command sent to host pipe; send output to container pipe; store exit code
listenhost(){
	# stop when host pipe is removed
	while [ -e "$1" ]; do
		# "|| true" is necessary to stop "Interrupted system call" when running commands like 'command1; command2; command3'
		# now replaced with assignment of exit code to local variable (which also returns true)
		# using { bash -c ... } >& is less fragile than eval
		tmpexit=0
		cmd="$(cat "$1")"
		call_host_debug_print "cmd: $cmd"
		{
			bash -c "$cmd" || tmpexit=$?
		} >& "$2"
		echo "$tmpexit" > "$3"
	done
}
export_func listenhost

# creates randomly named pipe and prints the name
makepipe(){
	PREFIX="$1"
	PIPETMP=${CALL_HOST_DIR}/${PREFIX}_$(uuidgen)
	mkfifo "$PIPETMP"
	echo "$PIPETMP"
}
export_func makepipe

# to be run on host before launching each apptainer session
startpipe(){
	HOSTPIPE=$(makepipe HOST)
	CONTPIPE=$(makepipe CONT)
	EXITPIPE=$(makepipe EXIT)
	# export pipes to apptainer
	echo "export APPTAINERENV_HOSTPIPE=$HOSTPIPE; export APPTAINERENV_CONTPIPE=$CONTPIPE; export APPTAINERENV_EXITPIPE=$EXITPIPE"
}
export_func startpipe

# sends function to host, then listens for output, and provides exit code from function
call_host(){
	# disable ctrl+c to prevent "Interrupted system call"
	trap "" SIGINT

	# determine caller function name in a portable way
	CURFN="$(current_funcname)"
	if [ "$CURFN" = "call_host" ] || [ -z "$CURFN" ]; then
		FUNCTMP=
	else
		FUNCTMP="$CURFN"
	fi

	# extra environment settings; set every time because commands are executed on host in subshell
	# todo: evolve into full plugin system that executes detected functions/executables in order (like config.d)
	EXTRA="$(call_host_plugin_01)"

	echo "cd $PWD; $EXTRA $FUNCTMP $*" > "$HOSTPIPE"
	cat < "$CONTPIPE"
	return "$(cat < "$EXITPIPE")"
}
export_func call_host

# from https://stackoverflow.com/questions/1203583/how-do-i-rename-a-bash-function
copy_function() {
	# portable retrieval of function source and re-definition under a new name
	fnsrc="$(get_function "$1")"
	if [ -z "$fnsrc" ]; then
		return
	fi
	# replace only the first occurrence of the function name (at definition)
	# Use a more portable sed pattern without \b
	fnnew="$(printf '%s\n' "$fnsrc" | sed "1s/^$1 /$2 /; 1s/^$1()/$2()/")"
	eval "$fnnew"
	export_func "$2"
}
export_func copy_function

if [ -z "$APPTAINER_ORIG" ]; then
	export APPTAINER_ORIG=$(which apptainer)
fi
# always set this (in case of nested containers)
export APPTAINERENV_APPTAINER_ORIG=$APPTAINER_ORIG

apptainer(){
	if [ "$CALL_HOST_STATUS" = "disable" ]; then
		(
		# shellcheck disable=SC2030
		export APPTAINERENV_CALL_HOST_STATUS=disable
		$APPTAINER_ORIG "$@"
		)
	else
		# in subshell to contain exports
		(
		# shellcheck disable=SC2031
		export APPTAINERENV_CALL_HOST_STATUS=enable
		# only start pipes on host
		# i.e. don't create more pipes/listeners for nested containers
		if [ -z "$APPTAINER_CONTAINER" ]; then
			eval "$(startpipe)"
			listenhost "$APPTAINERENV_HOSTPIPE" "$APPTAINERENV_CONTPIPE" "$APPTAINERENV_EXITPIPE" &
			LISTENER=$!
		fi
		# actually run apptainer
		$APPTAINER_ORIG "$@"
		# avoid dangling cat process after exiting container
		# (again, only on host)
		if [ -z "$APPTAINER_CONTAINER" ]; then
			pkill -P "$LISTENER"
			rm -f "$APPTAINERENV_HOSTPIPE" "$APPTAINERENV_CONTPIPE" "$APPTAINERENV_EXITPIPE"
		fi
		)
	fi
}
export_func apptainer

# on host: get list of condor executables
if [ -z "$APPTAINER_CONTAINER" ]; then
	# define command prefixes to search for
	HOSTFN_PREFIXES="condor_ eos"

	# portable command list discovery:
	if command -v compgen >/dev/null 2>&1; then
		# bash: use compgen with grep pattern built from prefixes
		GREP_PATTERN="$(echo "$HOSTFN_PREFIXES" | sed 's/ /\\|^/g' | sed 's/^/^/')"
		export APPTAINERENV_HOSTFNS=$(compgen -c | grep -E "$GREP_PATTERN" | tr '\n' ' ')
	else
		# fallback: scan PATH for matching executables (portable)
		APPTAINERENV_HOSTFNS="$( ( IFS=:
		for d in $PATH; do
			[ -d "$d" ] || continue
			for prefix in $HOSTFN_PREFIXES; do
				# shellcheck disable=SC2231
				for f in "$d"/${prefix}*; do
					[ -e "$f" ] && [ -x "$f" ] && basename "$f"
				done
			done
		done ) | sort -u | tr '\n' ' ')"
		export APPTAINERENV_HOSTFNS
	fi

	if [ -n "$CALL_HOST_USERFNS" ]; then
		export APPTAINERENV_HOSTFNS="$APPTAINERENV_HOSTFNS $CALL_HOST_USERFNS"
	fi
# in container: replace with call_host versions
elif [ "$CALL_HOST_STATUS" = "enable" ]; then
	# shellcheck disable=SC2153
	for HOSTFN in $HOSTFNS; do
		copy_function call_host "$HOSTFN"
	done
fi
