#!/usr/bin/env python
import os, sys, argparse, subprocess, datetime, fnmatch, re, itertools
from collections import namedtuple

class Version(namedtuple('Version', 'version_info_0 version_info_1 version_info_2 version_info_3 path note')):
    __slots__ = ()
    def __eq__(self, major, mid, minor):
        return self.version_info_0 == major and self.version_info_1 == mid and self.version_info_2 == minor
    def __str__(self, note=""):
    	return "%i.%i.%i%s  %s  %s" % (self.version_info_0,self.version_info_1,self.version_info_2, \
    	                               self.version_info_3,self.path,note if self.note=="" else self.note)
    def getVersionString(self):
    	if self.version_info_0 == 0 and self.version_info_1 == 0 and self.version_info_2 == 0:
    		return ""
    	else:
	    	return "%i.%i.%i" % (self.version_info_0,self.version_info_1,self.version_info_2)

class FormattedVersion(namedtuple('FormattedVersion','Version Path Notes')):
	__slots__ = ()

# Split a path at slashes based on a set maximum width
def splitPathWidth(path,width=80):
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
def getShortPath(path):
	path_parts = path.split('/')
	return '/'+path_parts[1]+'/'+path_parts[2]+'/.../'+path_parts[-2]+'/'+path_parts[-1]

# Creates a version based on the ouput of a popen command to a python executable
def getVersionPopen(path,short_path="",note=""):
	p = subprocess.Popen(path+" --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
	output = p.communicate()[0]
	version_info = map(int,output.split()[1].split('.'))
	return Version(version_info[0],version_info[1],version_info[2],"",short_path if short_path != "" else path,note)

# Creates a version based on a folder name and some additional information
def getVersionFolder(basepath,folder_name,width=80,architecture="",note=""):
	folder_name_working = folder_name
	vnumbers = []
	for i in range(0,2):
		vnumbers.append(folder_name_working[0:folder_name_working.find('.')])
		folder_name_working = folder_name_working[folder_name_working.find('.')+1:]
	if '.' in folder_name_working:
		vnumbers += folder_name_working.split('.')
		vnumbers[-1] = "."+vnumbers[-1] #put back dot
	else:
		vnumbers += folder_name_working.split('-')
		vnumbers[-1] = "-"+vnumbers[-1] #put back dash
	endpath = "/<architecture>/bin/python" if architecture == "" else "/"+architecture+"/bin/python"
	path = basepath+folder_name+endpath
	pathlines = splitPathWidth(path,width)
	versions = []
	versions.append(Version(int(vnumbers[0]),int(vnumbers[1]),int(vnumbers[2]),str(vnumbers[3]),pathlines[0],note))
	if len(pathlines)>1:
		for ip,p in enumerate(pathlines):
			if ip == 0: continue
			versions.append(Version(0,0,0,"",p,""))
	return versions

# Converts a single Version to a single FormattedVersion
def versionToFormattedVersion(version):
	return FormattedVersion(version.getVersionString(),version.path,version.note)

# Converts a list of Versions to FormattedVersions
def versionsToFormattedVersions(versions):
	return [versionToFormattedVersion(v) for v in versions]

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
		print hpattern % tuple(headers)
		print separator
		_u = lambda t: t.decode('UTF-8', 'replace') if isinstance(t, str) else t
		for line in rows:
			print pattern % tuple(_u(t) for t in line)
	elif len(rows) == 1:
		row = rows[0]
		hwidth = len(max(row._fields,key=lambda x: len(x)))
		for i in range(len(row)):
			print "%*s = %s" % (hwidth,row._fields[i],row[i])

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
python getPythonVersions.py -s -f
# A list of just the python 2.7 versions
python getPythonVersions.py -g 2.7
""",
									 epilog="""
Mischief managed!""")
	parser.add_argument("-d","--debug", help="Shows some extra information in order to debug this program (default = %(default)s).",
						default=False, action="store_true")
	parser.add_argument("-f","--filter", help="Show only the python versions, ignoring the OS architectures (default = %(default)s).",
	                    default=False, action="store_true")
	parser.add_argument("-g","--grep", help="Select for a given python version pattern (default = %(default)s).",
	                    default="")
	parser.add_argument("-p","--pgrep", help="Select for a given path based on a pattern (default = %(default)s).",
	                    default="")
	parser.add_argument("-s","--shorten", help="Shorten the basepath of the CVMFS releases (default = %(default)s).",
	                    default=False, action="store_true")
	parser.add_argument('--version', help="The verion number of this program.",
						action='version', version='%(prog)s 1.0a')
	parser.add_argument("-w","--width", help="Maximum width of the path string (default = %(default)s).",
	                    default=120, type=int)
	args = parser.parse_args()

	if(args.debug):
		print 'Number of arguments:', len(sys.argv), 'arguments.'
		print 'Argument List:', str(sys.argv)
		print "Argument ", args

	# Set up the container of versions found
	versions = []

	# Get current running version
	if 'CMSSW_BASE' in os.environ:
		short_path = os.environ['CMSSW_RELEASE_BASE']+"/.../python"
	else:
		short_path = getShortPath(sys.executable)
	pathlines = splitPathWidth(short_path if args.shorten else sys.executable,args.width)
	versions.append(Version(sys.version_info[0],sys.version_info[1],sys.version_info[2],"",
	                        pathlines[0],"Currently running version"))
	if len(pathlines)>1:
		for ip,p in enumerate(pathlines):
			if ip == 0: continue
			versions.append(Version(0,0,0,"",p,""))

	# Get the system version
	versions.append(getVersionPopen("/usr/bin/python","","Default system python (" + ("sl7)" if os.uname()[2].find("el6") < 0 else "sl6)")))

	# Get the version if in a CMSSW release
	if 'CMSSW_BASE' in os.environ:
		short_path = os.environ['CMSSW_RELEASE_BASE']+"/.../python"
		pathlines = splitPathWidth(short_path if args.shorten else os.environ['CMSSW_RELEASE_BASE']+"/external/"+os.environ['SCRAM_ARCH']+"/bin/python",args.width)
		versions.append(getVersionPopen(os.environ['CMSSW_RELEASE_BASE']+"/external/"+os.environ['SCRAM_ARCH']+"/bin/python", \
		                                pathlines[0],"Python version from "+os.environ['CMSSW_VERSION']))
		if len(pathlines)>1:
			for ip,p in enumerate(pathlines):
				if ip == 0: continue
				versions.append(Version(0,0,0,"",p,""))

	# Get the versions available on CVMFS
	# Start by getting the initial list of python versions
	pattern = "?.?.*-*"
	basepath = "/cvmfs/sft.cern.ch/lcg/releases/Python/"
	dirs = []
	for dir in os.listdir(basepath):
		if fnmatch.fnmatch(dir, pattern):
			dirs.append(dir)

	# Sort based on version numbers and folder creation date
	# To get the human readable date and time use datetime.datetime.fromtimestamp(os.stat(<path>).st_ctime)
	dirs = sorted(dirs, key=lambda x: tuple([int(i) for i in re.findall('\d+', x)[:3]]+[os.stat(basepath+dir).st_ctime]))

	# Filter out multiple copied of the same python version (ignore version hashes)
	# Choose only the latest folder
	if args.filter:
		dirs_minor_version_groups = [list(b) for a, b in itertools.groupby(dirs, key=lambda x: x.split(".")[2].split('-')[0])]
		for minor_versions in dirs_minor_version_groups:
			# Need to re-sort on date for some reason once these are grouped. Maybe the grouping is messing up the time ordering.
			minor_versions = sorted(minor_versions, key=lambda x: os.stat(basepath+x).st_ctime)
			versions += getVersionFolder(basepath if not args.shorten else "/cvmfs/.../",minor_versions[-1],args.width)
	else:
		for dir in dirs:
			# Get list of architectures and filter for "-opt" and not "-dbg"
			archs = os.listdir(basepath+dir)
			pattern = "*-opt"
			archs = fnmatch.filter(archs,pattern)
			for arch in archs:
				versions += getVersionFolder(basepath if not args.shorten else "/cvmfs/.../",dir,args.width,arch)

	# Filter on version based on user defined pattern
	if args.grep != "":
		pattern = "*"+args.grep+"*"
		versions = [version for version in versions if fnmatch.fnmatch(version.getVersionString(),pattern)]

	# Filter on path based on user defined pattern
	if args.pgrep != "":
		pattern = "*"+args.pgrep+"*"
		versions = [version for version in versions if fnmatch.fnmatch(version.path,pattern)]

	# Convert from the raw version namedtuples to the formatted versions used for printing
	versions = versionsToFormattedVersions(versions)

	# Print the formatted table
	print "WARNING::getPythonVersions::Do not setup CMSSW and LCG software in the same environment.\n  Bad things will happen.\n"
	pprinttable(versions)

if __name__ == '__main__':
	import sys
	getPythonVersions(sys.argv[1:])
