#!/usr/bin/env python3

"""The purpose of this module is to recursively copy the files from one WLCG connected grid endpoint to onther.
That said, the endpoints need not be grid connected, they can also be a local directory. Based on some minimal
information provided by the user, the module will look up the needed information about the endpoints from
the GetSiteInfo module.

The reason this module is necessary is because the recursive option for 'xrdcp' does not work reliably. This
module is intended to replace 'xrdcp -r'. That said, it has a lot more features, which can also act as an
improvement over 'xrdcp', like the ability to use 'gsiftp' information for the endpoints.
"""

from __future__ import absolute_import
import argparse
import fnmatch
import os
import shlex
import subprocess
import sys
import GetSiteInfo

class Command:
    """This is the base class used for building up the copy/ls/mkdir commands."""
    def __init__(self, *, start_site = None, end_site = None, verbose = False, additional_arguments = "", override_path = ""):
        self.start_site = start_site
        self.end_site = end_site
        self.verbose = verbose
        self.additional_arguments = additional_arguments
        self.override_path = override_path
        self.command_pieces = []

    def get_command(self, start = None, end = None, pos = None, delim=' '):
        """Return a string with the joined command pieces.
        The user can specify a range of pieces to join or a single piece to return.
        The separator between the pieces can also be specified.
        """
        command_slice = self.command_pieces[start:end]
        return delim.join(command_slice) if pos is None else command_slice[pos]

    def get_full_command(self):
        """An alias to returning the fully joined, space separated command."""
        return self.get_command()

    def get_command_and_arguments(self):
        """An alias to returning the just the executable and argument portion of the command,
        space separated.
        """
        return self.get_command(end = -3)

    def get_start_location(self):
        """An alias to returning just the formated start site location."""
        return self.get_command(pos = -2)

    def get_end_location(self):
        """An alias to returning just the formated end site location."""
        return self.get_command(pos = -1)

class GfalCommand(Command):
    """Creates and stores a GFAL based command"""
    def __init__(self, *, action, recursive = False, dry_run = False, **kwargs):
        super().__init__(**kwargs)
        self.base_command = "gfal-"
        self.action = action
        self.recursive = recursive
        self.dry_run = dry_run
        self.start_site_prefix = self.get_site_prefix(self.start_site) if self.start_site is not None else ""
        self.end_site_prefix = self.get_site_prefix(self.end_site) if self.end_site is not None else ""
        self.build_command()

    # pylint: disable=no-self-use
    def get_site_prefix(self, site):
        """Return the formatted site path, including the protcol to use, the endpoint,
        and the initial portion of the path, through the username.
        """
        if site.alias == 'local':
            return "file:////"
        elif site.gsiftp_endpoint != 'None':
            return "gsiftp://" + site.gsiftp_endpoint + "/store/user/" + site.username + "/"
        elif site.xrootd_endpoint != 'None':
            return "root://" + site.xrootd_endpoint + "//store/user/" + site.username + "/"
        else:
            site.print_site_info(fast = True)
            raise RuntimeError(f"The site {site.alias} must be 'local' or have either a gsiftp or xrootd endpoint.")

    def build_command(self):
        """Build the list of command pieces based on the previously set options."""
        self.command_pieces = [self.base_command + self.action]
        if self.verbose:
            self.command_pieces.append("-vvv")
        if self.recursive:
            self.command_pieces.append("-r")
        if self.dry_run:
            self.command_pieces.append("--dry-run")
        if self.additional_arguments != "":
            self.command_pieces.append(self.additional_arguments)
        self.command_pieces.append((self.start_site_prefix +
                                    (self.override_path if self.override_path != "" else self.start_site.path) +
                                    "/") if self.start_site is not None else "")
        self.command_pieces.append((self.end_site_prefix +
                                    (self.override_path if self.override_path != "" else self.end_site.path) +
                                    "/") if self.end_site is not None else "")

class XRootDCommand(Command):
    """Creates and stores a GFAL based command"""
    def __init__(self, *, action, subaction = "", quiet = False, **kwargs):
        super().__init__(**kwargs)
        self.base_command = "xrd"
        self.action = action
        self.subaction = subaction
        self.quiet = quiet
        self.start_site_prefix = self.get_site_prefix(self.start_site)
        self.end_site_prefix = self.get_site_prefix(self.end_site)
        self.build_command()

    def get_site_prefix(self, site):
        """Return the formatted site path, including the protcol to use, the action to perform, the endpoint,
        and the initial portion of the path, through the username.
        """
        if site.alias == 'local':
            return ""
        elif site.xrootd_endpoint != 'None':
            if self.subaction != "":
                return "root://" + site.xrootd_endpoint + "/ " + self.subaction + "/store/user/" + site.username + "/"
            else:
                return "root://" + site.xrootd_endpoint + "//store/user/" + site.username + "/"
        else:
            site.print_site_info(fast = True)
            raise RuntimeError(f"The site {site.alias} must be 'local' or have an xrootd endpoint.")

    def build_command(self):
        """Build the list of command pieces based on the previously set options."""
        self.command_pieces = [self.base_command + self.action]
        if self.verbose:
            self.command_pieces.append("-v")
        if self.quiet:
            self.command_pieces.append("-s")
        if self.additional_arguments != "":
            self.command_pieces.append(self.additional_arguments)
        self.command_pieces.append((self.start_site_prefix +
                                    (self.override_path if self.override_path != "" else self.start_site.path) +
                                    "/") if self.start_site is not None else "")
        self.command_pieces.append((self.end_site_prefix +
                                    (self.override_path if self.override_path != "" else self.end_site.path) +
                                    "/") if self.end_site is not None else "")

class Error(EnvironmentError):
    """EnvironmentError is the base class for errors that come from outside of Python (the operating system,
    file system, etc.). It is the parent class for IOError and OSError exceptions.
    See https://www.programiz.com/python-programming/user-defined-exception for reference.
    """
    #pylint: disable=unnecessary-pass
    pass

class Location(GetSiteInfo.Site):
    """Class for storing site, user, and path information.
    This is a derived class, with the Site class from GetSiteInfo
    being the base class.
    """
    def __init__(self, alias, username, path):
        super().__init__(alias)
        self.username = username
        self.path = path

    def print_location_info(self,fast):
        """Print the Site and Location information to STDOUT."""
        print(super().__str__(fast))
        print("\tusername:", self.username)
        print("\tPath:", self.path)

def run_checks(recursive, depth, start_path, end_path):
    """Does some basic sanity checks before proceeding with the rest of the module.
    This tries to head off problems that might occur later on.
    The checks include:
    1. Checking for option clashing having to do with the recursive option.
    2. Checking that the start and end paths are formatted appropriately.
    3. Making sure the user has a valid grid proxy.
    """
    print("Running checks on options ...")

    if recursive :
        print("\trun_checks::recursive option chosen so depth set to large value (9999)")
        depth = 9999

    with open(os.devnull, 'wb') as devnull:
        returncode = 0
        with subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'),
                              stdout=devnull,
                              stderr=subprocess.STDOUT) as process:
            returncode = process.wait()
        if returncode != 0:
            print("\tWARNING::You must have a valid proxy for this script to work.\nRunning \"voms-proxy-init -voms cms\"...\n")
            subprocess.call("voms-proxy-init -voms cms -valid 192:00", shell=True)
            with subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'),
                                  stdout=devnull,
                                  stderr=subprocess.STDOUT) as process:
                returncode = process.wait()
            if returncode != 0 :
                print("\tERROR::Sorry, but I still could not find your proxy.\n"
                      "Without a valid proxy, this program will fail spectacularly.\n"
                      "The program will now exit.")
                sys.exit(1)

    if start_path=="./":
        print("\trun_checks::start_path chosen as the current working directory ("+str(os.environ['PWD'])+")")
        start_path=os.environ['PWD']
    if end_path=="./":
        end_path=""

    print()
    return (recursive, depth, start_path, end_path)

def init_commands(start_site, end_site, arguments = argparse.Namespace()):
    """This function makes sure that the beginning parts of the start and end paths are formmated appropriately."""
    if arguments.debug:
        print("copyfiles::init_commands() initializing the start and end commands based on the chosen protocol (" +
              str(arguments.protocol) + ")")

    command = None

    if arguments.protocol == "gfal":
        command = GfalCommand(action = "copy",
                              recursive = arguments.recursive,
                              dry_run = arguments.dry_run,
                              start_site = start_site,
                              end_site = end_site,
                              verbose = arguments.verbose,
                              additional_arguments = arguments.additional)
    elif arguments.protocol == "xrootd":
        command = XRootDCommand(action = "cp",
                                quiet = arguments.quiet,
                                start_site = start_site,
                                end_site = end_site,
                                verbose = arguments.verbose,
                                additional_arguments = arguments.additional)
    else:
        raise RuntimeError("copyfiles::init_commands() could not figure out how to format the copy command.")

    copy_command = command.get_command_and_arguments()
    start_location = command.get_start_location()
    end_location = command.get_end_location()

    if arguments.debug:
        print("\tcopy_command:", copy_command)
        print("\tstart_location:", start_location)
        print("\tend_location:", end_location)

    return (copy_command, start_location, end_location)


def make_directory(end_site, path, protocol, debug = False):
    """This function will create a directory on a remote file system (the endpoint) assuming it is missing."""
    made_dir = False

    if end_site.alias == 'local' :
        if not os.path.exists(path) :
            os.makedirs(path)
            made_dir = True
    else:
        ls_command = None
        if protocol == "gfal":
            ls_command = GfalCommand(action = "ls",
                                     verbose = True,
                                     end_site = end_site,
                                     override_path = path)
        elif protocol == "xrootd":
            ls_command = XRootDCommand(action = "fs",
                                       subaction = "ls",
                                       end_site = end_site,
                                       override_path = path)

        if os.system(ls_command.get_full_command()) != 0 and protocol == "gfal":
            mkdir_command = GfalCommand(action = "mkdir",
                                        end_site = end_site,
                                        override_path = path)
            cmd = mkdir_command.get_full_command()
            print("\tcmd:", cmd)
            os.system(cmd)
            made_dir = True
        elif os.system(ls_command.get_full_command()) != 0 and protocol == "xrootd":
            mkdir_command = XRootDCommand(action = "fs",
                                          subaction = "mkdir",
                                          end_site = end_site,
                                          override_path = path)
            cmd = mkdir_command.get_full_command()
            print("\tcmd:", cmd)
            os.system(cmd)
            made_dir = True

    if not made_dir:
        print("make_directory:")
        print("\tThere was a problem making the directory", path)
        print("\tEither the destination directory already exists or the make_directory command is broken")
    elif debug:
        print("make_directory:")
        print("\tstatus: success")
        print("\tdirectory:", path)
        print("\tprotocol:", protocol)

def get_list_of_files(protocol, start_site, sample, path, debug = False):
    """This function will return a list of file from the start site."""
    files_unfiltered = []
    if start_site.alias == 'local':
        if os.path.isfile(path):
            return [os.path.basename(path)]
        else:
            files_unfiltered = os.listdir(path)
        if debug:
            print("get_list_of_files:")
            print("\tList of files (unfiltered):", files_unfiltered)
    else:
        if protocol == "gfal":
            ls_command = GfalCommand(action = "ls",
                                     start_site = start_site,
                                     override_path = path)
        elif protocol == "xrootd":
            ls_command = XRootDCommand(action = "fs",
                                       subaction = "ls",
                                       start_site = start_site,
                                       override_path = path)
        cmd = ls_command.get_full_command()
        if debug:
            print("get_list_of_files:")
            print("\tCommand: ", cmd)

        # pylint: disable=consider-using-with
        proc = subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE).communicate()[0]
        files_unfiltered = proc.splitlines()
        files_unfiltered = [x.strip(' ') for x in files_unfiltered]
        files_unfiltered = [x.strip('\n') for x in files_unfiltered]
    files_unfiltered = [x.replace("//", "/") for x in files_unfiltered]
    files_unfiltered = [x.split(' ', 1)[0] if x.split(' ', 1)[0].isdigit() else x for x in files_unfiltered]
    if protocol == 'xrootd':
        files_unfiltered = [x.replace(x[:x.rfind("/") + 1], "") for x in files_unfiltered]
    files_unfiltered = [x for x in files_unfiltered if x != '']
    files_unfiltered = [x for x in files_unfiltered if x != path.replace("//", "/")]
    files_unfiltered = [x for x in files_unfiltered if x != path[path.find(start_site.path) + len(start_site.path):]]
    files_unfiltered = [x.split("/")[-1] if x[-1] != "/" else x.split("/")[-2] + "/" for x in files_unfiltered]
    files = []
    for thesample in sample:
        files += fnmatch.filter(files_unfiltered, '*' + thesample + '*')
    return files

def filter_list_of_files(sample, files_unfiltered):
    """This function filters the list of files based on a patter, which allows for wildcards."""
    files = []
    if len(sample) == 0:
        sample = ["*"]
    for thesample in sample:
        files += fnmatch.filter(files_unfiltered, '*' + thesample + '*')
    return files

def ignore_patterns(patterns):
    """Function that can be used as copytree() ignore parameter.

    Patterns is a sequence of glob-style patterns
    that are used to exclude files"""
    def _ignore_patterns(path, names):
        ignored_names = []
        for pattern in patterns:
            if len(fnmatch.filter([path],'*'+pattern+'*')) > 0:
                ignored_names.extend(names)
            #names_extended = [os.path.join(path,n) for n in names]
            #ignored_names.extend(fnmatch.filter(names_extended, '*'+pattern+'*'))
            else:
                ignored_names.extend(fnmatch.filter(names, '*'+pattern+'*'))
        return set(ignored_names)
    return _ignore_patterns

def do_diff(files, protocol, end_site, sample, dst, debug):
    """Return a list of files which are located at the start site, but not the end site."""
    if end_site.alias == 'local' and os.environ.get('HOSTNAME',"not found").find("fnal.gov") > 0 :
        files1 = os.listdir(dst)
    else:
        get_list_of_files(protocol, end_site, sample, dst, debug)
    files_diff = [f for f in files if f not in files1 or os.path.isdir(dst + "/" + f)]
    print("Adding an additional " + str(len(files_diff)) + " files/folders")
    return files_diff

def remote_is_dir(start_site,srcname):
    """Return True if the remote path is a directory and False otherwise."""
    returncode = 0
    cmd = "xrdfs root://" + start_site.xrootd_endpoint + "/ stat -q IsDir " + srcname
    with subprocess.Popen(cmd, shell = True, stdout = subprocess.PIPE, stderr = subprocess.STDOUT) as process:
        _ = process.communicate()[0]
        returncode = process.returncode
    return returncode == 0

# pylint: disable=too-many-locals
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
def copytree(start_site, src, end_site, dst, current_depth, symlinks = False, ignore = None, arguments = argparse.Namespace()):
    """Recursively copy a directory (src) to another location (dst)"""
    if arguments.debug:
        print("copytree:")
        print("\tsrc:", src)
        print("\tdst:", dst)
        print("\tdepth:", str(arguments.depth))
        print("\tcurrent_depth:", str(current_depth))
        print("\tsymlinks:", str(symlinks))
        print("\tdry_run:", str(arguments.dry_run))
    if current_depth >= arguments.depth:
        return

    if not arguments.dry_run:
        make_directory(end_site, dst, arguments.protocol, arguments.debug)

    files = get_list_of_files(arguments.protocol, start_site, arguments.sample, src, arguments.debug)

    if arguments.debug:
        print("copytree:")
        print("\tList of files:", files)

    if arguments.diff:
        files = do_diff(files, arguments.protocol, end_site, arguments.sample, dst, arguments.debug)

    if ignore is not None:
        ignored_names = ignore(src, files)
    else:
        ignored_names = set()

    errors = []
    for file in files:
        if file in ignored_names:
            continue
        srcname = os.path.join(src, file)
        dstname = os.path.join(dst, file)

        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto, dstname)
            elif os.path.isdir(srcname) or (arguments.protocol == "xrootd" and remote_is_dir(start_site, srcname)):
                copytree(start_site,
                         srcname,
                         end_site,
                         dstname,
                         current_depth + 1,
                         symlinks,
                         ignore,
                         arguments)
            else:
                srel = os.path.relpath(src, src[:src.find(start_site.path) + len(start_site.path)]) + "/"
                if srel == "./":
                    srel = ""
                copy_command, start_location, end_location = init_commands(start_site, end_site, arguments)
                print("Copying file " + file + " from " + srel)
                command = copy_command + " " + start_location + srel + file + " " + end_location + srel + file
                print(command)
                if not arguments.dry_run:
                    os.system(command)
                print("")

        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error as err:
            errors.extend(err.args[0])
        except EnvironmentError as why:
            errors.append((srcname, dstname, str(why)))
    if errors:
        raise Error(errors)

def local2local(start_site, end_site, recursive, delete, additional):
    """If the program is being used to move from a local directory to another local directory then don't use
    a remote copy protocol. This function will use the POSIX 'mv' and 'cp' commands, depending upon the options
    specified.
    """
    command = 'mv' if delete else 'cp'
    if not delete and recursive:
        command += ' -R'
    command = command + ' ' + additional + ' ' + start_site.path + ' ' + end_site.path
    print(command)
    os.system(command)

def main(arguments = argparse.Namespace()):
    """The main function coordinating the overal logic of which protocols to use, how to get the site/server
    information, and which copy command to use.
    """
    arguments.recursive, arguments.depth, arguments.start_path, arguments.end_path = run_checks(arguments.recursive,
                                                                                                arguments.depth,
                                                                                                arguments.start_path,
                                                                                                arguments.end_path)

    #get the site information
    start_site = Location(arguments.start_server,
                          arguments.start_user,
                          arguments.start_path + "/" if arguments.start_server != 'local' else arguments.start_path)
    if start_site.alias != 'local':
        GetSiteInfo.get_site_info(site = start_site, debug = arguments.debug, fast = True, quiet = True)
    end_site = Location(arguments.end_server,
                        arguments.end_user,
                        arguments.end_path + "/" if arguments.end_server != 'local' else arguments.end_path)
    if end_site.alias != 'local':
        GetSiteInfo.get_site_info(site = end_site, debug = arguments.debug, fast = True, quiet = True)

    #local to local copies can use POSIX commands
    if start_site.alias == 'local' and end_site.alias == 'local':
        local2local(start_site, end_site, arguments.recursive, arguments.delete, arguments.additional)
        return

    #gfal-copy has its own working recursive option, so we can take more advantage of that
    if arguments.protocol=='gfal':
        copy_command, start_location, end_location = init_commands(start_site, end_site, arguments)
        if arguments.from_file != "":
            command = copy_command + " --from-file " + arguments.from_file + " " + end_location
        else:
            command = copy_command + " " + start_location + " " + end_location
        print(command)
        os.system(command)
        return

    #Needed for the xrootd protocol because of the lack of a recursive functionality
    if arguments.protocol == 'xrootd':
        top_src = ""
        if start_site.alias == 'local':
            top_src = start_site.path
        else:
            top_src = "/store/user/" + start_site.username + "/" + start_site.path

        top_dst = ""
        if end_site.alias == 'local':
            top_dst = end_site.path
        else:
            top_dst = "/store/user/" + end_site.username + "/" + end_site.path

        if arguments.debug:
            print("main:")
            print("\ttop_src:", top_src)
            print("\ttop_dst:", top_dst)
            print("\tdepth:", str(arguments.depth))
            print("\tdry_run:", arguments.dry_run)
        copytree(start_site = start_site,
                 src = top_src,
                 end_site = end_site,
                 dst = top_dst,
                 current_depth = 0,
                 symlinks = False,
                 ignore = ignore_patterns(arguments.ignore),
                 arguments = arguments)

if __name__ == '__main__':
    #program name available through the %(prog)s command
    parser = argparse.ArgumentParser(formatter_class = argparse.RawDescriptionHelpFormatter,
                                     description = """
Transfer files from one location on the OSG to another.
Still need to implement the delete functionality for remote sites.""",
                                     epilog = """
#############
# Use Cases #
#############
Single file local to remote (gfal)
    python copyfiles.py local <absolute path>/<filename> T3_US_FNALLPC <path after username> -p gfal
Single file remote to local (gfal)
    python copyfiles.py T3_US_FNALLPC <path after username>/<filename> local <absolute path>/<filename> -p gfal
Single file local to remote (xrootd)
    python copyfiles.py local <absolute path> T3_US_FNALLPC <path after username> -p xrootd -s <filename>
Single file remote to local (xrootd)
    python copyfiles.py T3_US_FNALLPC <path after username> local <absolute path> -p xrootd -s <filename>
Single file local to local transfers
    python copyfiles.py local <path>/<filename> local <path>
Directory local to local transfers
    python copyfiles.py local <path>/ local <path> -r
Directory remote to local transfers (gfal - needs to be recursive to make folders)
    python copyfiles.py T3_US_FNALLPC <path> local <absolute path> -p gfal -r
Directory remote to local transfers (xrootd - can be made recursive)
    python copyfiles.py T3_US_FNALLPC <path after username> local <absolute path> -p xrootd --depth <number of levels down>

And those are the options available. Deal with it.""")
    group = parser.add_mutually_exclusive_group()
    parser.add_argument("start_server",
                        help = "The name of the server where the files are initially located")
    parser.add_argument("start_path",
                        help = "The location of the files within the users store area or the " \
                             "absolute path if the start_server is \'local\'")
    parser.add_argument("ENDserver",
                        help = "The name of the server to which the files should be copied")
    parser.add_argument("end_path",
                        help = "The location of the files within the users store area or the " \
                             "absolute path if the ENDserver is \'local\'")
    parser.add_argument("-a","--additional_arguments", type = str, default = "",
                        help = "Any additional arguments for the protocol that are not implemented here.")
    parser.add_argument("-d","--debug", action = "store_true",
                        help = "Shows some extra information in order to debug this program.")
    parser.add_argument("--depth", type = int, default = 1,
                        help = "The number of levels down to copy. 2 indicates just the files/folders " \
                             "inside start_path. (default = 1)")
    parser.add_argument("--delete", action = "store_true",
                        help = "Will remove the original files after a successful transfer. "\
                             "This will make the commands act more like a move than a copy.")
    parser.add_argument("-diff","--diff", action = "store_true",
                        help = """Tells the program to do a diff between the two directories and only copy the missing files.
                                Only works for two local directories. 
                                This is not implemented for the local to local or gfal transfers.""")
    parser.add_argument("--dry_run", action = "store_true",
                        help = "Do not perform any action, just print what would be done.")
    parser.add_argument("--from_file", type = str, default = "",
                        help = "Specify the files to copy. Only implemented for gfal.")
    parser.add_argument("-i","--ignore", nargs = '+', type = str, default = (),
                        help = "Patterns of files/folders to ignore. (default = ())")
    parser.add_argument("-p", "--protocol", choices = ["gfal","xrootd"], default = "xrootd",
                        help = "Gives the user the option on what protocol to use to transfer the files. (default = xrootd)")
    group.add_argument("-q", "--quiet", action = "store_true",
                       help = "decrease output verbosity to minimal amount")
    parser.add_argument("-r", "--recursive", action = "store_true",
                        help = "Recursively copies directories and files")
    parser.add_argument("-s", "--sample", nargs = '+', default = ["*"],
                        help = "Shared portion of the name of the files to be copied. (default = [\"*\"])")
    parser.add_argument("-str","--streams", default = "15",
                        help = "The number of transfer streams. (default = 15)")
    parser.add_argument("-su", "--start_user", default = os.environ['USER'],
                        help = "The username of the person transfering the files. (default = os.environ[\'USER\'])")
    parser.add_argument("-eu", "--end_user", default = os.environ['USER'],
                        help = "The username of the person transfering the files. (default = os.environ[\'USER\'])")
    parser.add_argument("-t","--timeout", default = "1800",
                        help = "Sets the send/recieve timeout for the gfal command. (default = 1800)")
    group.add_argument("-v", "--verbose", action = "store_true",
                       help = "Increase output verbosity of gfal-copy or xrdcp commands")
    parser.add_argument('--version', action = 'version', version = '%(prog)s 2.0b')
    args = parser.parse_args()

    if args.debug:
        print('Number of arguments:', len(sys.argv), 'arguments.')
        print('Argument List:', str(sys.argv))
        print("Argument ", args)

    main(args)
