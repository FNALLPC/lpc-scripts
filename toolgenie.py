#!/usr/bin/env python
from __future__ import print_function
from collections import namedtuple
import argparse, os, re, readline
import xml.etree.ElementTree as ET

# https://stackoverflow.com/questions/21731043/use-of-input-raw-input-in-python-2-and-3
# Bind raw_input to input in Python 2.
try:
    input = raw_input
except NameError:
    pass

class CMSSW(namedtuple('CMSSW', 'type major mid minor extra note')):
    __slots__ = ()
    def __eq__(self,type,major,mid,minor,extra,note):
        return self.type == type and self.major == major and self.mid == mid and self.minor == minor and self.extra == extra and self.note == note
CMSSW.__new__.__defaults__ = ("",) * len(CMSSW._fields)

class Release(namedtuple('Release', 'architecture label type state prodarch')):
    __slots__ = ()
    def __eq__(self, architecture, label):
        return self.architecture == architecture and self.label == label
    def getReleaseString(self):
        return "architecture=%s;label=%s;type=%s;state=%s;prodarch=%s;" % (self.architecture,self.label,self.type,self.state,self.prodarch)

class Toolbox(namedtuple('Toolbox',['Release','Tools','Path'])):
    __slots__ = ()

class Tool(namedtuple('Tool',['Name','ConfigPaths','Locations','Versions','Architectures','Releases'])):
    __slots__ = ()

def filter_on_architecture(release_map, architectures):
    return [release for release in release_map if any(architecture in release.architecture for architecture in architectures)]

def filter_on_label(release_map, labels):
    return [release for release in release_map if any(label in release.label for label in labels)]

def filter_on_tool(toolboxes, tool):
    return [tb for tb in toolboxes if tool in tb.Tools]

def get_architectures(release_map):
    archs = []
    for rel in release_map:
        if rel.architecture not in archs:
            archs.append(rel.architecture)
    return sorted(archs)

def get_labels(release_map):
    labels = []
    for rel in release_map:
        if rel.label not in labels:
            labels.append(rel.label)
    return sorted(labels,key=lambda label: CMSSW([int(x) if x.isdigit() else 999 if type(x)==str else x for ix,x in enumerate(label.split("_"))]))

def get_tools(toolbox_list):
    tools = []
    for toolbox in toolbox_list:
        for tool in toolbox.Tools:
            if tool not in tools:
                tools.append(tool)
    return sorted(tools)

def parse_release_map():
    relmap = []
    with open("/cvmfs/cms.cern.ch/releases.map",'r') as release_map:
        for line in release_map:
            line_list = process_map_line(line)
            # Skip releases listed in the map file who are named after branches. Typically these take the form 'CMSSW_#_#_X'. These entries tend to not have actual folders on CVMFS.
            if re.search("^(CMSSW)_[0-9]*_[0-9]*_[^0-9].*(?m)",line_list[1]):
                continue
            relmap.append(Release._make(line_list))
    return relmap

def print_list(l, type='item'):
    print("The " + type + " choices are listed below.")
    for i, item in enumerate(l,1):
        print('{0:{width}}'.format(i,width=len(str(len(l)))), '. ' + item, sep='',end='\n')

def process_map_line(line):
    line_split = line.strip().split(';')[:-1]
    line_split = [x.split('=')[1] for x in line_split]
    return [int(x) if x.isdigit() else x for x in line_split]

def toolgenie(architecture=None, cmssw=None, tool=None, quiet=False):
    # Get the initial release map from CVMFS
    relmap = parse_release_map()

    # Fileter on the SCRAM architecture
    architecture_options = get_architectures(relmap)
    user_response = ""
    if architecture == None:
        print("Select an architecture. For a single architecture selection, you can enter the item number or the name of the architecture. " \
              "To select multiple architectures, you can use a regex using the syntax \'r:<regex>\'.")
        if not quiet: print_list(architecture_options,"architecture")
        f = "{0:>12s} -- {1:<30s}\n"
        print("Example regex:\n"+f.format("r:.*","All architectures")+f.format("r:slc7.*","All slc7 releases"))
        user_response = input('--> ')
        print()
    else:
        user_response = architecture
    if user_response.isdigit() and (int(user_response) > len(architecture_options) or int(user_response) < 0):
        raise Exception("The response was out of bounds. You must enter a listed value.\n")
    if not user_response.isdigit() and not 'r:' in user_response and user_response not in architecture_options:
        raise Exception("The response was not in the list of acceptable scram architectures.\n")
    selected_architectures = []
    if 'r:' in user_response:
        user_response_altered = user_response[2:]
        selected_architectures = [ao for ao in architecture_options if re.search(user_response_altered,ao)]
    else:
        selected_architectures = [architecture_options[int(user_response)-1] if user_response.isdigit() else user_response]
    if len(selected_architectures) == 0:
        raise Exception("Uh oh! No architectures were found based on your input ({0}).".format(user_response))
    selected_releases = filter_on_architecture(relmap,selected_architectures)

    # Print the selected architectures so that the user know what they did
    print("Based on your input ({0}), the selected SCRAM architectures are:".format(user_response))
    for a in selected_architectures:
        print('\t{0}'.format(a))
    print()
    
    # Filter on the CMSSW label
    label_options = get_labels(selected_releases)
    if cmssw == None:
        print("Select a CMSSW release. For a single release, you can enter the item number or the name of the release. " \
              "To select multiple relases, you can use a regex using the syntax \'r:<regex>\'.")
        if not quiet: print_list(label_options,"release")
        f = "{0:>37s} -- {1:<50s}\n"
        print("Example regex:\n"+f.format("r:.*","All CMSSW releases for the previously selected architectures")+
              f.format("r:CMSSW_1._[0,6]_.*(?<!pre[0-9])$","All CMSSW releases with X=10-19, Y=0 or 6, Z=anything, and which aren't a pre release"))
        user_response = input('--> ')
        print()
    else:
        user_response = cmssw
    if user_response.isdigit() and (int(user_response) > len(label_options) or int(user_response) < 0):
        raise Exception("The response was out of bounds. You must enter a listed value.\n")
    if not user_response.isdigit() and not 'r:' in user_response and user_response not in label_options:
        raise Exception("The response was not in the list of acceptable CMSSW releases.\n")
    selected_labels = []
    if 'r:' in user_response:
        user_response_altered = user_response[2:]
        selected_labels = [lo for lo in label_options if re.search(user_response_altered,lo)]
    else:
        selected_labels = [label_options[int(user_response)-1] if user_response.isdigit() else user_response]
    if len(selected_labels) == 0:
        raise Exception("Uh oh! No releases were found based on your input ({0}).".format(user_response))
    selected_releases = filter_on_label(selected_releases,selected_labels)

    # Print the selected release(s) so that the user knows what they did
    print("You selected the release(s):")
    for r in selected_releases:
        print('\t{0}'.format(r))
    print()

    # Get all paths to the tool configuration files
    paths_to_toollists = []
    for r in selected_releases:
        paths_to_toollists.append('/cvmfs/cms.cern.ch/'+r.architecture+'/cms/'+('cmssw-patch/' if 'patch' in r.label else 'cmssw/')+r.label+'/config/toolbox/'+r.architecture+'/tools/selected/')

    # Get a dictionary of tools and their associated configuration paths
    selected_releases_tools = []
    skipped_paths = []
    for ipath, path in enumerate(paths_to_toollists):
        if not os.path.exists(path):
            skipped_paths.append(path)
            continue
        tools = os.listdir(path)
        tools = [t.replace('.xml','') for t in tools]
        selected_releases_tools.append(Toolbox(selected_releases[ipath],tools,path))
    if len(skipped_paths) > 0: print("\nWARNING! The following configuration paths do not exist and were skipped.")
    for p in skipped_paths:
        print("\t"+p)

    # Make a unique list of tools and filter based on the selected tool
    tool_options = get_tools(selected_releases_tools)
    if tool == None:
        print("Select a tool. You can enter the tool index or the name of the tool. To select multiple tools use a comma separated list.")
        if not quiet: print_list(tool_options,"tool")
        user_response = input('--> ')
        print()
    else:
        user_response = tool
    user_response = user_response.replace(' ','').split(',')
    selected_toolboxes = {}
    for ur in user_response:
        if ur.isdigit() and (int(ur) > len(tool_options) or int(ur) < 0):
            raise Exception("The response was out of bounds. You must enter a listed value.\n")
        if not ur.isdigit() and ur not in tool_options:
            raise Exception("The response was not in the list of acceptable CMSSW releases.\n")
        selected_tool = tool_options[int(ur)-1] if ur.isdigit() else ur
        if not selected_tool in selected_toolboxes.keys():
            selected_toolboxes[selected_tool] = filter_on_tool(selected_releases_tools,selected_tool)
        else:
            selected_toolboxes[selected_tool].extend(filter_on_tool(selected_releases_tools,selected_tool))

    # Gather the tool information from the various releases
    tools = []
    for key, value in selected_toolboxes.items():
        config_paths = [t.Path+key+'.xml' for t in selected_toolboxes[key]]
        versions = []
        paths = []
        for cp in config_paths:
            # Skip paths that don't exist. These should already be filtered out by now, but just in case ...
            if not os.path.exists(cp):
                print("Warning! The configuration path {0} does not exist. It will be skipped.".format(cp))
                continue
            tree = ET.parse(cp)
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
        current_tool = Tool(key,config_paths,paths,versions,[t.Release.architecture for t in selected_toolboxes[key]],[t.Release.label for t in selected_toolboxes[key]])
        tools.append(current_tool)

        # Print the information for a given tool
        headers = ["SCRAM_ARCH","Release","Version","ConfigPath","Location"]
        min_widths = [len(max(current_tool.Architectures, key=len)),len(max(current_tool.Releases, key=len)),len(max(current_tool.Versions, key=len)),len(max(current_tool.ConfigPaths, key=len)),len(max(current_tool.Locations, key=len))]
        min_widths = [max(len(headers[i]),m) for i,m in enumerate(min_widths)]
        f = "| {0:^{5}s} | {1:^{6}s} | {2:^{7}s} | {3:^{8}s} | {4:^{9}s} |"
        print("The following is a summary of the information for the tool \'{0}\':".format(current_tool.Name))
        print(f.format(*(headers+min_widths)))
        print(f.format(*(['-'*width for width in min_widths]+min_widths)))
        f = f.replace("^","<")
        for index, value in enumerate(current_tool.Locations):
            print(f.format(current_tool.Architectures[index],current_tool.Releases[index],current_tool.Versions[index],current_tool.ConfigPaths[index],current_tool.Locations[index],*min_widths))
        print('\n')

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
    parser.add_argument("architecture", metavar='arch', nargs='?', default=None, help="The architecture(s) to look at. Can be a regex, " \
                                                                                    "a single architecture, or if known, the index of " \
                                                                                    "the architecture from the list of all architectures. " \
                                                                                    "(default = %(default)s)")
    parser.add_argument("cmssw", metavar='cmssw', nargs='?', default=None, help="The CMSSW release(s) to look at. Can be a regex, " \
                                                                              "a single CMSSW release, or if known, the index of " \
                                                                              "the CMSSW release from the list of all of the releases. " \
                                                                              "(default = %(default)s)")
    parser.add_argument("tool", metavar='tool', nargs='?', default=None, help="The tool(s) for which to compile the table of information. " \
                                                                            "You can enter the tool index or the name of the tool. " \
                                                                            "To select multiple tools use a comma separated list." \
                                                                            "(default = %(default)s)")
    parser.add_argument("-q", "--quiet", default=False, action="store_true", help="Limit the number of printouts (default = %(default)s)")

    args = parser.parse_args()

    toolgenie(**vars(args))
