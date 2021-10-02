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
from ast import literal_eval
from collections import namedtuple
import json
import os
import shlex
from io import StringIO
import subprocess
import sys
import traceback
import pycurl

class SiteDBDictEntry(namedtuple('SiteDBDictEntry', 'local_redirector xrootd_endpoint local_path_to_store')):
    """Namedtuple used to store site information not contained in a database."""
    __slots__ = ()
    def __str__(self):
        return f"{self.local_redirector} {self.xrootd_endpoint} {self.local_path_to_store}"

siteDBDict = {
    'CERNBox' : SiteDBDictEntry("", 'eosuser-internal.cern.ch', '/eos/user/<u>/<username>/'),
    'T1_US_FNAL' : SiteDBDictEntry('cmsxrootd-site.fnal.gov', '' , ''),
    'T2_CH_CERN' : SiteDBDictEntry('', '', ''),
    'T2_US_Vanderbilt' : SiteDBDictEntry('', 'root://xrootd.accre.vanderbilt.edu/', '/lio/lfs/cms/'),
    'T3_US_FNALLPC' : SiteDBDictEntry('', '', '/eos/uscms/'),
    'T3_US_TAMU' : SiteDBDictEntry('', '', '/fdata/hepx/'),
    'T3_US_UMD' : SiteDBDictEntry('', '', '/mnt/hadoop/cms/')
}

def is_number(num):
    """Returns True if the argment can be converted to a float, otherwise return False."""
    try:
        float(num)
        return True
    except ValueError:
        return False

class Pledge(namedtuple('Pledge', 'pledge_date quarter cpu disk_store tape_store local_store')):
    """A namedtuple containing the pledge information for a given site."""
    __slots__ = ()
    def __str__(self):
        return f"{self.pledge_date:10.1f} {self.quarter:4i} {self.cpu:f} {self.disk_store:f} \
                 {self.tape_store:f} {self.local_store}"

class Responsibility(namedtuple('Responsibility', 'username role email')):
    """A namedtuple containing the information for the person responsible for a given site."""
    __slots__ = ()
    def __str__(self):
        return f"{self.username} {self.role} {self.email}"

class Site:
    """Class for storing OSG site information from SiteDB"""
    __do_not_cap = ["fqdn","lfn","pfn"]
    __cap_rule = {"Xrootd":"XRootD","Gsiftp":"gsiftp"}
    __fast_fields = {"parent_site":None,"child_sites":None,
                     "pledges":Pledge,"responsibilities":Responsibility}

    def __init__(self,alias):
        self.facility = ""
        self.alias = alias
        self.types = []
        self.element_type = ""
        self.fqdn = ""
        self.lfn = ""
        self.pfn = ""
        self.local_redirector = ""
        self.xrootd_endpoint = ""
        self.gsiftp_endpoint = ""
        self.local_path_to_store = ""
        self.job_manager = ""
        self.is_primary = False
        self.parent_site = ""
        self.child_sites = []
        self.pledges = []
        self.responsibilities = []

    def __repr__(self):
        return f"{self.__class__.__name__}(self.alias:%r)"

    def __str__(self, fast):
        ret =  "Site Information:\n"

        members = [attr for attr in dir(self) if not callable(getattr(self, attr)) and \
                    not attr.startswith("__") and \
                    not attr.startswith("_Site__")]
        for member in members:
            description = ' '.join(member.split('_'))
            if description not in self.__do_not_cap:
                description = description.capitalize()
            for key, value in self.__cap_rule.items():
                description = description.replace(key, value)
            if not fast and member in self.__fast_fields:
                if self.__fast_fields[member] is not None:
                    ret += "\t" + description + ": " + str(self.__fast_fields[member]._fields) + "\n"
                    for item in literal_eval(f"self.{member}"):
                        ret += "\t\t"+str(item)+"\n"
                else:
                    ret += "\t" + description + ": " + str(literal_eval(f"self.{member}")) + "\n"
            else:
                ret += "\t" + description + ": " + str(literal_eval(f"self.{member}")) + "\n"
        return ret

    def create_xrootd_endpoint(self):
        """Properly format and set the XRootD endpoint for the Site."""
        self.xrootd_endpoint = f"root://{self.fqdn}/"

def run_checks(quiet):
    """Does some basic sanity checks before proceeding with the rest of the module.
    This tries to head off problems that might occur later on.
    The checks include:
    1. Making sure the python executable being used meets the minimum requirements.
    2. Making sure the user has a valid grid proxy.
    """
    if not quiet:
        print("Running sanity checks before proceeding ...")

    #check the python version
    min_python_version = (3,0,0)
    if sys.version_info < min_python_version:
        raise RuntimeError(f"Must be using Python "
                           f"{min_python_version[0]}.{min_python_version[1]}.{min_python_version[2]} "
                           f"or higher. Try running getPythonVersions.py to get a list of standalone python versions.")

    #check for a grid proxy
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

def get_curl_info(url):
    """Setup and run a pycurl task for a given url."""
    buffer = StringIO()
    curl_object = pycurl.Curl()
    curl_object.setopt(curl_object.URL, url)
    curl_object.setopt(pycurl.HTTPGET, 1)
    curl_object.setopt(pycurl.SSL_VERIFYPEER, 0) #Set to 0 and not 1 because CERN certs are self signed
    curl_object.setopt(pycurl.SSL_VERIFYHOST, 2)
    curl_object.setopt(pycurl.SSLKEY, os.environ['X509_USER_PROXY'])
    curl_object.setopt(pycurl.SSLCERT, os.environ['X509_USER_PROXY'])
    curl_object.setopt(pycurl.CAINFO, '/etc/grid-security/certificates')
    curl_object.setopt(pycurl.FOLLOWLOCATION, 1)
    curl_object.setopt(curl_object.WRITEFUNCTION, buffer.write)
    curl_object.perform()
    curl_object.close()
    return buffer.getvalue()

def find_facility_from_alias(site, debug = False):
    """Get the facility information for a given Site."""
    body = get_curl_info('https://cmsweb.cern.ch/sitedb/data/prod/site-names')
    if debug:
        print("GetSiteInfo::find_facility_from_alias()")
    for ibody in body.split('\n'):
        if len(ibody.split('"')) < 6:
            continue
        current_alias = ibody.split('"')[5]
        if debug:
            print("\t",ibody," current_alias:", current_alias)
        if current_alias == site.alias:
            site.facility = ibody.split('"')[3]
            site.types.append(ibody.split('"')[1])

def find_se_info(site, debug = False):
    """Get the storage element information for a given Site."""
    body = get_curl_info('https://cmsweb.cern.ch/sitedb/data/prod/site-resources')
    if debug:
        print("GetSiteInfo::find_se_info()")
    for ibody in body.split('\n'):
        if len(ibody.split('"')) < 8:
            continue
        current_site = ibody.split('"')[1]
        if debug:
            print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            site.element_type = ibody.split('"')[3]
            site.fqdn = ibody.split('"')[5]
            site.is_primary = bool(ibody.split('"')[7])

def get_site_associations(site, debug = False):
    """Get the other sites associated to the given Site."""
    body = get_curl_info('https://cmsweb.cern.ch/sitedb/data/prod/site-associations')
    if debug:
        print("GetSiteInfo::get_site_associations()")
    for ibody in body.split('\n'):
        if len(ibody.split('"')) < 5:
            continue
        current_parent = ibody.split('"')[1]
        current_child = ibody.split('"')[3]
        if debug:
            print("\t",ibody," current_parent:", current_parent," current_child:", current_child)
        if current_parent == site.facility:
            site.child_sites.append(ibody.split('"')[3])
        if current_child == site.facility:
            site.parent_site = ibody.split('"')[1]
    if site.parent_site == "":
        site.parent_site = "None"

def get_pledges(site, debug = False):
    """Get the pledges make by a given Site."""
    body = get_curl_info('https://cmsweb.cern.ch/sitedb/data/prod/resource-pledges')
    if debug:
        print("GetSiteInfo::get_pledges()")
    for ibody in body.split('\n'):
        if len(ibody.split('"')) < 3:
            continue
        current_site = ibody.split('"')[1]
        if debug:
            print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            pledge_list = ibody.split('"')[2].split(",")
            local_store = float(pledge_list[6].split(']')[0]) if is_number(pledge_list[6].split(']')[0]) else "null"
            site.pledges.append(Pledge(float(pledge_list[1]),
                                       int(pledge_list[2]),
                                       float(pledge_list[3]),
                                       float(pledge_list[4]),
                                       float(pledge_list[5]),
                                       local_store))

def get_site_responsibilities(site, debug = False):
    """Get the responsibilities for a given Site."""
    body = get_curl_info('https://cmsweb.cern.ch/sitedb/data/prod/site-responsibilities')
    if debug:
        print("GetSiteInfo::get_site_responsibilities()")
    for ibody in body.split('\n'):
        if len(ibody.split('"')) < 6:
            continue
        current_site = ibody.split('"')[3]
        if debug:
            print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            site.responsibilities.append(Responsibility(ibody.split('"')[1],
                                                        ibody.split('"')[5],
                                                        ""))

def get_lfn_and_pfn_from_phedex(site, debug = False):
    """Get the LFN and PFN information from PhEDEx for a given Site."""
    jstr = get_curl_info('https://cmsweb.cern.ch/phedex/datasvc/json/prod/lfn2pfn?node=' +
                       site.alias +
                       '&lfn=/store/user&protocol=srmv2')
    if debug:
        print("GetSiteInfo::getPDNFromPhEDEx()")
    try:
        result = json.loads(jstr)
        site.lfn = result['phedex']['mapping'][0]['lfn']
        site.pfn = result['phedex']['mapping'][0]['pfn']
    except Exception as exception:
        print("Unable to get the LFN and PFN for", site.alias, "from PhEDEx")
        print(jstr)
        if debug:
            raise RuntimeError(traceback.format_exc()) from exception
        site.lfn = "None"
        site.pfn = "None"

def add_information_not_in_site_db(site):
    """Add information to the Site which is in the local dictionary and not contained online."""
    if site.alias in siteDBDict:
        site.local_redirector = siteDBDict[site.alias].local_redirector \
                                if siteDBDict[site.alias].local_redirector != '' else "None"
        site.local_path_to_store = siteDBDict[site.alias].local_path_to_store \
                                   if siteDBDict[site.alias].local_path_to_store != '' else "None"
        site.gsiftp_endpoint = site.pfn
        site.xrootd_endpoint = siteDBDict[site.alias].xrootd_endpoint

    if site.xrootd_endpoint == '':
        site.create_xrootd_endpoint()


def get_site_info(site_alias="", site=None, cric=False, debug=False, fast=False, print_json=False, quiet=False):
    """Main module function which coordinated the various information finding tasks."""
    if site is None:
        site = Site(site_alias)
    run_checks(quiet)

    # most of this information is from SiteDB, but the LFN and PFN strings are from PhEDEx
    if not cric:
        find_facility_from_alias(site, debug)
        find_se_info(site, debug)
        get_lfn_and_pfn_from_phedex(site, debug)
        if not fast:
            get_site_associations(site, debug)
            get_pledges(site, debug)
            get_site_responsibilities(site, debug)
    else:
        jstr = get_curl_info('https://cms-cric.cern.ch/api/cms/site/query/?json&name=' + site.alias)
        data = json.loads(jstr)[site.alias]
        site.facility = data['facility']

        jstr = get_curl_info('https://cms-cric.cern.ch/api/cms/glideinentry/query/list/?json&site=' + site.alias)
        if print_json:
            print(jstr)
        _, data = json.loads(jstr).popitem()
        site.job_manager = data['queues'][0]['ce_jobmanager']
        site.responsibilities.append(Responsibility("<Unknown>",
                                                    "Site Admin Contact",
                                                    data['computeunits'][0]['site_admin_contacts']))


    # add the information stored in the dictionary defined at the top
    add_information_not_in_site_db(site)

    # print the site information to the console
    if not quiet and not print_json:
        print(site.__str__(fast))

    return site

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="""Access SiteDB and PhEDEx to retrieve a sites information.\n
                                     Information on how this information is obtained can be found at 
                                     https://cms-http-group.web.cern.ch/cms-http-group/apidoc/sitedb/current/introduction.html\n
                                     Haven't yet implemented esp-credit 
                                     (https://cmsweb.cern.ch/sitedb/data/prod/esp-credit)\n
                                     or parsed together the federations 
                                     (https://cmsweb.cern.ch/sitedb/data/prod/federations), the\n
                                     federation sites 
                                     (https://cmsweb.cern.ch/sitedb/data/prod/federations-sites), and the
                                     federation pledges 
                                     (https://cmsweb.cern.ch/sitedb/data/prod/federations-pledges).""",
                                     epilog="And those are the options available. Deal with it.")
    parser.add_argument("site_alias",
                        help="The alias of the server whose information you want to retrieve")
    parser.add_argument("-c","--cric", action="store_true",
                        help="Gather site information from CRIC rather than SiteDB. " \
                        "This feature is currently experimental. (default=%(default)s)")
    parser.add_argument("-d","--debug", action="store_true",
                        help="Shows some extra information in order to debug this program (default=%(default)s)")
    parser.add_argument("-f","--fast", action="store_true",
                        help="Retrieves less information, but will run faster (default=%(default)s)")
    parser.add_argument("-j","--print_json", action="store_true",
                        help="Print the full site information from CRIC in JSON format. " \
                        "This feature is only available with the --cric option (default=%(default)s)")
    parser.add_argument("-q","--quiet", action="store_true",
                        help="Print the resulting information to stdout (default=%(default)s)")
    parser.add_argument('--version', action='version', version='%(prog)s v1.1')
    #Change to 2.0 (Franklin) when CRIC functionality complete.

    args = parser.parse_args()

    if args.debug:
        print('Number of arguments:', len(sys.argv), 'arguments.')
        print('Argument List:', str(sys.argv))
        print("Argument ", args)

    get_site_info(**vars(args))
