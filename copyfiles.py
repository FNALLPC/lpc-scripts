#!/usr/bin/env python3
from __future__ import absolute_import
import argparse
import errno
import fnmatch
import getopt
import getSiteInfo
import os
import shlex
import subprocess
from subprocess import call
import sys

class Error(EnvironmentError):
    pass

class Location(getSiteInfo.Site):
    """Class for storing site, user, and path information"""
    def __init__(self,alias,username,path):
        super(Location, self).__init__(alias)
        self.username = username
        self.path = path

    def print_location_info(self,fast):
        self.print_site_info(fast)
        print("\tusername:", self.username)
        print("\tPath:", self.path)

def run_checks(RECURSIVE,DEPTH,STARTpath,ENDpath):
    print("Running checks on options ...")

    if RECURSIVE :
        print("\trun_checks::recursive option chosen so depth set to large value (9999)")
        DEPTH = 9999

    with open(os.devnull, 'wb') as devnull:
        process = subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'), stdout=devnull, stderr=subprocess.STDOUT)
        returncode = process.wait()
        if returncode!=0 :
            print("\tWARNING::You must have a valid proxy for this script to work.\nRunning \"voms-proxy-init -voms cms\"...\n")
            subprocess.call("voms-proxy-init -voms cms -valid 192:00", shell=True)
            process = subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'), stdout=devnull, stderr=subprocess.STDOUT)
            returncode = process.wait()
            if returncode!=0 :
                print("\tERROR::Sorry, but I still could not find your proxy.\n"
                      "Without a valid proxy, this program will fail spectacularly.\n"
                      "The program will now exit.")
                sys.exit()

    if STARTpath=="./":
        print("\trun_checks::STARTpath chosen as the current working directory ("+str(os.environ['PWD'])+")")
        STARTpath=os.environ['PWD']
    if ENDpath=="./":
        ENDpath=""

    print()
    return (RECURSIVE, DEPTH, STARTpath, ENDpath)

def init_commands(STARTsite, ENDsite, PROTOCOL, RECURSIVE=False, VERBOSE=False,
                  QUIET=False, STREAMS=15, TIMEOUT=1800, DRYRUN=False, ADDITIONAL=""):
    global args
    if args.debug:
        print("copyfiles::init_commands() initializing the start and end commands based on the chosen protocol ("+str(PROTOCOL)+")")

    copy_command = ""
    start_location = ""
    end_location = ""

    if(PROTOCOL=="gfal"):
        copy_command = "gfal-copy"
        if VERBOSE: copy_command += " -vvv"
        if RECURSIVE: copy_command += " -r"
        if DRYRUN: copy_command += " --dry-run"
        copy_command += " -n "+STREAMS+" --timeout "+TIMEOUT
    elif (PROTOCOL=="xrootd"):
        copy_command = "xrdcp"
        if(VERBOSE):
            copy_command += " -v"
        elif(QUIET):
            copy_command += " -s"
    if ADDITIONAL!="":
        copy_command += " "+ADDITIONAL

    if PROTOCOL=="xrootd" and STARTsite.alias=='local':
        start_location += " "+STARTsite.path+"/"
    elif PROTOCOL=="gfal" and STARTsite.alias=='local':
        start_location += " file:////"+STARTsite.path
    elif PROTOCOL=="gfal" and STARTsite.alias!='local':
        if STARTsite.gsiftp_endpoint!='None':
            start_location += " gsiftp://"+STARTsite.gsiftp_endpoint+"/store/user/"+STARTsite.username+"/"+STARTsite.path+"/"
        elif STARTsite.xrootd_endpoint!='None':
            start_location += " root://"+STARTsite.xrootd_endpoint+"//store/user/"+STARTsite.username+"/"+STARTsite.path+"/"
        else:
            print("ERROR::copyfiles::init_commands() The STARTsite must have either a gsiftp or xrootd endpoint")
            STARTsite.print_site_info(fast=True)
            sys.exit(-1)
    elif PROTOCOL=="xrootd" and STARTsite.alias!='local':
        start_location += " root://"+STARTsite.xrootd_endpoint+"//store/user/"+STARTsite.username+"/"+STARTsite.path+"/"
    else:
        print("ERROR::copyfiles::init_commands() could not figure out how to format the start command.")
        sys.exit(-2)

    if PROTOCOL=="xrootd" and ENDsite.alias=='local':
        end_location = ENDsite.path+"/"
    elif PROTOCOL=="gfal" and ENDsite.alias=='local':
        end_location = "file:////"+ENDsite.path
    elif PROTOCOL=="gfal" and ENDsite.alias!='local':
        if ENDsite.gsiftp_endpoint!='None':
            end_location = "gsiftp://"+ENDsite.gsiftp_endpoint+"/store/user/"+ENDsite.username+"/"+ENDsite.path+"/"
        elif ENDsite.xrootd_endpoint!='None':
            end_location = "root://"+ENDsite.xrootd_endpoint+"//store/user/"+ENDsite.username+"/"+ENDsite.path+"/"
        else:
            print("ERROR::copyfiles::init_commands() The ENDsite must have either a gsiftp or xrootd endpoint")
            ENDsite.print_site_info(fast=True)
            sys.exit(-3)
    elif PROTOCOL=="xrootd" and ENDsite.alias!='local':
        end_location = "root://"+ENDsite.xrootd_endpoint+"//store/user/"+ENDsite.username+"/"+ENDsite.path+"/"
    else:
        print("ERROR::copyfiles::init_commands() could not figure out how to format the end command.")
        sys.exit(-4)

    if args.debug:
        print("\tcopy_command:", copy_command)
        print("\tstart_location:", start_location)
        print("\tend_location:", end_location)

    return (copy_command,start_location,end_location)


def make_directory(ENDsite, path, PROTOCOL):
    global args
    made_dir = False

    if ENDsite.alias=='local' :
        if not os.path.exists(path) :
            os.makedirs(path)
            made_dir = True
    else:
        if PROTOCOL=="gfal":
            if ENDsite.gsiftp_endpoint!='None':
                cmd = "gfal-ls -v gsiftp://"+ENDsite.gsiftp_endpoint+"/"+path
            elif ENDsite.xrootd_endpoint!='None':
                cmd = "gfal-ls -v root://"+ENDsite.xrootd_endpoint+"/"+path
        elif PROTOCOL=="xrootd":
            cmd = "xrdfs root://"+ENDsite.xrootd_endpoint+"/ ls "+path  

        if os.system(cmd)!=0 and PROTOCOL=="gfal":
            if ENDsite.gsiftp_endpoint!='None':
                cmd = "gfal-mkdir gsiftp://"+ENDsite.gsiftp_endpoint+"/"+path
            elif ENDsite.xrootd_endpoint!='None':
                cmd = "gfal-mkdir root://"+ENDsite.xrootd_endpoint+"/"+path
            print("\tcmd:", cmd)
            os.system(cmd)
            made_dir = True
        elif os.system(cmd)!=0 and PROTOCOL=="xrootd":
            cmd = "xrdfs root://"+ENDsite.xrootd_endpoint+"/ mkdir "+path
            print("\tcmd:", cmd)
            os.system(cmd)
            made_dir = True

    if not made_dir:
        print("make_directory:")
        print("\tThere was a problem making the directory", path)
        print("\tEither the destination directory already exists or the make_directory command is broken")
    elif args.debug:
        print("make_directory:")
        print("\tstatus: success")
        print("\tdirectory:", path)
        print("\tprotocol:", PROTOCOL)

def get_list_of_files(PROTOCOL, STARTsite, SAMPLE, path, DEBUG=False):
    FILES_UNFILTERED = []
    if STARTsite.alias=='local':
        if os.path.isfile(path):
            return [os.path.basename(path)]
        else:
            FILES_UNFILTERED = os.listdir(path)
        if DEBUG:
            print("get_list_of_files:")
            print("\tList of files (unfiltered):", FILES_UNFILTERED)
    else:
        if PROTOCOL=="gfal":
            if STARTsite.gsiftp_endpoint!='None':
                options = "gfal-ls gsiftp://"+STARTsite.gsiftp_endpoint+"/"+path
            elif STARTsite.xrootd_endpoint!='None':
                options = "gfal-ls root://"+STARTsite.xrootd_endpoint+"/"+path
        elif PROTOCOL=="xrootd":
            options = "xrdfs root://"+STARTsite.xrootd_endpoint+"/ ls "+path 
        if DEBUG:
            print("get_list_of_files:")
            print("\tCommand: ", options)
        proc = subprocess.Popen(options, shell=True, stdout=subprocess.PIPE).communicate()[0]
        FILES_UNFILTERED = proc.splitlines()
        FILES_UNFILTERED = [x.strip(' ') for x in FILES_UNFILTERED]
        FILES_UNFILTERED = [x.strip('\n') for x in FILES_UNFILTERED]
    FILES_UNFILTERED = [x.replace("//", "/") for x in FILES_UNFILTERED]
    FILES_UNFILTERED = [x.split(' ',1)[0] if x.split(' ',1)[0].isdigit() else x for x in FILES_UNFILTERED]
    if PROTOCOL=='xrootd':
        FILES_UNFILTERED = [x.replace(x[:x.rfind("/")+1], "") for x in FILES_UNFILTERED]
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x != '']
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x != path.replace("//","/")]
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x!=path[path.find(STARTsite.path)+len(STARTsite.path):]]
    FILES_UNFILTERED = [x.split("/")[-1] if x[-1]!="/" else x.split("/")[-2]+"/" for x in FILES_UNFILTERED]
    FILES = []
    for ss in SAMPLE:
        FILES += fnmatch.filter(FILES_UNFILTERED, '*'+ss+'*')
    return FILES

def filter_list_of_files(SAMPLE, FILES_UNFILTERED):
    FILES = []
    if(len(SAMPLE)==0): SAMPLE = ["*"]
    for ss in SAMPLE:
        FILES += fnmatch.filter(FILES_UNFILTERED, '*'+ss+'*')
    return FILES

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

def do_diff(FILES, PROTOCOL, ENDsite, SAMPLE, dst):
    if ENDsite.alias=='local' and os.environ.get('HOSTNAME',"not found").find("fnal.gov") > 0 :
        FILES1 = os.listdir(dst)
    else:
        get_list_of_files(PROTOCOL, ENDsite, SAMPLE, dst, args.debug)
    FILES_DIFF = [f for f in FILES if f not in FILES1 or os.path.isdir(dst+"/"+f)]
    print("Adding an additional " + str(len(FILES_DIFF)) + " files/folders")
    return FILES_DIFF

def remoteIsDir(STARTsite,srcname):
    cmd = "xrdfs root://"+STARTsite.xrootd_endpoint+"/ stat -q IsDir "+srcname
    child = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    streamdata = child.communicate()[0]
    return child.returncode==0

def copytree(STARTsite, src, ENDsite, dst, DEPTH, CURRENTdepth, symlinks=False,
             SAMPLE=["*"], DIFF=False, ignore=None, PROTOCOL="local", RECURSIVE=False,
             STREAMS=15, TIMEOUT=1800, VERBOSE=False, QUIET=False, DRYRUN=False, ADDITIONAL=""):
    global args

    if args.debug:
        print("copytree:")
        print("\tsrc:", src)
        print("\tdst:", dst)
        print("\tDEPTH:", str(DEPTH))
        print("\tCURRENTdepth:", str(CURRENTdepth))
        print("\tsymlinks:", str(symlinks))
        print("\tDRYRUN:", str(DRYRUN))
    if CURRENTdepth >= DEPTH:
        return
    
    if not DRYRUN:
        make_directory(ENDsite,dst,PROTOCOL)

    FILES = get_list_of_files(PROTOCOL, STARTsite, SAMPLE, src, args.debug)

    if args.debug:
        print("copytree:")
        print("\tList of files:", FILES)

    if DIFF :
        FILES = do_diff(FILES, PROTOCOL, ENDsite, SAMPLE, dst)
    
    if ignore is not None:
        ignored_names = ignore(src, FILES)
    else:
        ignored_names = set()

    errors = []
    for FILE in FILES:
        if FILE in ignored_names:
            continue
        srcname = os.path.join(src, FILE)
        dstname = os.path.join(dst, FILE)

        try:
            if symlinks and os.path.islink(srcname):
                linkto = os.readlink(srcname)
                os.symlink(linkto,dstname)
            elif os.path.isdir(srcname) or (PROTOCOL=="xrootd" and remoteIsDir(STARTsite,srcname)):
                copytree(STARTsite,srcname,ENDsite,dstname,DEPTH,CURRENTdepth+1,symlinks,SAMPLE,DIFF,ignore,PROTOCOL,RECURSIVE,STREAMS,TIMEOUT,VERBOSE,QUIET,DRYRUN,ADDITIONAL)
            else:
                srel = os.path.relpath(src,src[:src.find(STARTsite.path)+len(STARTsite.path)])+"/"
                if srel == "./":
                    srel = ""
                copy_command, start_location, end_location = init_commands(STARTsite,ENDsite,PROTOCOL,RECURSIVE,VERBOSE,QUIET,STREAMS,TIMEOUT,DRYRUN,ADDITIONAL)
                print("Copying file " + FILE + " from " + srel)
                command = copy_command+" "+start_location+srel+FILE+" "+end_location+srel+FILE
                print(command)
                if not DRYRUN:
                    os.system(command)
                print("")
                
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
        except EnvironmentError, why:
            errors.append((srcname, dstname, str(why)))
    if errors:
        raise Error, errors

def local2local(STARTsite, ENDsite, RECURSIVE, DELETE, ADDITIONAL):
    command = 'mv' if DELETE else 'cp'
    if not DELETE and RECURSIVE:
        command += ' -R'
    command = command + ' ' + ADDITIONAL + ' ' + STARTsite.path + ' ' + ENDsite.path
    print(command)
    os.system(command)


def main(START, STARTpath, START_USER, END, ENDpath, END_USER, PROTOCOL, SAMPLE, DIFF, DELETE,
         FROM_FILE, RECURSIVE, IGNORE, DEPTH, VERBOSE, QUIET, STREAMS, TIMEOUT, ADDITIONAL, DRYRUN):
    RECURSIVE, DEPTH, STARTpath, ENDpath = run_checks(RECURSIVE,DEPTH,STARTpath,ENDpath)

    #get the site information
    STARTsite = Location(START,START_USER,STARTpath+"/" if START!='local' else STARTpath)
    if STARTsite.alias!='local': getSiteInfo.getSiteInfo(site=STARTsite,debug=args.debug,fast=True,quiet=True)
    ENDsite = Location(END,END_USER,ENDpath+"/" if END!='local' else ENDpath)
    if ENDsite.alias!='local': getSiteInfo.getSiteInfo(site=ENDsite,debug=args.debug,fast=True,quiet=True)
    #STARTsite = getSiteInfo.main(site_alias=START,debug=args.debug,fast=True,quiet=True) if START!='local' else Location('local',START_USER,STARTpath)
    #ENDsite = getSiteInfo.main(site_alias=END,debug=args.debug,fast=True,quiet=True) if END!='local' else Location('local',END_USER,ENDpath)

    #local to local copies can use POSIX commands
    if STARTsite.alias=='local' and ENDsite.alias=='local':
        local2local(STARTsite, ENDsite, RECURSIVE, DELETE, ADDITIONAL)
        return

    #gfal-copy has its own working recursive option, so we can take more advantage of that
    if PROTOCOL=='gfal':
        copy_command, start_location, end_location = init_commands(STARTsite,ENDsite,PROTOCOL,RECURSIVE,VERBOSE,QUIET,STREAMS,TIMEOUT,DRYRUN,ADDITIONAL)
        if FROM_FILE!="":
            command = copy_command+" --from-file "+file_list+" "+end_location
        else:
            command = copy_command+" "+start_location+" "+end_location
        print(command)
        os.system(command)
        return

    #Needed for the xrootd protocol because of the lack of a recursive functionality
    if PROTOCOL=='xrootd':
        TOPsrc = ""
        if STARTsite.alias=='local':
            TOPsrc = STARTsite.path
        else:
            TOPsrc = "/store/user/"+STARTsite.username+"/"+STARTsite.path

        TOPdst = ""
        if ENDsite.alias=='local':
            TOPdst = ENDsite.path
        else:
            TOPdst = "/store/user/"+ENDsite.username+"/"+ENDsite.path

        if args.debug:
            print("main:")
            print("\tTOPsrc:", TOPsrc)
            print("\tTOPdst:", TOPdst)
            print("\tDEPTH:", str(DEPTH))
            print("\tDRYRUN:", DRYRUN)
        copytree(STARTsite=STARTsite,src=TOPsrc,ENDsite=ENDsite,dst=TOPdst,DEPTH=DEPTH,CURRENTdepth=0,symlinks=False,
                 SAMPLE=SAMPLE,DIFF=DIFF,ignore=ignore_patterns(IGNORE),PROTOCOL=PROTOCOL,RECURSIVE=RECURSIVE,
                 STREAMS=STREAMS,TIMEOUT=TIMEOUT,VERBOSE=VERBOSE,QUIET=QUIET,DRYRUN=DRYRUN,ADDITIONAL=ADDITIONAL)
        return

if __name__ == '__main__':
    #program name available through the %(prog)s command
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description="""
Transfer files from one location on the OSG to another.
Still need to implement the delete functionality for remote sites.""",
                                     epilog="""
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
    parser.add_argument("STARTserver", help="The name of the server where the files are initially located")
    parser.add_argument("STARTpath", help="The location of the files within the users store area or the absolute path if the STARTserver is \'local\'")
    parser.add_argument("ENDserver", help="The name of the server to which the files should be copied")
    parser.add_argument("ENDpath", help="The location of the files within the users store area or the absolute path if the ENDserver is \'local\'")
    parser.add_argument("-a","--additional_arguments", help="Any additional arguments for the protocol that are not implemented here.",
                        type=str, default="")
    parser.add_argument("-d","--debug", help="Shows some extra information in order to debug this program.",
                        action="store_true")
    parser.add_argument("--depth", help="The number of levels down to copy. 2 indicates just the files/folders inside STARTpath. (default=1)",
                        type=int, default=1)
    parser.add_argument("--delete", help="Will remove the original files after a successful transfer. This will make the commands act more like a move than a copy.",
                        action="store_true")
    parser.add_argument("-diff","--diff", help="""Tells the program to do a diff between the two directories and only copy the missing files. Only works for two local directories.
                                                  This is not implemented for the local to local or gfal transfers.""", action="store_true")
    parser.add_argument("--dry_run", help="Do not perform any action, just print what would be done.",
                        action="store_true")
    parser.add_argument("--from_file", help="Specify the files to copy. Only implemented for gfal.",
                        type=str, default="")
    parser.add_argument("-i","--ignore", help="Patterns of files/folders to ignore. (default=())",
                        nargs='+', type=str, default=())
    parser.add_argument("-p", "--protocol", help="Gives the user the option on what protocol to use to transfer the files. (default=xrootd)",
                        choices=["gfal","xrootd"], default="xrootd")
    group.add_argument("-q", "--quiet", help="decrease output verbosity to minimal amount",
                       action="store_true")
    parser.add_argument("-r", "--recursive", help="Recursively copies directories and files",
                        action="store_true")
    parser.add_argument("-s", "--sample", help="Shared portion of the name of the files to be copied. (default=[\"*\"])", nargs='+',
                        default=["*"])
    parser.add_argument("-str","--streams", help="The number of transfer streams. (default=15)", default="15")
    parser.add_argument("-su", "--start_user", help="The username of the person transfering the files. (default=os.environ[\'USER\'])",
                        default=os.environ['USER'])
    parser.add_argument("-eu", "--end_user", help="The username of the person transfering the files. (default=os.environ[\'USER\'])",
                        default=os.environ['USER'])
    parser.add_argument("-t","--timeout", help="Sets the send/recieve timeout for the gfal command. (default=1800)",
                        default="1800")
    group.add_argument("-v", "--verbose", help="Increase output verbosity of gfal-copy or xrdcp commands",
                        action="store_true")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0b')
    args = parser.parse_args()

    if(args.debug):
         print('Number of arguments:', len(sys.argv), 'arguments.')
         print('Argument List:', str(sys.argv))
         print("Argument ", args)
    
    main(START=args.STARTserver, STARTpath=args.STARTpath, START_USER=args.start_user,
         END=args.ENDserver, ENDpath=args.ENDpath, END_USER=args.end_user,
         PROTOCOL=args.protocol, STREAMS=args.streams, TIMEOUT=args.timeout,
         DIFF=args.diff, DELETE=args.delete, RECURSIVE=args.recursive, DEPTH=args.depth,
         FROM_FILE=args.from_file, SAMPLE=args.sample, IGNORE=tuple(args.ignore), VERBOSE=args.verbose,
         QUIET=args.quiet, ADDITIONAL=args.additional_arguments, DRYRUN=args.dry_run)

