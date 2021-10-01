#!/usr/bin/env python3
from __future__ import absolute_import
import argparse
import datetime
import fnmatch
import itertools
import os
import platform
import re
import subprocess
import sys
from collections import namedtuple

class Version(namedtuple('Version', 'version_info_0 version_info_1 version_info_2 version_info_3 path notes lcg_versions_architectures_setups')):
    __slots__ = ()
    def __eq__(self, major, mid, minor):
        return (self.version_info_0 == major and
                self.version_info_1 == mid and
                self.version_info_2 == minor)
    def __hash__(self):
        return hash((self.version_info_0,
                     self.version_info_1,
                     self.version_info_2))
    def getVersionString(self):
    	if self.version_info_0 == 0 and self.version_info_1 == 0 and self.version_info_2 == 0:
    		return ""
    	else:
	    	return "%i.%i.%i" % (self.version_info_0,self.version_info_1,self.version_info_2)

class FormattedVersion(namedtuple('FormattedVersion',['Version','LCG_Versions','Architectures','Setup','Notes'])):
	__slots__ = ()

# Get the system architecture
def getArchitecture():
	uname = os.uname()
	ret = uname[-1]+"-"
	if "el6" in uname[2]:
		ret += "slc6"
	elif "el7" in uname[2]:
		ret += "centos7"
	else:
		ret += "unknown"

	ret += "-gcc" + platform.python_compiler().split()[1].replace(".","")
	return ret

# Split a path at slashes based on a set maximum width
def splitPathWidth(path,width=120):
	lines = ['']
	path_parts = path.split('/')
	for ip,p in enumerate(path_parts):
		if len(lines[-1])+len(p)+1 <= width:
			lines[-1] += p
		else:
			lines.append('  '+p)
		if ip<len(path_parts)-1:
				lines[-1] += '/'
	return lines

# Create a shorter path out of the first two folders, last folder, and the last folder/filename
def getShortPath(path, nfront=2, nback=2):
	path_parts = path.split('/')
	if nfront+nback >= len(path_parts)-1:
		return path
	else:
		ret = '/'
		for i in range(1,nfront+1):
			ret += path_parts[i] + '/'
		ret += '...'
		for i in range(-nback,0):
			ret += '/' + path_parts[i]
		return ret

# Creates a version based on the ouput of a popen command to a python executable
def getVersionPopen(path,note="",shorten=False,width=120,lcg_version="",architecture="",setup=""):
	p = subprocess.Popen(path+" --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	output = p.communicate()[0]
	output = output.replace('+','')
	version_info = map(int,output.split()[1].split('.'))
	versions = []
	short_path = getShortPath(path)
	pathlines = splitPathWidth(short_path if shorten else path,width)
	versions.append(Version(version_info[0],version_info[1],version_info[2],str(0) if len(version_info)<4 else str(version_info[3]),\
	            	pathlines[0],note,{lcg_version:(architecture,setup)}))
	if len(pathlines)>1:
		for ip,p in enumerate(pathlines):
			if ip == 0: continue
			versions.append(Version(0,0,0,"",p,"",{"":("","")}))
	return versions

# Get the python version from the path to the executable
def getVersionFromPath(path):
	version_part = path.split('/')[6]
	return version_part.split('-')[0]

# Converts a single Version to a single FormattedVersion
def versionToFormattedVersion(version,width):
	versions = []
	lcg_version, architecture_setup_tuple = version.lcg_versions_architectures_setups.popitem()
	setuplines = splitPathWidth(architecture_setup_tuple[1],width)
	versions.append(FormattedVersion(version.getVersionString(),lcg_version,architecture_setup_tuple[0],setuplines[0],version.notes))
	if len(setuplines)>1:
		for i, l in enumerate(setuplines):
			if i == 0: continue
			versions.append(FormattedVersion("","","",l,""))
	return versions

# Converts a list of Versions to FormattedVersions
def versionsToFormattedVersions(versions,width):
	ret = []
	for v in versions:
		ret += versionToFormattedVersion(v,width)
	return ret

# Converts a single Version to a single FormattedVersion
def dictEntryToFormattedVersion(python_version,version,width):
	versions = []
	for lcg_version, value in sorted(version.lcg_versions_architectures_setups.iteritems()):
		for iv, v in enumerate(value):
			setuplines = splitPathWidth(v[1],width)
			versions.append(FormattedVersion(python_version if len(versions) == 0 else "", lcg_version if iv == 0 else "", v[0], setuplines[0], ""))
			if len(setuplines)>1:
				for i, l in enumerate(setuplines):
					if i == 0: continue
					versions.append(FormattedVersion("","","",l,""))
	return versions

# Converts a list of Versions to FormattedVersions
def dictToFormattedVersions(dict,width):
	versions = []
	for python_version, version in sorted(dict.iteritems(),
                                              key=lambda (k,v): tuple(map(int,k.split('.')[0:3]) + 
                                                                      [k.split('.')[3] if len(k.split('.'))>3 else ""])):
		versions += dictEntryToFormattedVersion(python_version,version,width)
	return versions

# Prints a well formatted version of a single or multiple namedtuple(s)
# Taken from: https://stackoverflow.com/questions/5909873/how-can-i-pretty-print-ascii-tables-with-python
def pprinttable(rows):
	if len(rows) > 1:
		headers = rows[0]._fields
		lens = []
		for i in range(len(rows[0])):
			lens.append(len(max([x[i] for x in rows] + [headers[i]],key=lambda x:len(str(x)))))
		formats = []
		hformats = []
		for i in range(len(rows[0])):
			if isinstance(rows[0][i], int):
				formats.append("%%%dd" % lens[i])
			else:
				formats.append("%%-%ds" % lens[i])
			hformats.append("%%-%ds" % lens[i])
		pattern = " | ".join(formats)
		hpattern = " | ".join(hformats)
		separator = "-+-".join(['-' * n for n in lens])
		print(hpattern % tuple(headers))
		print(separator)
		_u = lambda t: t.decode('UTF-8', 'replace') if isinstance(t, str) else t
		for line in rows:
			print(pattern % tuple(_u(t) for t in line))
	elif len(rows) == 1:
		row = rows[0]
		hwidth = len(max(row._fields,key=lambda x: len(x)))
		for i in range(len(row)):
			print("%*s = %s" % (hwidth,row._fields[i],row[i]))

def getPythonVersions(args):

	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
									 description="""
Get the python versions available on a given server.

#######################
# Examples of running #
#######################
# A list of all available python versions
python getPythonVersions.py
# A list of unique version with shortened paths
python getPythonVersions.py -s
# A list of just the python 2.7 versions
python getPythonVersions.py -g 2.7
""",
									 epilog="""
Note: The grep options are not applied to the current, system, or CMSSW python versions.

Mischief managed!""")
	parser.add_argument("-a","--agrep", default="",
                            help="Select for a given architecture based on a pattern (default = %(default)s).")
	parser.add_argument("-d","--debug", default=False, action="store_true",
                            help="Shows some extra information in order to debug this program (default = %(default)s).")
	parser.add_argument("-g","--grep", default="",
                            help="Select for a given python version pattern (default = %(default)s).")
	parser.add_argument("-l","--lgrep", default="",
                            help="Select for a given LCG version based on a pattern (default = %(default)s).")
	parser.add_argument("-p","--pgrep", default="",
                            help="Select for a given path based on a pattern (default = %(default)s).")
	parser.add_argument("--path", default=False, action="store_true",
                            help="Replace the setup path with the path to the python executable (default = %(default)s).")
	parser.add_argument("-s","--shorten", default=False, action="store_true",
                            help="Shorten the setup path of the CVMFS releases (default = %(default)s).")
	parser.add_argument('--version', action='version', version='%(prog)s 1.0b',
                            help="The verion number of this program.")
	parser.add_argument("-w","--width", default=120, type=int,
                            help="Maximum width of the setup string (default = %(default)s).")
	args = parser.parse_args()

	if(args.debug):
		print("argparse debug:\n===============")
		print('Number of arguments:', len(sys.argv), 'arguments.')
		print('Argument List:', str(sys.argv))
		print("Argument ", args, "\n")

	# Set up the container of versions found
	versions = []

	# Get current running version
	versions += [Version(sys.version_info[0],sys.version_info[1],sys.version_info[2],"", \
	                     sys.executable,"Currently running version", \
	                     {"N/A":(getArchitecture(),"Unknown" if not args.path else sys.executable if not args.shorten else getShortPath(sys.executable))})]

	# Get the system version
	python_path = "/usr/bin/python"
	versions += getVersionPopen(python_path,"Default system python (" + ("sl7)" if os.uname()[2].find("el6") < 0 else "sl6)"), \
	                            args.shorten,120,"N/A",getArchitecture(), \
	                            "N/A" if not args.path else python_path if not args.shorten else getShortPath(python_path))

	# Get the version if in a CMSSW release
	if 'CMSSW_BASE' in os.environ:
		python_path = os.environ['CMSSW_RELEASE_BASE']+"/external/"+os.environ['SCRAM_ARCH']+"/bin/python"
		versions += getVersionPopen(python_path,"Python version from "+os.environ['CMSSW_VERSION'],args.shorten,120,"N/A", \
	                                os.environ['SCRAM_ARCH'], \
	                                os.environ['CMSSW_BASE'] if not args.path else python_path if not args.shorten else getShortPath(python_path))

	# Get the versions available on CVMFS
	# Start by getting the list of LCG versions and the associated architectures
	pattern = "LCG_*"
	basepath = "/cvmfs/sft.cern.ch/lcg/views/"
	dirs = []
	lcg_paths = []
	lcg_versions = []
	architectures = []
	python_paths = []
	for dir in os.listdir(basepath):
		if fnmatch.fnmatch(dir, pattern) and fnmatch.fnmatch(dir,"*"+args.lgrep+"*"):
			dirs.append(dir)
	pattern = "*"+args.agrep+"*-opt" if args.agrep != "" else "*-opt"
	for dir in dirs:
		archs = fnmatch.filter(os.listdir(basepath+dir),pattern)
		partial_list_lcg_paths = [basepath+dir+"/"+arch+"/bin/python" for arch in archs if os.path.exists(basepath+dir+"/"+arch+"/bin/python")]
		lcg_paths += partial_list_lcg_paths
		lcg_versions += [dir.split('_')[1]]*len(partial_list_lcg_paths)
		architectures += [arch for arch in archs if os.path.exists(basepath+dir+"/"+arch+"/bin/python")]
		python_paths += [os.readlink(path) for path in partial_list_lcg_paths]

	if args.debug:
		print("LCG to python paths:\n====================")
		for ip,p in enumerate(lcg_paths):
			print(p,"->",python_paths[ip])
		print()

	# Collect the python versions and their associated architectures
	python_dict = {}
	for ipath,ppath in enumerate(python_paths):
		# Filter on path based on user defined pattern
		if args.pgrep != "":
			pattern = "*"+args.pgrep+"*"
			if not fnmatch.fnmatch(ppath,pattern): continue

		current_version = getVersionFromPath(ppath)

		# Filter on version based on user defined pattern
		if args.grep != "":
			pattern = "*"+args.grep+"*"
			if not fnmatch.fnmatch(current_version,pattern): continue

		current_lcg_path = lcg_paths[ipath]
		current_lcg_version = lcg_versions[ipath]
		current_arch = architectures[ipath]
		current_setup_text = current_lcg_path[0:current_lcg_path.find("bin")]+"setup.(c)sh" if not args.path else ppath
		current_setup_text = getShortPath(current_setup_text) if args.shorten else current_setup_text
		if current_version in python_dict:
			if current_lcg_version in python_dict[current_version].lcg_versions_architectures_setups:
				python_dict[current_version].lcg_versions_architectures_setups[current_lcg_version].append((current_arch,current_setup_text))
			else:
				python_dict[current_version].lcg_versions_architectures_setups[current_lcg_version] = [(current_arch,current_setup_text)]
		else:
			current_version_list = current_version.split('.')
			python_dict[current_version] = Version(current_version_list[0],current_version_list[1],current_version_list[2], \
			                                       str(current_version_list[3]) if len(current_version_list)>3 else "", \
			                                       ppath, "",{current_lcg_version:[(current_arch,current_setup_text)]})

	if args.debug:
		print("Python Dictionary:\n==================")
		print(python_dict)
		print()

	# Convert from the raw version namedtuples to the formatted versions used for printing
	versions  = versionsToFormattedVersions(versions,args.width)
	versions += dictToFormattedVersions(python_dict,args.width)

	# Print the formatted table
	print("WARNING::getPythonVersions::Do not setup CMSSW and LCG software in the same environment.\n  Bad things will happen.\n")
	print("To setup the LCG software do:\n"
              "  source /cvmfs/sft.cern.ch/lcg/views/<LCG Version>/<Architecture>/setup.(c)sh\n")
	pprinttable(versions)

if __name__ == '__main__':
	import sys
	getPythonVersions(sys.argv[1:])
