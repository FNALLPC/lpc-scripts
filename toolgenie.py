#!/usr/bin/env python

"""Prints the CMSSW external tool information for a given set of architectures, CMSSW releases, and tools.
The program can be run, specifying all of the architectures, releases, and tools the user would like to
know about. However, it can also be run interactively, letting the module prompt the user for information.
In addition to specifying a list of choices, the user may also use regular expressions to cast a wirder net.
The modules output will be printed to STDOUT.
"""

# pylint: disable=unexpected-special-method-signature

from __future__ import absolute_import
from __future__ import print_function
from collections import namedtuple
from enum import Enum
import argparse
import os
import re
import ssl
import xml.etree.ElementTree as ET
import six.moves

class MapSource(Enum):
    """Enums specifying the source of the CMSSW release map."""
    CVMFS = 'CVMFS'
    GITHUB = 'GITHUB'
    CMSSDT = 'CMSSDT'

    def __str__(self):
        return self.value

class CMSSW(namedtuple('CMSSW', 'prefix major mid minor extra note')):
    """A namedtuple which contains the version information for a single CMSSW release."""
    __slots__ = ()
    def __eq__(self,prefix,major,mid,minor,extra,note):
        return (self.prefix == prefix and self.major == major and
                self.mid == mid and self.minor == minor and
                self.extra == extra and self.note == note)
    def __hash__(self):
        return hash((self.prefix, self.major, self.mid, self.minor, self.extra, self.note))
CMSSW.__new__.__defaults__ = ("",) * len(CMSSW._fields)

class Release(namedtuple('Release', 'architecture label type state prodarch')):
    """A namedtuple which contains the architecture information for a given CMSSW release."""
    __slots__ = ()
    def __eq__(self, architecture, label):
        return self.architecture == architecture and self.label == label
    def __hash__(self):
        return hash((self.architecture, self.label))
    def get_release_string(self):
        """Return a formatted string containing the Release information.
        This string matches that found in the text-based release maps.
        """
        return ("architecture=%s;label=%s;type=%s;state=%s;prodarch=%s;" %
                (self.architecture, self.label, self.type, self.state, self.prodarch))

class Toolbox(namedtuple('Toolbox',['Release','Tools','Path'])):
    """A namedtuple which contains the information needed to specify the tools for a single release."""
    __slots__ = ()

class Tool(namedtuple('Tool',['Name','ConfigPaths','Locations','Versions','Architectures','Releases'])):
    """A namedtuple containing the information for a single tool, with multiple versions, architectures, and releases."""
    __slots__ = ()

def filter_on_architecture(release_map, architectures):
    """Filter the list of Releases based on the chosen architectures.
    The input is a list of Releases and a list of chosen architectures.
    """
    return [release for release in release_map if \
            any(architecture in release.architecture for architecture in architectures)]

def filter_on_branch_name(line):
    """We want to skip releases listed in the map file who are named after branches
    Typically these take the form 'CMSSW_#_#_X'
    These entries tend to not have actual folders on CVMFS
    Returns true if a line containing this pattern is found
    """
    return re.search("^(CMSSW)_[0-9]*_[0-9]*_[^0-9].*(?m)",line)

def filter_on_label(release_map, labels):
    """Filter the list of Releases based on the chosen labels.
    The input is a list of Releases and a list of chosen labels for those releases.
    """
    return [release for release in release_map if any(label in release.label for label in labels)]

def filter_on_tool(toolboxes, tool):
    """Filter the list of tools for the selected releases based on the selected tool name.
    The input is a list of Toolboxes (tools in the selected CMSSW releases) and a tool name.
    """
    return [tb for tb in toolboxes if tool in tb.Tools]

def get_architectures(release_map):
    """Return a sorted list of architectures from a list of Releases."""
    archs = []
    for rel in release_map:
        if rel.architecture not in archs:
            archs.append(rel.architecture)
    return sorted(archs)

def get_labels(release_map):
    """Return a sorted list of labels from a list of Releases."""
    labels = []
    for rel in release_map:
        if rel.label not in labels:
            labels.append(rel.label)
    return sorted(labels, key=lambda label: \
                  CMSSW([int(x) if x.isdigit() else 999 if isinstance(x, str) \
                         else x for ix, x in enumerate(label.split("_"))]))

def get_selected_architectures(relmap, architecture = None, quiet = False):
    """Select a SCRAM architecture or a set of architectures.
    Return the list of architectures and the user input that led to that selection.
    """
    architecture_options = get_architectures(relmap)
    user_response = ""
    if architecture is None:
        print("Select an architecture. For a single architecture selection, " \
              "you can enter the item number or the name of the architecture. " \
              "To select multiple architectures, you can use a regex using the syntax \'r:<regex>\'.")
        if not quiet:
            print_list(architecture_options,"architecture")
        pattern = "{0:>12s} -- {1:<30s}\n"
        print("Example regex:\n" + pattern.format("r:.*","All architectures") + pattern.format("r:slc7.*","All slc7 releases"))
        user_response = six.moves.input('--> ')
        print()
    else:
        user_response = architecture
    if user_response.isdigit() and (int(user_response) > len(architecture_options) or int(user_response) < 0):
        raise Exception("The response was out of bounds. You must enter a listed value.\n")
    if not user_response.isdigit() and 'r:' not in user_response and user_response not in architecture_options:
        raise Exception("The response was not in the list of acceptable scram architectures.\n")
    selected_architectures = []
    if 'r:' in user_response:
        user_response_altered = user_response[2:]
        selected_architectures = [ao for ao in architecture_options if re.search(user_response_altered,ao)]
    else:
        selected_architectures = [architecture_options[int(user_response)-1]
                                  if user_response.isdigit() else user_response]
    if len(selected_architectures) == 0:
        raise Exception("Uh oh! No architectures were found based on your input ({0}).".format(user_response))

    return (selected_architectures, user_response)

def get_selected_releases(selected_releases, cmssw = None, quiet = False):
    """Select and return a set of CMSSW releases."""
    label_options = get_labels(selected_releases)
    user_response = ""
    if cmssw is None:
        print("Select a CMSSW release. For a single release, " \
              "you can enter the item number or the name of the release. " \
              "To select multiple relases, you can use a regex using the syntax \'r:<regex>\'.")
        if not quiet:
            print_list(label_options,"release")
        pattern = "{0:>37s} -- {1:<50s}\n"
        print("Example regex:\n" +
              pattern.format("r:.*","All CMSSW releases for the previously selected architectures") +
              pattern.format("r:CMSSW_1._[0,6]_.*(?<!pre[0-9])$","All CMSSW releases with " \
                             "X=10-19, Y=0 or 6, Z=anything, and which aren't a pre release"))
        user_response = six.moves.input('--> ')
        print()
    else:
        user_response = cmssw
    if user_response.isdigit() and (int(user_response) > len(label_options) or int(user_response) < 0):
        raise Exception("The response was out of bounds. You must enter a listed value.\n")
    if not user_response.isdigit() and 'r:' not in user_response and user_response not in label_options:
        raise Exception("The response was not in the list of acceptable CMSSW releases.\n")
    selected_labels = []
    if 'r:' in user_response:
        user_response_altered = user_response[2:]
        selected_labels = [lo for lo in label_options if re.search(user_response_altered, lo)]
    else:
        selected_labels = [label_options[int(user_response)-1] if user_response.isdigit() else user_response]
    if len(selected_labels) == 0:
        raise Exception("Uh oh! No releases were found based on your input ({0}).".format(user_response))
    selected_releases = filter_on_label(selected_releases, selected_labels)

    return selected_releases

def get_selected_toolboxes(selected_releases_tools, tool = None, quiet = False):
    """Return a dictionary where the keys are the selected tools and the values are lists of selected releases."""
    tool_options = get_tools(selected_releases_tools)
    user_response = ""
    if tool is None:
        print("Select a tool. You can enter the tool index or the name of the tool. " \
              "To select multiple tools use a comma separated list.")
        if not quiet:
            print_list(tool_options,"tool")
        user_responses = six.moves.input('--> ')
        print()
    else:
        user_responses = tool
    user_responses = user_responses.replace(' ','').split(',')
    selected_toolboxes = {}
    for user_response in user_responses:
        if user_response.isdigit() and (int(user_response) > len(tool_options) or int(user_response) < 0):
            raise Exception("The response was out of bounds. You must enter a listed value.\n")
        if not user_response.isdigit() and user_response not in tool_options:
            raise Exception("The response was not in the list of acceptable tools.\n")
        selected_tool = tool_options[int(user_response)-1] if user_response.isdigit() else user_response
        if not selected_tool in selected_toolboxes.keys():
            selected_toolboxes[selected_tool] = filter_on_tool(selected_releases_tools, selected_tool)
        else:
            selected_toolboxes[selected_tool].extend(filter_on_tool(selected_releases_tools, selected_tool))

    return selected_toolboxes

def get_tool_information(tool_name, toolbox):
    """Gather the tool information from the various releases in a Toolbox and use it to create and return a Tool."""
    config_paths = [t.Path + tool_name + '.xml' for t in toolbox]
    versions = []
    paths = []
    for config_path in config_paths:
        # Skip paths that don't exist. These should already be filtered out by now, but just in case ...
        if not os.path.exists(config_path):
            print("Warning! The configuration path {0} does not exist. It will be skipped.".format(config_path))
            continue
        tree = ET.parse(config_path)
        root = tree.getroot()
        versions.append(root.attrib['version'])
        path = ""
        for child in root:
            if child.tag == "client":
                for child2 in child:
                    if child2.tag == "environment" and "BASE" in child2.attrib['name']:
                        path = child2.attrib['default']
                        break
        paths.append(path)

    return Tool(tool_name, config_paths, paths, versions,
                [t.Release.architecture for t in toolbox],
                [t.Release.label for t in toolbox])

def get_tools(toolbox_list):
    """Return a sorted list of Tools from a list of Toolboxes."""
    tools = []
    for toolbox in toolbox_list:
        for tool in toolbox.Tools:
            if tool not in tools:
                tools.append(tool)
    return sorted(tools)

def get_tools_for_selected_releases(paths_to_toollists, selected_releases):
    """Returns a list of the tools contained in the selected releases.
    The input is a list of all the paths to all of the tools in all of the selected releases.
    """
    selected_releases_tools = []
    skipped_paths = []
    for ipath, path in enumerate(paths_to_toollists):
        if not os.path.exists(path):
            skipped_paths.append(path)
            continue
        tools = os.listdir(path)
        tools = [t.replace('.xml','') for t in tools]
        selected_releases_tools.append(Toolbox(selected_releases[ipath], tools, path))
    if len(skipped_paths) > 0:
        print("\nWARNING! The following configuration paths do not exist and were skipped.")
    for skipped_path in skipped_paths:
        print("\t" + skipped_path)

    return selected_releases_tools

def parse_map_lines(lines):
    """Parse the release map and return a list of Releases."""
    relmap = []
    for line in lines:
        line_list = process_map_line(line.decode('utf-8'))
        if filter_on_branch_name(line_list[1]):
            continue
        relmap.append(Release._make(line_list))
    return relmap

def parse_release_map(source=MapSource.GITHUB):
    """Find the release map from the best source and then call 'parse_map_lines' to run the map
    into the list of Releases to return.
    """
    relmap = []

    if source in [MapSource.GITHUB, MapSource.CMSSDT]:
        url = ""
        if source == MapSource.GITHUB:
            url = "https://raw.githubusercontent.com/cms-sw/cms-bot/master/releases.map"
        else:
            url = "https://cmssdt.cern.ch/SDT/releases.map"
        # pylint: disable=protected-access
        ssl._create_default_https_context = ssl._create_unverified_context
        contents = ""
        with six.moves.urllib.request.urlopen(url) as file:
            contents = file.read()
        contents = contents.split(b'\n')[:-1]
        relmap = parse_map_lines(contents)
    elif source == MapSource.CVMFS:
        with open("/cvmfs/cms.cern.ch/releases.map", mode='r', encoding='utf-8') as release_map:
            relmap = parse_map_lines(release_map)
    else:
        raise Exception("Unknown source for the architecture/release map.\n")

    return relmap

def print_list(the_list, entry_type='item'):
    """Print a formated list of items."""
    print("The " + entry_type + " choices are listed below.")
    for i, item in enumerate(the_list, 1):
        print('{0:{width}}'.format(i, width=len(str(len(the_list)))), '. ' + item, sep='',end='\n')

def process_map_line(line):
    """Process a single line of the release map, turning it into a list of useful information chunks."""
    line_split = line.strip().split(';')[:-1]
    line_split = [x.split('=')[1] for x in line_split]
    return [int(x) if x.isdigit() else x for x in line_split]

def print_selection(topline, selected_list = None):
    """Print a topline of information and then an indented list of selected items."""
    if selected_list is None:
        selected_list = []

    print(topline)
    for selected in selected_list:
        print('\t{0}'.format(selected))
    print("")

def print_tool_information(tool):
    """Print the final table of Tool information to STDOUT."""
    headers = ["SCRAM_ARCH","Release","Version","ConfigPath","Location"]
    min_widths = [len(max(tool.Architectures, key=len)),
                  len(max(tool.Releases, key=len)),
                  len(max(tool.Versions, key=len)),
                  len(max(tool.ConfigPaths, key=len)),
                  len(max(tool.Locations, key=len))]
    min_widths = [max(len(headers[i]), m) for i, m in enumerate(min_widths)]
    pattern = "| {0:^{5}s} | {1:^{6}s} | {2:^{7}s} | {3:^{8}s} | {4:^{9}s} |"
    print("The following is a summary of the information for the tool \'{0}\':".format(tool.Name))
    print(pattern.format(*(headers + min_widths)))
    print(pattern.format(*(['-'*width for width in min_widths] + min_widths)))
    pattern = pattern.replace("^","<")
    for index, _ in enumerate(tool.Locations):
        print(pattern.format(tool.Architectures[index],
                             tool.Releases[index],
                             tool.Versions[index],
                             tool.ConfigPaths[index],
                             tool.Locations[index],*min_widths))
    print('\n')

def toolgenie(architecture = None, cmssw = None, tool = None, quiet = False, source = MapSource.GITHUB):
    """The main function for this module. It is responsible for coordinating the overall logic."""

    # Get the initial release map from CVMFS/GITHUB/CMSSDT
    relmap = parse_release_map(source)

    # Select a SCRAM architecture or a set of architectures
    # The full list is taken from the list of Releases (the release map)
    selected_architectures, user_response = get_selected_architectures(relmap = relmap,
                                                                       architecture = architecture,
                                                                       quiet = quiet)

    # Print the selected architectures so that the user know what they did
    print_selection(f"Based on your input ({user_response}), the selected SCRAM architectures are:", selected_architectures)

    # Filter the release map (list of Releases) based on the selected architectures
    selected_releases = filter_on_architecture(relmap, selected_architectures)

    # Select a CMSSW release or set of released based upon the CMSSW label
    selected_releases = get_selected_releases(selected_releases = selected_releases, cmssw = cmssw, quiet = quiet)

    # Print the selected release(s) so that the user knows what they did
    print_selection("You selected the release(s):", selected_releases)

    # Get all paths to the tool configuration files
    paths_to_toollists = []
    for selected_release in selected_releases:
        paths_to_toollists.append('/cvmfs/cms.cern.ch/' + selected_release.architecture + '/cms/' +
                                  ('cmssw-patch/' if 'patch' in selected_release.label else 'cmssw/') +
                                  selected_release.label + '/config/toolbox/' + selected_release.architecture +
                                  '/tools/selected/')

    # Get a dictionary of tools and their associated configuration paths
    selected_releases_tools = get_tools_for_selected_releases(paths_to_toollists, selected_releases)

    # Make a unique list of tools and filter based on the selected tool
    selected_toolboxes = get_selected_toolboxes(selected_releases_tools, tool = tool, quiet = quiet)

    # Print the selected tool(s) so that the user know what they did
    print_selection("You selected the tools(s):", selected_toolboxes)

    # Gather the tool information from the various releases
    tools = []
    for key, value in selected_toolboxes.items():
        tools.append(get_tool_information(tool_name = key, toolbox = value))

        # Print the information for a given tool
        if len(tools) > 0:
            print_tool_information(tools[-1])

    return tools

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""
Get some information about the tool(s) in a given CMSSW release or set of releases.

This tool works for both python2 and python3.

Dependencies:
=============
  - Must already have mounted /cvmfs/cms.cern.ch

Examples of how to run:
=======================
python toolgenie.py --help
python toolgenie.py
python toolgenie.py slc7_.* 1 1
""",
                                     epilog="",
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("architecture", metavar='arch', nargs='?', default=None,
                        help="The architecture(s) to look at. Can be a regex, " \
                        "a single architecture, or if known, the index of " \
                        "the architecture from the list of all architectures. " \
                        "(default = %(default)s)")
    parser.add_argument("cmssw", metavar='cmssw', nargs='?', default=None,
                        help="The CMSSW release(s) to look at. Can be a regex, " \
                        "a single CMSSW release, or if known, the index of " \
                        "the CMSSW release from the list of all of the releases. " \
                        "(default = %(default)s)")
    parser.add_argument("tool", metavar='tool', nargs='?', default=None,
                        help="The tool(s) for which to compile the table of information. " \
                        "You can enter the tool index or the name of the tool. " \
                        "To select multiple tools use a comma separated list." \
                        "(default = %(default)s)")
    parser.add_argument("-q", "--quiet", default=False, action="store_true",
                        help="Limit the number of printouts (default = %(default)s)")
    parser.add_argument("-s", "--source", default=MapSource.GITHUB, type=MapSource, choices=list(MapSource),
                        help="Specify the source of the release map (default= %(default)s)")

    args = parser.parse_args()

    toolgenie(**vars(args))
