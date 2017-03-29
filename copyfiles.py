#!/usr/bin/env python
import os, sys, getopt, argparse, fnmatch, errno, subprocess, tempfile
from subprocess import call

class Error(EnvironmentError):
    pass

siteDBDict = {
#   alias: ('host_name_pattern', local_file_system, 'server', 'local_path_to_user_area', 'xrootd_path')
    'T1_US_FNAL' : ('.fnal.gov'       , 'cmsxrootd-site.fnal.gov', '' , '', 'root://cmsxrootd-site.fnal.gov/'),
    'T3_US_FNAL' : ('.fnal.gov'       , 'cmseos.fnal.gov'    , '/srm/v2/server?SFN=', '/eos/uscms/store/user/' , 'root://cmseos.fnal.gov/'),
    'T3_US_TAMU' : ('.brazos.tamu.edu', 'srm.brazos.tamu.edu', '/srm/v2/server?SFN=', '/fdata/hepx/store/user/', ''),
    'local'      : (''                , ''                   , ''                   , ''                       , '')
}



def run_checks(RECURSIVE,DEPTH,STARTpath,ENDpath):
    print "Running checks on options ..."

    if RECURSIVE :
        print "\trun_checks::recursive option chosen so depth set to large value (9999)"
        DEPTH = 9999

	if os.system("voms-proxy-info")!=0 :
		print "\tWARNING::You must have a valid proxy for this script to work.\nRunning \"voms-proxy-init -voms cms\"...\n"
		call("voms-proxy-init -voms cms -valid 192:00", shell=True)
		if os.system("voms-proxy-info")!=0 :
			print "\tERROR::Sorry, but I still could not find your proxy.\nWithout a valid proxy, this program will fail spectacularly.\nThe program will now exit." 
			sys.exit()

    if STARTpath[-1]!="/":
        STARTpath+="/"
    if ENDpath[-1]!="/":
        ENDpath+="/"

    if STARTpath=="./":
        print "\trun_checks::STARTpath chosen as the current working directory ("+str(os.environ['PWD'])+")"
        STARTpath=os.environ['PWD']
    if ENDpath=="./":
        ENDpath=""

    return (RECURSIVE, DEPTH, STARTpath, ENDpath)

def init_commands():
    print "init_commands::initializing the start and end commands based on the chosen protocol ("+str(PROTOCOL)+")"

    if(PROTOCOL=="lcg"):
        scommand = "lcg-cp"
        scommand += " -v " if VERBOSE else " "
        scommand += "-b -n "+STREAMS+" --sendreceive-timeout "+SRT+" --srm-timeout 60 -D srmv2"
    elif (PROTOCOL=="xrootd"):
        scommand = "xrdcp"
        if(VERBOSE):
            scommand += " -v"
        elif(QUIET):
            scommand += " -s"
    else:
        scommand = "srm-copy"

    if PROTOCOL=="xrootd" and START=='local':
        scommand += " \""+STARTpath+"/"
    elif PROTOCOL!="xrootd" and START=='local':
        scommand += " \"file:////"+STARTpath+"/"
    elif PROTOCOL=="xrootd" and START!='local':
        scommand += " \""+siteDBDict[START][4]+"//store/user/"+START_USER+"/"+STARTpath+"/"
    else:
        scommand += " \"srm://"+siteDBDict[START][1]+":8443"+siteDBDict[START][2]+siteDBDict[START][3]+"/"+START_USER+"/"+STARTpath+"/"

    if PROTOCOL=="xrootd" and END=='local':
        ecommand = "\""+ENDpath+"/"
    elif PROTOCOL!="xrootd" and END=='local':
        ecommand = "\"file:////"+ENDpath+"/"
    elif PROTOCOL=="xrootd" and END!='local':
        ecommand = "\""+siteDBDict[END][4]+"//store/user/"+END_USER+"/"+ENDpath+"/"
    else:
        ecommand = "\"srm://"+siteDBDict[END][1]+":8443"+siteDBDict[END][2]+siteDBDict[END][3]+"/"+END_USER+"/"+ENDpath+"/"

    print "\tscommand:",scommand
    print "\tecommand:",ecommand

    return (scommand,ecommand)


def make_directory(END, path, PROTOCOL):
    made_dir = False

    if END=='local' :
        if not os.path.exists(path) :
            os.makedirs(path)
            made_dir = True
    else:
        if PROTOCOL=="lcg":
            cmd = "lcg-ls -v -b -D srmv2 \"srm://"+siteDBDict[END][1]+":8443"+siteDBDict[END][2]+path+"\""
        elif PROTOCOL=="xrootd":
            cmd = "xrdfs "+siteDBDict[END][4]+" ls "+path  
        else:
            cmd = "srmls -2 -pushmode=true \"srm://"+siteDBDict[END][1]+":8443"+siteDBDict[END][2]+path+"\""

        if os.system(cmd)!=0 and PROTOCOL=="xrootd":
            cmd = "xrdfs "+siteDBDict[END][4]+" mkdir "+path
            print "\tcmd:",cmd
            os.system(cmd)
            made_dir = True
        else:
            cmd = "srm-mkdir \"srm://"+siteDBDict[END][1]+":8443"+siteDBDict[END][2]+path+"\""
            print "\tcmd:",cmd
            os.system(cmd)
            made_dir = True

    if made_dir:
        print "make_directory:"
        print "\tstatus: success"
        print "\tdirectory:",path
        print "\tprotocol:",PROTOCOL
    else:
        print "make_directory:"
        print "\tDestination directory already exists"

def get_list_of_files(START, START_USER, STARTpath, SAMPLE, path):
    global args
    FILES_UNFILTERED = []
    if START=='local': #and os.environ.get('HOSTNAME',"not found").find("fnal.gov") > 0 :
        FILES_UNFILTERED = os.listdir(path)
        if args.debug:
            print "get_list_of_files:"
            print "\tList of files:",FILES_UNFILTERED
    else:
        options = "srmls -2 -pushmode=true \"srm://"+siteDBDict[START][1]+":8443"+siteDBDict[START][2]+path+"\""
        proc = subprocess.Popen(options, shell=True, stdout=subprocess.PIPE).communicate()[0]
		# if output is too long
        #proc = subprocess.Popen(['srmls',options], stdout=tempfile.TemporaryFile()).communicate()[0]
        FILES_UNFILTERED = proc.splitlines()
        FILES_UNFILTERED = [x.strip(' ') for x in FILES_UNFILTERED]
        FILES_UNFILTERED = [x.strip('\n') for x in FILES_UNFILTERED]
	FILES_UNFILTERED = [x.replace("//", "/") for x in FILES_UNFILTERED]
	#FILES_UNFILTERED.remove('Picked up _JAVA_OPTIONS: -Xmx1024m')
    FILES_UNFILTERED = [x.split(' ',1)[0] if x.split(' ',1)[0].isdigit() else x for x in FILES_UNFILTERED]
    FILES_UNFILTERED = [x.replace((siteDBDict[START][3][siteDBDict[START][3].find("/store"):]+START_USER+"/"+STARTpath+"/").replace("//","/"), "") for x in FILES_UNFILTERED]
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x != '']
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x != path.replace("//","/")]
    FILES_UNFILTERED = [x for x in FILES_UNFILTERED if x!=path[path.find(STARTpath)+len(STARTpath):]]
    FILES_UNFILTERED = [x.split("/")[-1] if x[-1]!="/" else x.split("/")[-2]+"/" for x in FILES_UNFILTERED]
    FILES = []
    for ss in SAMPLE:
        FILES += fnmatch.filter(FILES_UNFILTERED, '*'+ss+'*')
    return FILES

def filter_list_of_files(SAMPLE, FILES_UNFILTERED):
    FILES = []
    if(len(SAMPLE)==1):
        SAMPLE = ["*"]
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

def copytree(START, START_USER, STARTpath, src, dst, DEPTH, CURRENTdepth, symlinks=False, ignore=None, PROTOCOL="local"):
    global args

    if args.debug:
        print "copytree:"
        print "\tsrc:",src
        print "\tdst:",dst
        print "\tCURRENTdepth:",str(CURRENTdepth)
        print "\tsymlinks:",str(symlinks)
    if CURRENTdepth >= DEPTH :
        return
    
    make_directory(END,dst,PROTOCOL)

    global SAMPLE
    FILES = get_list_of_files(START, START_USER, STARTpath, SAMPLE, src)
    #print "get_list_of_files src:",src
    #print "get_list_of_files STARTpath:",STARTpath
    if args.debug:
        print "copytree:"
        print "\tList of files:",FILES

    if DIFF :
        FILES1 = FILES
        if END=='local' and os.environ.get('HOSTNAME',"not found").find("fnal.gov") > 0 :
            FILES2 = os.listdir(dst)
        else:
            options = '"srm://'+siteDBDict[END][1]+':8443'+siteDBDict[END][2]+dst+'"'
            proc = subprocess.Popen(['srmls','-2','-pushmode=true',options], stderr=subprocess.STDOUT, stdout=subprocess.PIPE).communicate()[0]
            proc_splitlines = proc.splitlines()
            FILES2 = []
            for f in proc_splitlines :
                if len(f.split()) > 0 and f.split()[0].isdigit() :
                    FILES2.append(os.path.basename(f.split()[1]))
        FILES_DIFF = [f for f in FILES1 if f not in FILES2 or os.path.isdir(dst+"/"+f)]
        print "Adding an additional "+str(len(FILES_DIFF))+" files/folders"
        FILES = FILES_DIFF
    
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
            elif os.path.isdir(srcname) or (srcname[0]=="/" and srcname[-1]=="/" and PROTOCOL=="xrootd"):
                copytree(START, START_USER, STARTpath, srcname, dstname, DEPTH, CURRENTdepth+1, symlinks, ignore, PROTOCOL)
            else:
                srel = os.path.relpath(src,src[:src.find(STARTpath)+len(STARTpath)])+"/"
                if srel == "./":
                    srel = ""
                scommand, ecommand = init_commands()
                print "Copying file "+FILE+" from "+srel
                command = scommand+srel+FILE+"\" "+ecommand+srel+FILE+"\""
                if PROTOCOL=="srm":
                    ecommand+= " -2 -pushmode"
                    ecommand += " -debug" if VERBOSE else ""
                print command
                os.system(command)
                
        # catch the Error from the recursive copytree so that we can
        # continue with other files
        except Error, err:
            errors.extend(err.args[0])
        except EnvironmentError, why:
            errors.append((srcname, dstname, str(why)))
    if errors:
        raise Error, errors

def main(START, STARTpath, START_USER, END, ENDpath, END_USER, PROTOCOL, SAMPLE, DIFF,
         RECURSIVE, IGNORE, DEPTH, VERBOSE, QUIET, scommand, ecommand, STREAMS, SRT):
    RECURSIVE, DEPTH, STARTpath, ENDpath = run_checks(RECURSIVE,DEPTH,STARTpath,ENDpath)

    TOPsrc = ""
    if START=='local':
        TOPsrc = STARTpath
    else:
        TOPsrc = siteDBDict[START][3]+"/"+START_USER+"/"+STARTpath
        TOPsrc = TOPsrc[TOPsrc.find("/store"):]

    TOPdst = ""
    if END=='local':
        TOPdst = ENDpath
    else:
        TOPdst = siteDBDict[END][3]+"/"+END_USER+"/"+ENDpath
        TOPdst = TOPdst[TOPdst.find("/store"):]

    if args.debug:
        print "main:"
        print "\tTOPsrc:",TOPsrc
        print "\tTOPdst:",TOPdst
        print "\tDEPTH:",str(DEPTH)

    copytree(START,START_USER,STARTpath,TOPsrc,TOPdst, DEPTH, 0, False, ignore_patterns(IGNORE), PROTOCOL)


if __name__ == '__main__':
    #program name available through the %(prog)s command
    parser = argparse.ArgumentParser(description="Transfer files from one location on the OSG to another",
                                     epilog="And those are the options available. Deal with it.")
    group = parser.add_mutually_exclusive_group()
    parser.add_argument("STARTserver", help="The name of the server where the files are initially located",
                        choices=siteDBDict.keys())
    parser.add_argument("STARTpath", help="The location of the files within the users store or resilient areas")
    parser.add_argument("ENDserver", help="The name of the server to which the files should be copied",
                        choices=siteDBDict.keys())
    parser.add_argument("ENDpath", help="The location of the files within the users fdata area")
    parser.add_argument("-d","--debug", help="Shows some extra information in order to debug this program",
                        action="store_true")
    parser.add_argument("-diff","--diff",
                        help="Tells the program to do a diff between the two directories and only copy the missing files. Only works for two local directories.",
                        action="store_true")
    parser.add_argument("-i","--ignore", help="Patterns of files/folders to ignore",
                        nargs='+', type=str, default=())
    parser.add_argument("-p", "--protocol", help="Gives the user the option on what protocol to use to transfer the files",
                        choices=["srm","lcg","xrootd"], default="xrootd")
    parser.add_argument("-pnfs", "--pnfs", help="dCache location of original files", choices=["store","resilient"],
                        default="store")
    group.add_argument("-q", "--quiet", help="decrease output verbosity to minimal amount",
                       action="store_true")
    parser.add_argument("-r", "--recursive", help="Recursively copies directories and files",
                        action="store_true")
    parser.add_argument("-s", "--sample", help="Shared portion of the name of the files to be copied", nargs='+',
                        default=["*"])
    parser.add_argument("-srt","--sendreceive_timeout", help="Sets the send/recieve timeout for the lcg command",
                        default="20")
    parser.add_argument("-str","--streams", help="The number of transfer streams", default="15")
    parser.add_argument("-su", "--start_user", help="username of the person transfering the files",
                        default=os.environ['USER'])
    parser.add_argument("-eu", "--end_user", help="username of the person transfering the files",
                        default=os.environ['USER'])
    group.add_argument("-v", "--verbose", help="Increase output verbosity of lcg-cp (-v) or srm (-debug) commands",
                        action="store_true")
    parser.add_argument('--version', action='version', version='%(prog)s 2.0b')
    args = parser.parse_args()

    if(args.debug):
         print 'Number of arguments:', len(sys.argv), 'arguments.'
         print 'Argument List:', str(sys.argv)
         print "Argument ", args
    
    START = args.STARTserver
    STARTpath = args.STARTpath
    START_USER = args.start_user
    END = args.ENDserver
    ENDpath = args.ENDpath
    END_USER = args.end_user
    PROTOCOL = args.protocol
    SAMPLE = args.sample
    DIFF = args.diff
    RECURSIVE = args.recursive
    IGNORE = tuple(args.ignore)
    DEPTH = 1
    VERBOSE = args.verbose
    QUIET = args.quiet
    scommand = ""
    ecommand = ""
    STREAMS = args.streams
    SRT = args.sendreceive_timeout  

    main(START=args.STARTserver, STARTpath=args.STARTpath, START_USER=args.start_user,
         END=args.ENDserver, ENDpath=args.ENDpath, END_USER=args.end_user,
         PROTOCOL=args.protocol, STREAMS=args.streams, SRT=args.sendreceive_timeout,
         DIFF=args.diff, RECURSIVE=args.recursive, DEPTH=1,
         SAMPLE=args.sample, IGNORE=tuple(args.ignore),
         VERBOSE=args.verbose, QUIET=args.quiet, scommand="", ecommand="")

