#!/usr/bin/env python3

"""
This module collects the available for a given computing site on the CMS side of the
Worldwide LHC Computing Grid (WLCG). The information for these sites is contained in
the CRIC and RUCIO databases. The idea for this module is that it will be faster for
users to get the information they need here than it would be to try to collect the
information by going to the online portals for CRIC or RUCIO. The information collected
can also be returned in a format easily used by other modules.
"""

from __future__ import absolute_import
import argparse
from collections import namedtuple, defaultdict
from enum import Enum
import json
import os
import shlex
import subprocess
import sys
import traceback
from urllib import request

class LocalDictEntry(namedtuple('LocalDictEntry', 'local_redirector xrootd_endpoint local_path_to_store')):
    """Namedtuple used to store site information not contained in a database."""
    __slots__ = ()
    def __str__(self):
        return f"{self.local_redirector} {self.xrootd_endpoint} {self.local_path_to_store}"

localDict = {
    'CERNBox' : LocalDictEntry("", 'eosuser-internal.cern.ch', '/eos/user/<u>/<username>/'),
    'T1_US_FNAL' : LocalDictEntry('cmsxrootd-site.fnal.gov', '' , ''),
    'T2_CH_CERN' : LocalDictEntry('', '', ''),
    'T2_US_Vanderbilt' : LocalDictEntry('', 'root://xrootd.accre.vanderbilt.edu/', '/lio/lfs/cms/'),
    'T3_US_FNALLPC' : LocalDictEntry('', '', '/eos/uscms/'),
    'T3_US_TAMU' : LocalDictEntry('', '', '/fdata/hepx/'),
    'T3_US_UMD' : LocalDictEntry('', '', '/mnt/hadoop/cms/')
}

def is_number(num):
    """Returns True if the argment can be converted to a float, otherwise return False."""
    try:
        float(num)
        return True
    except ValueError:
        return False

def get_json_info(url):
    """Open the page and deserialize the json content for a given url.
    The loading of the information is somewhat equivalent to the command:
    `curl -sS --capath /etc/grid-security/certificates/ <url>`

    This style of loading information was copied from:
    https://github.com/dmwm/CMSRucio/blob/cbffac994c253746511af7d5d7cf954665bc5026/src/CRIC_test.py
    """
    return json.load(request.urlopen(url))


class EndpointType(Enum):
    """Enum class containing endpoint types for grid sites. Some of the values are aliases for
    different capitalization schemes.
    """
    # pylint: disable=invalid-name
    FILE      = 0
    file      = 0
    XROOTD    = 1
    XRootD    = 1
    GSIFTP    = 2
    SRM       = 3
    SRMv2     = 4
    perfSONAR = 5
    ARCCE     = 6
    WebDAV    = 7
    Unknown   = 99

    @classmethod
    def has_member(cls, value):
        """Return True if the string, value, is a valid enum name (member of the class) and False otherwise."""
        return value in set(cls.__members__)

class Site:
    """Class for storing OSG site information from SiteDB"""
    def __init__(self, alias):
        self.alias = alias
        self.endpoints = defaultdict(set)
        self.facility = ""
        self.fts = []
        self.glidein_name = ""
        self.name = ""
        self.local_path_to_store = ""
        self.local_redirector = ""
        self.pfn = ""
        self.rse = ""
        self.state = ""
        self.status = ""
        self.type = ""
        self.vo_name = ""

    __do_not_cap = ["pfn"]
    __cap_rule = {"Fts":"FTS", "Glidein":"glidein", "Gsiftp":"gsiftp", "Rse":"RSE", "Vo":"VO"}

    def __repr__(self):
        return f"{self.__class__.__name__}({self.alias!r})"

    def __str__(self):
        ret =  "Site Information:\n"

        useful_members = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not \
                          attr.startswith("__") and not attr.startswith("_Site__")]
        for member in useful_members:
            description = ' '.join(member.split('_'))
            if description not in self.__do_not_cap:
                description = description.capitalize()
            for key, value in self.__cap_rule.items():
                description = description.replace(key, value)

            if member == "endpoints":
                ret += "\t" + description + ":\n"
                for key, value in getattr(self, member).items():
                    ret += "\t\t" + key.name + ": " + ", ".join(value) + "\n"
            else:
                ret += "\t" + description + ": " + str(getattr(self, member)) + "\n"
        return ret

    def get_cric_info(self, debug = False, print_json = False):
        """Get as much information as possible from the Computing Resource Information Catalog (CRIC).
        This catalog contains information about physical and CMS logical computing resources.
        the online web portal is at https://cms-cric.cern.ch/.
        """
        if debug:
            print("GetSiteInfo::Site::get_cric_info()")

        # Alternate Links:
        #   'https://cms-cric.cern.ch/api/cms/facility/query/list/?json&name=US_Colorado'+site.alias[2:]
        data = get_json_info('https://cms-cric.cern.ch/api/cms/site/query/list/?json&name=' + self.alias)
        try:
            if print_json:
                print(data)
            data = data[self.alias]
            self.facility = data['facility']
            self.name = data['name']
            self.state = data['state']
            self.status = data['status']
            self.vo_name = data['vo_name']
        except Exception as exc:
            if debug:
                raise RuntimeError(traceback.format_exc()) from exc

        data = get_json_info('https://cms-cric.cern.ch/api/cms/glideinentry/query/list/?json&site=' + self.alias)
        try:
            if print_json:
                print(data)
            if len(data) > 0:
                _, data = data.popitem()
                self.glidein_name = data['name']
        except RuntimeError as rterr:
            if debug:
                raise RuntimeError(traceback.format_exc()) from rterr
        except KeyError as keyerr:
            if debug:
                raise KeyError(traceback.format_exc()) from keyerr

        # Site information by tier
        #   https://cms-cric.cern.ch/api/cms/site/query/list/?json&tier_level=3

    def get_cmssst_endpoint(self, debug = False, print_json = False):
        """Get as much site endpoint information as possible from CMSSST, the online web portal for which is
        located at https://cmssst.web.cern.ch/cmssst/site_info/site_endpoints.json.
        """
        if debug:
            print("GetSiteInfo::Site::get_cmssst_endpoint()")
        result = get_json_info("http://cmssst.web.cern.ch/cmssst/site_info/site_endpoints.json")
        try:
            if print_json:
                print(result)
            selected_item = next((item for item in result['data'] if item["site"] == self.alias), None)
            if selected_item is not None:
                prefix = ''
                suffix = ''
                if selected_item['type'] == EndpointType.XROOTD.name:
                    prefix = 'root://'
                    suffix = '/'
                elif selected_item['type'] == EndpointType.SRM.name or selected_item['type'] == EndpointType.SRMv2.name:
                    prefix = 'srm://'
                    suffix = '/srm/managerv2?SFN='
                self.endpoints[EndpointType[selected_item['type'].replace('-','')]].add(prefix+selected_item['endpoint']+suffix)
        except Exception as exc:
            print("Unable to get the list of endpoints from http://cmssst.web.cern.ch")
            print(result)
            if debug:
                raise RuntimeError(traceback.format_exc()) from exc

    def get_siteconf_info(self, debug = False, max_endpoint_values_per_type = 9999, print_json = False):
        """Gather additional information from the storage.json files located at /cvmfs/cms.cern.ch/SITECONF.
        This feature requires that the /cvmfs/cms.cern.ch folder be mounted on the host. These files are also
        stored on GitLab at https://gitlab.cern.ch/SITECONF.
        """
        if debug:
            print("GetSiteInfo::Site::get_siteconf_endpoints()")
        try:
            with open(f'/cvmfs/cms.cern.ch/SITECONF/{self.alias}/storage.json', encoding = "utf-8") as file:
                data = json.load(file)[0]
                if print_json:
                    print(data)

                self.type = data["type"]
                self.rse = data["rse"]
                self.fts += data["fts"]

                for protocol in data["protocols"]:
                    if "prefix" not in protocol:
                        continue

                    protocol_name = "Unknown"
                    if EndpointType.has_member(protocol["protocol"]):
                        protocol_name = protocol["protocol"]

                    if EndpointType[protocol_name] in self.endpoints and \
                        len(self.endpoints[EndpointType[protocol_name]]) >= max_endpoint_values_per_type:
                        shortest_endpoint = min(self.endpoints[EndpointType[protocol_name]], key=len)
                        if len(shortest_endpoint) < len(protocol["prefix"]):
                            self.endpoints[EndpointType[protocol_name]].remove(shortest_endpoint)
                            self.endpoints[EndpointType[protocol_name]].add(protocol["prefix"])
                    else:
                        self.endpoints[EndpointType[protocol_name]].add(protocol["prefix"])
                    if protocol_name == EndpointType.SRMv2.name and "gsiftp://" in protocol["prefix"] and \
                        EndpointType.GSIFTP not in self.endpoints:
                        self.endpoints[EndpointType.GSIFTP].add(protocol["prefix"])
                    if EndpointType.GSIFTP in self.endpoints:
                        self.pfn = max(self.endpoints[EndpointType.GSIFTP], key=len)
        except Exception as exc:
            print(f"Unable to get a list of endpoints from /cvmfs/cms.cern.ch/SITECONF/{self.alias}/storage.json")
            if debug:
                raise RuntimeError(traceback.format_exc()) from exc

    def add_local_information(self):
        """Add information to the Site which is in the local dictionary and not contained online."""
        if self.alias in localDict:
            self.local_redirector = localDict[self.alias].local_redirector \
                                    if localDict[self.alias].local_redirector != '' else "None"
            self.local_path_to_store = localDict[self.alias].local_path_to_store \
                                       if localDict[self.alias].local_path_to_store != '' else "None"
            if localDict[self.alias].xrootd_endpoint != '':
                self.endpoints[EndpointType.XROOTD].add(localDict[self.alias].xrootd_endpoint)

    def print_shell_str(self, shell = None, env = False):
        """An alternate method for printing the site information. this method is capable of printing
        a subset of the information in a more compact, shell-friendly manner. It is also capable of
        formatting the information so that it is easier to export to the shell environment.
        """
        separator = "=" if env else " : "
        try:
            for item_name in shell:
                item = getattr(self, item_name)
                if isinstance(item, str):
                    print(f"{item_name}{separator}{str(item)}")
                else:
                    for i_subitem, subitem_name in enumerate(item):
                        subitem = None
                        if isinstance(item, list):
                            subitem = item[i_subitem]
                            print(f"{item_name}{separator if not env else '_'}{str(i_subitem)}{separator}{str(subitem)}")
                        else:
                            subitem = item[subitem_name]
                            print(f"{item_name}{separator if not env else '_'}{subitem_name.name}"
                                  f"{separator}{str(','.join(subitem))}")
        except Exception as exc:
            print("Unable to print the shell formatted information.\n"
                  "Double check that you have provided a valid list of information to print.\n"
                  "Use 'GetSiteInfo.py --help' to check the list of acceptable options.")
            raise RuntimeError(traceback.format_exc()) from exc

    def get_info_from_all_sources(self, debug = False, max_endpoint_values_per_type = 9999, print_json = False):
        """This function is a shortcut for gathering information from all available resources."""

        # Get information from CRIC
        self.get_cric_info(debug, print_json)

        # Get information from cmssst
        self.get_cmssst_endpoint(debug, print_json)

        # Get more endpoints from SITECONF
        self.get_siteconf_info(debug, max_endpoint_values_per_type, print_json)

        # add the information stored in the dictionary defined at the top
        self.add_local_information()

def run_checks(quiet):
    """Does some basic sanity checks before proceeding with the rest of the module.
    This tries to head off problems that might occur later on.
    The checks include:
    1. Making sure the python executable being used meets the minimum requirements.
    2. Making sure the user has a valid grid proxy.
    """
    if not quiet:
        print("Running sanity checks before proceeding ...")

    # check the python version
    min_python_version = (3,0,0)
    if sys.version_info < min_python_version:
        raise RuntimeError(f"Must be using Python "
                           f"{min_python_version[0]}.{min_python_version[1]}.{min_python_version[2]} "
                           f"or higher. Try running getPythonVersions.py to get a list of standalone python versions.")

    # check that the /cvmfs/cms.cern.ch/SITECONF/ directory exists.
    # needed by Site.get_siteconf_info(...)
    directory = "/cvmfs/cms.cern.ch/SITECONF/"
    if not os.path.exists(directory):
        raise RuntimeError(f"The directory {directory} is not mounted.")

    # check for a grid proxy
    with open(os.devnull, 'wb') as devnull:
        returncode = 0
        with subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'),
                                   stdout=devnull,
                                   stderr=subprocess.STDOUT) as process:
            returncode = process.wait()
        if returncode != 0 :
            print("\tWARNING::You must have a valid proxy for this script to work.\n" \
                  "Running \"voms-proxy-init -voms cms\"...\n")
            subprocess.call("voms-proxy-init -voms cms -valid 192:00",
                            shell=True)
            with subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'),
                                  stdout=devnull,
                                  stderr=subprocess.STDOUT) as process:
                returncode = process.wait()
            if returncode != 0:
                raise RuntimeError("Sorry, but I still could not find your proxy.\n" \
                                   "Without a valid proxy, this program will fail spectacularly.\n" \
                                   "The program will now exit.")

    return os.environ['X509_USER_PROXY']

def get_site_info(site_alias = "",
                  site = None,
                  debug = False,
                  env = False,
                  max_endpoint_values_per_type = 9999,
                  print_json = False,
                  quiet = False,
                  shell = None):
    """Main module function which coordinates the various information finding tasks and decides how to print the
    information to STDOUT.
    """
    run_checks(quiet|(shell is not None))

    if site is None:
        site = Site(site_alias)

    site.get_info_from_all_sources(debug, max_endpoint_values_per_type, print_json)

    # print the site information to the console
    if not quiet:
        if shell is not None and isinstance(shell, list):
            site.print_shell_str(shell, env)
        else:
            print(str(site))

    return site

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="""Access CRIC and PhEDEx to retrieve a sites information.""",
                                     epilog="""When the --shell option comes before the positional argument you need
                                     to add '--' (no quotes) before the positional argument.\n\n
                                     And those are the options available. Deal with it.""")
    parser.add_argument("site_alias",
                        help="The alias of the server whose information you want to retrieve")
    parser.add_argument("-d","--debug", action = "store_true",
                        help = "Shows some extra information in order to debug this program (default = %(default)s)")
    parser.add_argument("-e","--env", action = "store_true",
                        help = "Format the shell output in a way that the values can be easily set as environment \
                              variables (default = %(default)s")
    parser.add_argument("-j","--print_json", action = "store_true",
                        help = "Print the full site information from CRIC in JSON format. " \
                        "This feature is only available with the --cric option (default = %(default)s)")
    parser.add_argument("-m", "--max_endpoint_values_per_type", type = int, default = 9999,
                        help = "The maximum number of values to store per endpoint type (default = %(default)s)")
    parser.add_argument("-q","--quiet", action = "store_true",
                        help = "Print the resulting information to stdout (default = %(default)s)")
    parser.add_argument("-s","--shell",  default = None, nargs = '+',
                        choices = ['alias','endpoints','facility','fts','glidein_name','name','local_path_to_store',
                                 'local_redirector','pfn','rse','state','status','type','vo_name'],
                        help = "Print selected information in a shell friendly manner (default = %(default)s)")
    parser.add_argument('--version', action = 'version', version = '%(prog)s v2.0 (Franklin)')

    args = parser.parse_args()

    if args.debug:
        print('Number of arguments:', len(sys.argv), 'arguments.')
        print('Argument List:', str(sys.argv))
        print("Argument ", args)

    get_site_info(**vars(args))
