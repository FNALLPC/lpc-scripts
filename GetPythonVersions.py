#!/usr/bin/env python3

"""
Returns a list of the python executables available to the user. These include
the python executable being used to run this module, the system python version,
the python executable in any currently setup CMSSW release (the user must run
'cmsenv' first), and all of the python versions contained within
/cvmfs/sft.cern.ch/lcg/views/.
"""

from __future__ import absolute_import
import argparse
import fnmatch
import os
import platform
import re
import subprocess
import sys
from collections import namedtuple

class Version(namedtuple('Version',
                         'version_info_0 version_info_1 version_info_2 version_info_3 ' \
                         'path notes lcg_versions_architectures_setups')):
    """A namedtuple containing the version information for a given python executable."""
    __slots__ = ()

    def __eq__(self, major, mid, minor):
        return (self.version_info_0 == major and
                self.version_info_1 == mid and
                self.version_info_2 == minor)
    def __hash__(self):
        return hash((self.version_info_0,
                     self.version_info_1,
                     self.version_info_2))
    def get_version_string(self):
        """Returns a formatted string containing the version major.mid.minor information."""
        if self.version_info_0 == 0 and self.version_info_1 == 0 and self.version_info_2 == 0:
            return ""
        else:
            return f"{self.version_info_0:d}.{self.version_info_1:d}.{self.version_info_2:d}"

class FormattedVersion(namedtuple('FormattedVersion',['Version','LCG_Versions','Architectures','Setup','Notes'])):
    """A namedtuple containing the formatted version information for a python executable,
    The values in the typle correspond to the information which will be sent to STDOUT.
    """
    __slots__ = ()

def collect_single_python_info(python_dict,
                               python_path,
                               version = "",
                               lcg_path = "",
                               lcg_version = "",
                               arch = "",
                               path = False,
                               shorten = False):
    """Parse and collect the information ofr a single python executable"""
    setup_text = lcg_path[0:lcg_path.find("bin")] + "setup.(c)sh" if not path else python_path
    setup_text = get_short_path(setup_text) if shorten else setup_text
    if version in python_dict:
        if lcg_version in python_dict[version].lcg_versions_architectures_setups:
            python_dict[version].lcg_versions_architectures_setups[lcg_version].append((arch, setup_text))
        else:
            python_dict[version].lcg_versions_architectures_setups[lcg_version] = [(arch, setup_text)]
    else:
        current_version_list = version.split('.')
        python_dict[version] = Version(current_version_list[0],
                                       current_version_list[1],
                                       current_version_list[2],
                                       str(current_version_list[3]) if len(current_version_list) > 3 else "",
                                       python_path,
                                       "",
                                       {lcg_version:[(arch, setup_text)]})

def collect_python_info(lcg_version_info_tuple,
                        grep = "",
                        path = False,
                        pgrep = "",
                        shorten = False,
                        debug = False):
    """Collect the python versions and their associated architectures."""
    lcg_paths, lcg_versions, architectures, python_paths = lcg_version_info_tuple
    python_dict = {}
    for ipath, ppath in enumerate(python_paths):
        # Filter on path based on user defined pattern
        if pgrep != "":
            pattern = "*" + pgrep + "*"
            if not fnmatch.fnmatch(ppath, pattern):
                continue

        current_version = get_version_from_path(ppath)

        # Filter on version based on user defined pattern
        if grep != "":
            pattern = "*" + grep + "*"
            if not fnmatch.fnmatch(current_version, pattern):
                continue

        collect_single_python_info(python_dict,
                                   python_path = ppath,
                                   version = current_version,
                                   lcg_path = lcg_paths[ipath],
                                   lcg_version = lcg_versions[ipath],
                                   arch = architectures[ipath],
                                   path = path,
                                   shorten = shorten)

    if debug:
        print("Python Dictionary:\n==================")
        print(python_dict, "\n")

    return python_dict

def get_architecture():
    """Return the OS information for the current system."""
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

def get_lcg_versions(agrep = "", lgrep = "", debug = False):
    """Get the LCG python versions associated architectures available on CVMFS."""
    pattern = "LCG_*"
    basepath = "/cvmfs/sft.cern.ch/lcg/views/"
    directories = []
    lcg_paths = []
    lcg_versions = []
    architectures = []
    python_paths = []
    for directory in os.listdir(basepath):
        if fnmatch.fnmatch(directory, pattern) and fnmatch.fnmatch(directory, "*" + lgrep + "*"):
            directories.append(directory)
    pattern = "*" + agrep + "*-opt" if agrep != "" else "*-opt"
    for directory in directories:
        archs = fnmatch.filter(os.listdir(basepath + directory), pattern)
        partial_list_lcg_paths = [basepath + directory + "/" + arch + "/bin/python" for arch in archs \
                                  if os.path.exists(basepath + directory + "/" + arch + "/bin/python")]
        lcg_paths += partial_list_lcg_paths
        lcg_versions += [directory.split('_')[1]] * len(partial_list_lcg_paths)
        architectures += [arch for arch in archs if os.path.exists(basepath + directory + "/" + arch + "/bin/python")]
        python_paths += [os.readlink(path) for path in partial_list_lcg_paths]

    if debug:
        print("LCG to python paths:\n====================")
        for ipath, path in enumerate(lcg_paths):
            print(path, "->", python_paths[ipath])
        print()

    return (lcg_paths, lcg_versions, architectures, python_paths)

def get_short_path(path, nfront=2, nback=2):
    """Create a shorter path out of the first two folders, last folder, and the last folder/filename."""
    path_parts = path.split('/')
    if nfront + nback >= len(path_parts) - 1:
        return path
    else:
        ret = '/'
        for i in range(1, nfront+1):
            ret += path_parts[i] + '/'
        ret += '...'
        for i in range(-nback, 0):
            ret += '/' + path_parts[i]
        return ret

def get_version_popen(path, note="", shorten=False, width=120, lcg_version="", architecture="", setup=""):
    """Creates a Version based on the ouput of a subprocess.Popen call.
    The command used askes a given python executable for its version information.
    """
    output = ""
    with subprocess.Popen(path+" --version", shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
        output = process.communicate()[0]
        output = output.decode('utf-8')
    output = output.replace('+','')
    version_info = list(map(int, output.split()[1].split('.')))
    versions = []
    short_path = get_short_path(path)
    pathlines = split_path_width(short_path if shorten else path, width=width)
    versions.append(Version(version_info[0],
                            version_info[1],
                            version_info[2],
                            str(0) if len(version_info)<4 else str(version_info[3]),
                            pathlines[0],
                            note,
                            {lcg_version:(architecture,setup)}))
    if len(pathlines) > 1:
        for ipathline, pathline in enumerate(pathlines):
            if ipathline == 0:
                continue
            versions.append(Version(0, 0, 0, "", pathline, "", {"" : ("", "")}))
    return versions

def get_version_from_path(path):
    """Get the python version specified in the path to a given executable.
    This is useful in parsing the version information for LCG python executables.
    This is much faster than running a subprocess.Popen call for each python executable.
    """
    version_part = [part for part in path.split('/') if re.match("[0-9].[0-9].[0-9]", part)][0]
    return version_part.split('-')[0]

def split_path_width(path, delim='/', width=120):
    """Split a string, usually a file path) at delim based on a maximum width for each piece.
    Each new string will have a width <= the width argument.
    """
    lines = ['']
    path_parts = path.split(delim)
    for ipart, part in enumerate(path_parts):
        if len(lines[-1]) + len(part) + 1 <= width:
            lines[-1] += part
        else:
            lines.append('  ' + part)
        if ipart < len(path_parts)-1:
            lines[-1] += delim
    return lines

def version_to_formatted_version(version, width):
    """Converts a single Version to a single FormattedVersion."""
    versions = []
    lcg_version, architecture_setup_tuple = version.lcg_versions_architectures_setups.popitem()
    setuplines = split_path_width(architecture_setup_tuple[1], width=width)
    versions.append(FormattedVersion(version.get_version_string(),
                                     lcg_version,
                                     architecture_setup_tuple[0],
                                     setuplines[0],
                                     version.notes))
    if len(setuplines) > 1:
        for iline, line in enumerate(setuplines):
            if iline == 0:
                continue
            versions.append(FormattedVersion("", "", "", line, ""))
    return versions

def versions_to_formatted_versions(versions, width):
    """Converts a list of Versions to a list of FormattedVersions.
    This is primarily used to format the list of python versions for the
    current, system, and CMSSW python executables.
    """
    ret = []
    for version in versions:
        ret += version_to_formatted_version(version, width)
    return ret

def dict_entry_to_formatted_version(python_version, version, width):
    """Converts a single Version to a single FormattedVersion."""
    versions = []
    for lcg_version, values in sorted(version.lcg_versions_architectures_setups.items()):
        for ivalue, value in enumerate(values):
            setuplines = split_path_width(value[1], width=width)
            versions.append(FormattedVersion(python_version if len(versions) == 0 else "",
                                             lcg_version if ivalue == 0 else "",
                                             value[0],
                                             setuplines[0],
                                             ""))
            if len(setuplines)>1:
                for iline, line in enumerate(setuplines):
                    if iline == 0:
                        continue
                    versions.append(FormattedVersion("", "", "", line, ""))
    return versions

def dict_to_formatted_versions(dictionary, width):
    """Converts a list of Versions to a sorted list of FormattedVersions.
    This is mainly used to format the list of LCG python versions.
    """
    versions = []
    sorted_list = sorted(dictionary.items(),
                         key=lambda item: tuple(list(map(int, item[0].split('.')[0:3])) +
                                                [item[0].split('.')[3] if len(item[0].split('.')) > 3 else ""]))
    for python_version, version in sorted_list:
        versions += dict_entry_to_formatted_version(python_version, version, width)
    return versions

def pprinttable(rows):
    """Prints a well formatted version of a single or multiple namedtuple(s)
    Taken from: https://stackoverflow.com/questions/5909873/how-can-i-pretty-print-ascii-tables-with-python
    """
    if len(rows) > 1:
        headers = rows[0]._fields
        lens = []
        for i in range(len(rows[0])):
            lens.append(len(max([x[i] for x in rows] + [headers[i]], key=lambda x:len(str(x)))))
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
        for line in rows:
            print(pattern % tuple(t for t in line))
    elif len(rows) == 1:
        row = rows[0]
        #pylint: disable=unused-variable
        hwidth = len(max(row._fields, len))
        for irow_item, row_item in enumerate(row):
            print(f"{row._fields[irow_item]:hwidth} = {row_item}")

def get_python_versions(args):
    """This is the main function for the GetPythonVersion module.
    The entire module runs through this function. It coordinates the argument parsing,
    version finding, and printing the final table.
    """

    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description="""
Get the python versions available on a given server.

#######################
# Examples of running #
#######################
# A list of all available python versions
python GetPythonVersions.py
# A list of unique version with shortened paths
python GetPythonVersions.py -s
# A list of just the python 2.7 versions
python GetPythonVersions.py -g 2.7
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

    if args.debug:
        print("argparse debug:\n===============")
        print('Number of arguments:', len(sys.argv), 'arguments.')
        print('Argument List:', str(sys.argv))
        print("Argument ", args, "\n")

    # Set up the container of versions found
    versions = []

    # Get current running version
    versions += [Version(sys.version_info[0],
                         sys.version_info[1],
                         sys.version_info[2],
                         "",
                         sys.executable,
                         "Currently running version",
                         {"N/A":(get_architecture(),"Unknown" if not args.path \
                                 else sys.executable if not args.shorten else get_short_path(sys.executable))})]

    # Get the system version
    python_path = "/usr/bin/python"
    versions += get_version_popen(python_path,
                                "Default system python (" + ("sl7)" if os.uname()[2].find("el6") < 0 else "sl6)"),
                                args.shorten,
                                120,
                                "N/A",
                                get_architecture(),
                                "N/A" if not args.path else python_path if not args.shorten \
                                else get_short_path(python_path))

    # Get the version if in a CMSSW release
    if 'CMSSW_BASE' in os.environ:
        python_path = os.environ['CMSSW_RELEASE_BASE']+"/external/"+os.environ['SCRAM_ARCH']+"/bin/python"
        versions += get_version_popen(python_path,
                                    "Python version from " + os.environ['CMSSW_VERSION'],
                                    args.shorten,
                                    120,
                                    "N/A",
                                    os.environ['SCRAM_ARCH'],
                                    os.environ['CMSSW_BASE'] if not args.path else python_path if not args.shorten \
                                    else get_short_path(python_path))

    # Get the LCG python versions available on CVMFS
    lcg_version_info_tuple = get_lcg_versions(agrep = args.agrep,
                                              lgrep = args.lgrep,
                                              debug = args.debug)

    # Collect the python versions and their associated architectures
    python_dict = collect_python_info(lcg_version_info_tuple,
                                      grep = args.grep,
                                      path = args.path,
                                      pgrep = args.pgrep,
                                      shorten = args.shorten,
                                      debug = args.debug)

    # Convert from the raw version namedtuples to the formatted versions used for printing
    versions  = versions_to_formatted_versions(versions, args.width)
    versions += dict_to_formatted_versions(python_dict, args.width)

    # Print the formatted table
    print("WARNING::getPythonVersions::Do not setup CMSSW and LCG software in the same environment.\n" \
          "Bad things will happen.\n")
    print("To setup the LCG software do:\n"
              "  source /cvmfs/sft.cern.ch/lcg/views/<LCG Version>/<Architecture>/setup.(c)sh\n")
    pprinttable(versions)

if __name__ == '__main__':
    get_python_versions(sys.argv[1:])
