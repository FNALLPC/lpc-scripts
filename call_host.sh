#!/bin/bash
# shellcheck disable=SC2155,SC2223

# check for configuration
CALL_HOST_CONFIG=~/.callhostrc
if [ -f "$CALL_HOST_CONFIG" ]; then
	# shellcheck source=/dev/null
	source "$CALL_HOST_CONFIG"
fi

# portable indirect variable access (works in both bash and zsh)
getvar(){
	eval "printf '%s' \"\${$1:-}\""
}

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
	export_func getvar
	declare_assoc(){
		# create named associative array in bash
		declare -gA "$1"
	}
    export_func declare_assoc
	current_funcname(){
		# return the caller function name if available (FUNCNAME[1]), otherwise fall back to FUNCNAME[0]
		if [ -n "${FUNCNAME[1]:-}" ]; then
			echo "${FUNCNAME[1]}"
		else
			echo "${FUNCNAME[0]:-}"
		fi
	}
    export_func current_funcname
	# get function definition (bash)
	get_function(){
		declare -f "$1" 2>/dev/null
	}
    export_func get_function
fi

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

# python helper that runs a command on the host under a pseudo-terminal (pty).
# This makes isatty() true for the host command (so full-screen tty programs like
# nano or emacs -nw work) and, crucially, routes the container terminal's control
# characters (e.g. ctrl+c -> 0x03) through the pty line discipline, which turns
# them into real signals (SIGINT) for the host command. python3 is used because it
# is present on essentially all interactive nodes and, unlike `script`, its pty
# correctly converts control bytes into signals. Stored as a string and executed
# via `python3 -c` so no temporary files need to be managed.
# shellcheck disable=SC2016
read -r -d '' CALL_HOST_PTY_PY <<'CALL_HOST_PTY_PY_EOF'
import os, sys, pty, select, termios, struct, fcntl, signal
cmd  = sys.argv[1] if len(sys.argv) > 1 else ""
rows = int(sys.argv[2]) if len(sys.argv) > 2 else 24
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 80
# the bridge itself must survive a stray INT/QUIT; only the child should receive them
signal.signal(signal.SIGINT,  signal.SIG_IGN)
signal.signal(signal.SIGQUIT, signal.SIG_IGN)
pid, fd = pty.fork()
if pid == 0:
    signal.signal(signal.SIGINT,  signal.SIG_DFL)
    signal.signal(signal.SIGQUIT, signal.SIG_DFL)
    os.execv("/bin/bash", ["/bin/bash", "-c", cmd])
    os._exit(127)
try:
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
except Exception:
    pass
# Disable the pty's suspend character (ctrl+z). We cannot honour job-control
# suspension here -- there is no interactive shell on this side to background the
# job to -- and a stopped host command would hang this bridge and be orphaned when
# the container exits. Disabling VSUSP makes ctrl+z a harmless passthrough byte.
try:
    attr = termios.tcgetattr(fd)
    attr[6][termios.VSUSP] = b'\x00'
    termios.tcsetattr(fd, termios.TCSANOW, attr)
except Exception:
    pass
fds = [fd, 0]
while True:
    try:
        r, _, _ = select.select(fds, [], [])
    except (OSError, select.error):
        continue
    if fd in r:
        try: data = os.read(fd, 65536)
        except OSError: data = b""
        if not data:
            break
        try: os.write(1, data)
        except OSError: break
    if 0 in r:
        try: data = os.read(0, 65536)
        except OSError: data = b""
        if not data:
            fds = [fd]            # stdin closed: stop polling it to avoid a busy loop
            continue
        try: os.write(fd, data)
        except OSError: break
_, status = os.waitpid(pid, 0)
if os.WIFEXITED(status):
    sys.exit(os.WEXITSTATUS(status))
if os.WIFSIGNALED(status):
    sys.exit(128 + os.WTERMSIG(status))
sys.exit(0)
CALL_HOST_PTY_PY_EOF
export CALL_HOST_PTY_PY
# tty mode is available if the host can allocate a pty for the command, i.e. it has
# either python3 (preferred) or script. Exported so the in-container call_host knows
# whether to request a pty.
if command -v python3 >/dev/null 2>&1 || command -v script >/dev/null 2>&1; then
	export APPTAINERENV_CALL_HOST_PTY_AVAIL=1
else
	export APPTAINERENV_CALL_HOST_PTY_AVAIL=0
fi

# A signal that is ignored (SIG_IGN) at the moment a program is exec'd cannot be
# reset by that program (POSIX). The listener must ignore SIGINT/SIGQUIT to keep
# its loop alive, and bash additionally forces SIG_IGN for SIGINT/SIGQUIT on any
# command started asynchronously (with &). Either way the host command would
# inherit "ignore" and could not be interrupted by a forwarded ctrl+c. To work
# around this we launch the (non-pty) host command through a small wrapper that
# resets those signals to their default disposition before running it. Prefer GNU
# coreutils' "env --default-signal" (fast, no extra process); fall back to a small
# python launcher (resets the handlers, then exec's, so no python stays resident).
# CALL_HOST_SIGDFL_MODE selects which mechanism run_on_host uses.
if env --default-signal=INT,QUIT true >/dev/null 2>&1; then
	CALL_HOST_SIGDFL_MODE="env"
elif command -v python3 >/dev/null 2>&1; then
	CALL_HOST_SIGDFL_MODE="python"
else
	CALL_HOST_SIGDFL_MODE="none"
fi
# kept free of newlines so it can be passed as a single argument
CALL_HOST_SIGDFL_PY='import os,sys,signal; signal.signal(signal.SIGINT,signal.SIG_DFL); signal.signal(signal.SIGQUIT,signal.SIG_DFL); os.execvp(sys.argv[1],sys.argv[1:])'
export CALL_HOST_SIGDFL_MODE CALL_HOST_SIGDFL_PY

# run a single command on the host, wiring up stdin, stdout/stderr, and signals.
# args: command want_tty rows cols inpipe contpipe sigpipe
# returns the command's exit status.
run_on_host(){
	local cmd="$1" want_tty="$2" rows="$3" cols="$4" inp="$5" cp="$6" sp="$7"
	local child sigfwd rc=0
	# launch in a new session (setsid) so the command gets its own process group;
	# this lets us deliver signals to the command (and its children) without
	# affecting the listener itself.
	if [ "$want_tty" = "1" ] && command -v python3 >/dev/null 2>&1; then
		setsid python3 -c "$CALL_HOST_PTY_PY" "$cmd" "$rows" "$cols" <"$inp" >"$cp" 2>&1 &
	elif [ "$want_tty" = "1" ] && command -v script >/dev/null 2>&1; then
		# fallback: `script` provides a pty (tty programs work) but does not convert
		# control bytes to signals, so ctrl+c relies on the signal pipe below.
		setsid script -qfec "stty rows ${rows:-24} cols ${cols:-80} 2>/dev/null; $cmd" /dev/null <"$inp" >"$cp" 2>&1 &
	else
		# Non-pty command. Reset the inherited "ignore" disposition for SIGINT/SIGQUIT
		# (see CALL_HOST_SIGDFL_MODE above) so a forwarded ctrl+c can interrupt it.
		case "$CALL_HOST_SIGDFL_MODE" in
			env)
				setsid env --default-signal=INT,QUIT bash -c "$cmd" <"$inp" >"$cp" 2>&1 &
				;;
			python)
				setsid python3 -c "$CALL_HOST_SIGDFL_PY" bash -c "$cmd" <"$inp" >"$cp" 2>&1 &
				;;
			*)
				# no reset mechanism available: ctrl+c forwarding may not interrupt,
				# but the command still runs correctly
				setsid bash -c "$cmd" <"$inp" >"$cp" 2>&1 &
				;;
		esac
	fi
	child=$!
	# The command runs in its own session/process group (setsid above), which is
	# necessary for targeted signal delivery but means it is NOT in the listener's
	# process group -- so the container-exit cleanup (which kills the listener's
	# group) would not reach a command that is still running (e.g. the user exits
	# the container mid-command). Guard against that: if this runner is terminated
	# (it IS in the listener's group), kill the command's whole process group first.
	trap 'kill -TERM -- -"$child" 2>/dev/null; kill -KILL -- -"$child" 2>/dev/null; exit 143' TERM HUP
	# forward signals received on the signal pipe to the command's process group.
	# This is how a ctrl+c from a non-tty container session interrupts the host
	# command. The loop exits once the command is gone.
	(
		trap "" SIGINT SIGQUIT
		while kill -0 "$child" 2>/dev/null; do
			IFS= read -r sig <"$sp" || break
			[ -n "$sig" ] && kill -"$sig" -- -"$child" 2>/dev/null
		done
	) &
	sigfwd=$!
	wait "$child"; rc=$?
	trap - TERM HUP
	# tear down the signal forwarder (and unblock its read on the pipe)
	kill "$sigfwd" 2>/dev/null
	echo "" > "$sp" 2>/dev/null &
	wait "$sigfwd" 2>/dev/null
	return "$rc"
}
export_func run_on_host

# execute command sent to host pipe; send output to container pipe; store exit code
# args: hostpipe contpipe exitpipe inpipe sigpipe
listenhost(){
	local hp="$1" cp="$2" ep="$3" inp="$4" sp="$5"
	# make the listener immune to signals that could otherwise break the loop and
	# leave the terminal hung ("Interrupted system call"); the command itself is
	# signalled explicitly via run_on_host instead.
	trap "" SIGINT SIGQUIT SIGPIPE
	# stop when host pipe is removed
	while [ -e "$hp" ]; do
		local payload header cmd want_tty rows cols tmpexit=0 tok
		# read one request; ignore spurious empty reads (e.g. writer reopened pipe)
		payload="$(cat "$hp")" || continue
		[ -z "$payload" ] && continue
		# the first line is a header describing the request; the rest is the command
		header="$(printf '%s\n' "$payload" | head -n 1)"
		want_tty=0; rows=24; cols=80
		case "$header" in
			CALL_HOST_HDR*)
				cmd="$(printf '%s\n' "$payload" | tail -n +2)"
				for tok in $header; do
					case "$tok" in
						TTY=*)  want_tty="${tok#TTY=}" ;;
						ROWS=*) rows="${tok#ROWS=}" ;;
						COLS=*) cols="${tok#COLS=}" ;;
					esac
				done
				;;
			*)
				# backward compatibility: no header, whole payload is the command
				cmd="$payload"
				;;
		esac
		call_host_debug_print "cmd: $cmd (tty=$want_tty)"
		run_on_host "$cmd" "$want_tty" "$rows" "$cols" "$inp" "$cp" "$sp" || tmpexit=$?
		echo "$tmpexit" > "$ep"
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
	# INPIPE carries the container's stdin to the host command;
	# SIGPIPE carries signals (e.g. INT from ctrl+c) to the host command.
	INPIPE=$(makepipe IN)
	SIGPIPE=$(makepipe SIG)
	# export pipes to apptainer
	echo "export APPTAINERENV_HOSTPIPE=$HOSTPIPE; export APPTAINERENV_CONTPIPE=$CONTPIPE; export APPTAINERENV_EXITPIPE=$EXITPIPE; export APPTAINERENV_INPIPE=$INPIPE; export APPTAINERENV_SIGPIPE=$SIGPIPE"
}
export_func startpipe

# sends function to host, then listens for output, and provides exit code from function
call_host(){
	if [ "$CALL_HOST_STATUS" != "enable" ]; then
		echo "call_host is disabled"
		return 1
	elif [ -z "$HOSTPIPE" ] || [ -z "$CONTPIPE" ] || [ -z "$EXITPIPE" ]; then
		echo "call_host pipes are missing"
		return 1
	fi

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

	# decide whether to request a pty on the host: only useful (and only correct)
	# when both our stdin and stdout are terminals, i.e. a genuinely interactive
	# call. In that case the host command gets a real tty (so editors etc. work)
	# and the pty converts our ctrl+c into a SIGINT for the host command.
	CALL_HOST_TTY=0
	CALL_HOST_ROWS=24
	CALL_HOST_COLS=80
	if [ -t 0 ] && [ -t 1 ] && [ "$APPTAINERENV_CALL_HOST_PTY_AVAIL" = "1" ]; then
		CALL_HOST_TTY=1
		CALL_HOST_SIZE="$(stty size 2>/dev/null)"
		if [ -n "$CALL_HOST_SIZE" ]; then
			CALL_HOST_ROWS="${CALL_HOST_SIZE%% *}"
			CALL_HOST_COLS="${CALL_HOST_SIZE##* }"
		fi
	fi

	# Build the request: a header line (parsed by the host listener) followed by
	# the actual command. The header is ignored by older host-side scripts.
	{
		printf 'CALL_HOST_HDR TTY=%s ROWS=%s COLS=%s\n' "$CALL_HOST_TTY" "$CALL_HOST_ROWS" "$CALL_HOST_COLS"
		printf 'cd %s; %s %s %s\n' "$PWD" "$EXTRA" "$FUNCTMP" "$*"
	} > "$HOSTPIPE"

	CALL_HOST_INCAT=
	CALL_HOST_OUTCAT=
	if [ "$CALL_HOST_TTY" = "1" ]; then
		# Interactive path. Put our terminal in raw mode so every keystroke
		# (including ctrl+c as a raw 0x03 byte) passes straight through to the host
		# pty unmodified; the host pty's line discipline then turns ctrl+c into a
		# real SIGINT for the host command. The output reader runs in the background
		# while we forward stdin in the foreground, so the two never compete for the
		# terminal. When the command ends the host closes CONTPIPE, the background
		# reader exits, and we stop forwarding input.
		CALL_HOST_STTY_SAVED="$(stty -g 2>/dev/null)"
		stty raw -echo 2>/dev/null
		# Run both helper readers inside one outer subshell. Two reasons:
		#  1. Job control does not apply to commands started inside a subshell, so the
		#     interactive shell never prints "[1] <pid>" / "Terminated" notices (which
		#     would corrupt the display of full-screen programs like nano).
		#  2. The subshell inherits our real terminal (fd 0/1), and because it is not
		#     interactive its background readers are not sent SIGTTIN when they read
		#     the terminal (which would otherwise stop the stdin forwarder).
		# The subshell returns when the host closes CONTPIPE, i.e. when the command
		# finishes; the stdin forwarder is then stopped.
		(
			cat < "$CONTPIPE" &
			CALL_HOST_OUT=$!
			( cat > "$INPIPE" 2>/dev/null ) <&0 &
			CALL_HOST_IN=$!
			wait "$CALL_HOST_OUT" 2>/dev/null
			kill "$CALL_HOST_IN" 2>/dev/null
		)
		[ -n "$CALL_HOST_STTY_SAVED" ] && stty "$CALL_HOST_STTY_SAVED" 2>/dev/null
	else
		# Non-interactive path. Forward our stdin to the host command in the
		# background. A background command in a non-interactive shell has its stdin
		# silently redirected from /dev/null (POSIX async behavior), so we duplicate
		# our real stdin onto fd 3 and read from that explicit descriptor instead.
		if [ -n "$INPIPE" ]; then
			exec 3<&0
			( cat <&3 > "$INPIPE" 2>/dev/null ) &
			CALL_HOST_INCAT=$!
			exec 3<&-
		fi
		# Catch ctrl+c locally and forward it as a SIGINT to the host command via
		# SIGPIPE, instead of letting it tear down this function (which previously
		# could break the pipe / hang the session). The output read is backgrounded
		# and waited on so the trap is delivered promptly.
		if [ -n "$SIGPIPE" ]; then
			trap 'printf "INT\n" > "$SIGPIPE" 2>/dev/null &' SIGINT
		else
			# no signal pipe: fall back to old behavior of ignoring ctrl+c
			trap "" SIGINT
		fi
		cat < "$CONTPIPE" &
		CALL_HOST_OUTCAT=$!
		while true; do
			wait "$CALL_HOST_OUTCAT"; CALL_HOST_WRC=$?
			# a return >128 means wait was interrupted by a signal (the trap ran);
			# keep waiting for the host command to actually finish and close CONTPIPE.
			[ "$CALL_HOST_WRC" -le 128 ] && break
		done
		trap - SIGINT
	fi

	# stop forwarding stdin (wait reaps the process quietly, avoiding a stray
	# "Terminated" job-control message)
	if [ -n "$CALL_HOST_INCAT" ]; then
		kill "$CALL_HOST_INCAT" 2>/dev/null
		wait "$CALL_HOST_INCAT" 2>/dev/null
	fi

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
			# Start the listener in its own new session/process group (setsid) and
			# detached from this shell's stdio. Two reasons:
			#  1. The listener communicates only through the explicit pipes, so it must
			#     never hold the user's terminal/stdout open (otherwise a pipeline like
			#     "... | tail" would never see EOF after the container exits).
			#  2. Its own process group lets us signal the whole subtree at cleanup.
			#     The listener reads each request with "$(cat "$hp")", which forks a
			#     subshell that forks cat; killing only the listener (or its direct
			#     children) would leave that cat grandchild blocked on the fifo and
			#     reparented to init. Killing the process group reaps all of them.
			setsid bash -c 'listenhost "$@"' _ "$APPTAINERENV_HOSTPIPE" "$APPTAINERENV_CONTPIPE" "$APPTAINERENV_EXITPIPE" "$APPTAINERENV_INPIPE" "$APPTAINERENV_SIGPIPE" </dev/null >/dev/null 2>&1 &
			LISTENER=$!
		fi
		# actually run apptainer
		$APPTAINER_ORIG "$@"
		# avoid dangling cat process after exiting container
		# (again, only on host)
		if [ -z "$APPTAINER_CONTAINER" ]; then
			# Tear down the listener and every descendant (the blocked "cat" reader,
			# signal forwarders, detached command runners) by signalling its whole
			# process group. setsid above made LISTENER the group leader, so its pgid
			# equals its pid, and a negative pid signals the entire group. This is
			# both necessary (the "cat" reader is a grandchild that a plain kill would
			# orphan) and sufficient, so we deliberately avoid pkill -P / kill on the
			# bare pid, which could hit an unrelated process if the pid were reused.
			kill -- -"$LISTENER" 2>/dev/null
			rm -f "$APPTAINERENV_HOSTPIPE" "$APPTAINERENV_CONTPIPE" "$APPTAINERENV_EXITPIPE" "$APPTAINERENV_INPIPE" "$APPTAINERENV_SIGPIPE"
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
		GREP_PATTERN="$(echo "$HOSTFN_PREFIXES" | sed 's/ /|^/g' | sed 's/^/^/')"
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
