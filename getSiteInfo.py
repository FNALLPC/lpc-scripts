#!/usr/bin/env python3
from __future__ import absolute_import
import argparse
from collections import namedtuple
import errno
import fnmatch
import getopt
import json
import os
import pycurl
import shlex
from StringIO import StringIO
import subprocess
import sys
import traceback

siteDBDict = {
#   alias:               (local_redirector,          'xrootd_endpoint',                     'local_path_to_store')
    'CERNBox'          : ('',                        'eosuser-internal.cern.ch',            '/eos/user/<u>/<username>/'),
    'T1_US_FNAL'       : ('cmsxrootd-site.fnal.gov', '' ,                                   ''),
    'T2_CH_CERN'       : ('',                        '',                                    ''),
    'T2_US_Vanderbilt' : ('',                        'root://xrootd.accre.vanderbilt.edu/', '/lio/lfs/cms/'),
    'T3_US_FNALLPC'    : ('',                        '',                                    '/eos/uscms/'),
    'T3_US_TAMU'       : ('',                        '',                                    '/fdata/hepx/'),
    'T3_US_UMD'        : ('',                        '',                                    '/mnt/hadoop/cms/')
}

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

class Pledge(namedtuple('Pledge', 'pledge_date quarter cpu disk_store tape_store local_store')):
     __slots__ = ()
     def __str__(self):
         return '%10.1f %4i %f %f %f %s' % (self.pledge_date, self.quarter, self.cpu, self.disk_store, self.tape_store, self.local_store)

class Responsibility(namedtuple('Responsibility', 'username role email')):
     __slots__ = ()
     def __str__(self):
         return '%s %s %s' % (self.username, self.role, self.email)

class Site(object):
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
        return "%s(%r)" % (self.__class__.__name__, self.alias)

    def __str__(self,fast):
        ret =  "Site Information:\n"

        members = [attr for attr in dir(self) if not callable(getattr(self, attr)) and not attr.startswith("__") and not attr.startswith("_Site__")]
        for m in members:
            description = ' '.join(m.split('_'))
            if description not in self.__do_not_cap:
                description = description.capitalize()
            for k,v in self.__cap_rule.iteritems():
                description = description.replace(k,v)
            if not fast and m in self.__fast_fields.keys():
                if self.__fast_fields[m] != None:
                    ret += "\t"+description+": "+str(self.__fast_fields[m]._fields)+"\n"
                    for item in eval("self.%s"%m):
                        ret += "\t\t"+str(item)+"\n"
                else:
                    ret += "\t"+description+": "+str(eval("self.%s"%m))+"\n"
            else:
                ret += "\t"+description+": "+str(eval("self.%s"%m))+"\n"
        return ret

    def create_xrootd_endpoint(self):
        self.xrootd_endpoint = "root://%s/" % (self.fqdn)

def run_checks(quiet):
    if not quiet: print("Running sanity checks before proceeding ...")

    #check the python version
    min_python_version = (2,7,11)
    if sys.version_info < min_python_version:
        raise RuntimeError("Must be using Python %s.%s.%s or higher. " \
                           "Try running getPythonVersions.py to get a list of standalone python versions." % min_python_version)

    #check for a grid proxy
    with open(os.devnull, 'wb') as devnull:
        process = subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'), stdout=devnull, stderr=subprocess.STDOUT)
        returncode = process.wait()
        if returncode!=0 :
            print("\tWARNING::You must have a valid proxy for this script to work.\nRunning \"voms-proxy-init -voms cms\"...\n")
            subprocess.call("voms-proxy-init -voms cms -valid 192:00", shell=True)
            process = subprocess.Popen(shlex.split('voms-proxy-info -exists -valid 0:10'), stdout=devnull, stderr=subprocess.STDOUT)
            returncode = process.wait()
            if returncode!=0:
                raise RuntimeError("Sorry, but I still could not find your proxy.\nWithout a valid proxy, this program will fail spectacularly.\nThe program will now exit.")

    return os.environ['X509_USER_PROXY']

def getCurlInfo(url):
    buffer = StringIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(pycurl.HTTPGET, 1)
    c.setopt(pycurl.SSL_VERIFYPEER, 0) #Set to 0 and not 1 because CERN certs are self signed
    c.setopt(pycurl.SSL_VERIFYHOST, 2)
    c.setopt(pycurl.SSLKEY, os.environ['X509_USER_PROXY'])
    c.setopt(pycurl.SSLCERT, os.environ['X509_USER_PROXY'])
    c.setopt(pycurl.CAINFO, '/etc/grid-security/certificates')
    c.setopt(pycurl.FOLLOWLOCATION, 1)
    c.setopt(c.WRITEFUNCTION, buffer.write)
    c.perform()
    c.close()
    return buffer.getvalue()

def findFacilityFromAlias(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-names')
    if debug: print("getSiteInfo::findFacilityFromAlias()")
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<6: continue
        current_alias = ibody.split('"')[5]
        if debug: print("\t",ibody," current_alias:", current_alias)
        if current_alias == site.alias:
            site.facility = ibody.split('"')[3]
            site.types.append(ibody.split('"')[1])

def findSEInfo(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-resources')
    if debug: print("getSiteInfo::findSEInfo()")
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<8: continue
        current_site = ibody.split('"')[1]
        if debug: print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            site.element_type = ibody.split('"')[3]
            site.fqdn = ibody.split('"')[5]
            site.is_primary = bool(ibody.split('"')[7])

def getSiteAssociations(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-associations')
    if debug: print("getSiteInfo::getSiteAssociations()")
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<5: continue
        current_parent = ibody.split('"')[1]
        current_child = ibody.split('"')[3]
        if debug: print("\t",ibody," current_parent:", current_parent," current_child:", current_child)
        if current_parent == site.facility:
            site.child_sites.append(ibody.split('"')[3])
        if current_child == site.facility:
            site.parent_site = ibody.split('"')[1]
    if site.parent_site == "":
        site.parent_site = "None"

def getPledges(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/resource-pledges')
    if debug: print("getSiteInfo::getPledges()")
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<3: continue
        current_site = ibody.split('"')[1]
        if debug: print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            pledge_list = ibody.split('"')[2].split(",")
            local_store = float(pledge_list[6].split(']')[0]) if is_number(pledge_list[6].split(']')[0]) else "null"
            site.pledges.append(Pledge(float(pledge_list[1]),int(pledge_list[2]),float(pledge_list[3]),float(pledge_list[4]),float(pledge_list[5]),local_store))

def getSiteResponsibilities(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-responsibilities')
    if debug: print("getSiteInfo::getSiteResponsibilities()")
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<6: continue
        current_site = ibody.split('"')[3]
        if debug: print("\t",ibody," current_site:", current_site)
        if current_site == site.facility:
            site.responsibilities.append(Responsibility(ibody.split('"')[1],ibody.split('"')[5],""))

def getLFNAndPFNFromPhEDEx(site, debug = False):
    jstr = getCurlInfo('https://cmsweb.cern.ch/phedex/datasvc/json/prod/lfn2pfn?node='+site.alias+'&lfn=/store/user&protocol=srmv2')
    if debug: print("getSiteInfo::getPDNFromPhEDEx()")
    try:
        result = json.loads(jstr)
        site.lfn = result['phedex']['mapping'][0]['lfn']
        site.pfn = result['phedex']['mapping'][0]['pfn']
    except:
        print("Unable to get the LFN and PFN for", site.alias, "from PhEDEx")
        print(jstr)
        if debug: raise RuntimeError(traceback.format_exc()) 
        site.lfn = "None"
        site.pfn = "None"


def addInformationNotInSiteDB(site, debug = False):
    if site.alias in siteDBDict:
        site.local_redirector    = siteDBDict[site.alias][0] if siteDBDict[site.alias][0]!='' else "None"
        site.local_path_to_store = siteDBDict[site.alias][2] if siteDBDict[site.alias][2]!='' else "None"
        site.gsiftp_endpoint     = site.pfn
        site.xrootd_endpoint = siteDBDict[site.alias][1]

    if site.xrootd_endpoint == '':
        site.create_xrootd_endpoint()


def getSiteInfo(site_alias="", site=None, cric=False, debug=False, fast=False, print_json=False, quiet=False):
    if site == None:
        site = Site(site_alias)
    run_checks(quiet)

    # most of this information is from SiteDB, but the LFN and PFN strings are from PhEDEx
    if not cric:
        findFacilityFromAlias(site, debug)
        findSEInfo(site, debug)
        getLFNAndPFNFromPhEDEx(site, debug)
        if not fast:
            getSiteAssociations(site, debug)
            getPledges(site, debug)
            getSiteResponsibilities(site, debug)
    else:
        jstr = getCurlInfo('https://cms-cric.cern.ch/api/cms/site/query/?json&name='+site.alias)
        data = json.loads(jstr)[site.alias]
        site.facility = data['facility']

        jstr = getCurlInfo('https://cms-cric.cern.ch/api/cms/glideinentry/query/list/?json&site='+site.alias)
        if print_json:
            print(jstr)
        key, data = json.loads(jstr).popitem()
        site.job_manager = data['queues'][0]['ce_jobmanager']
        site.responsibilities.append(Responsibility("<Unknown>","Site Admin Contact",data['computeunits'][0]['site_admin_contacts']))


    # add the information stored in the dictionary defined at the top
    addInformationNotInSiteDB(site, debug)
    
    # print the site information to the console
    if not quiet and not print_json: print(site.__str__(fast))
    
    return site

if __name__ == '__main__':
    #program name available through the %(prog)s command
    parser = argparse.ArgumentParser(description="""Access SiteDB and PhEDEx to retrieve a sites information.\n
                                     Information on how this information is obtained can be found at https://cms-http-group.web.cern.ch/cms-http-group/apidoc/sitedb/current/introduction.html\n
                                     Haven't yet implemented esp-credit (https://cmsweb.cern.ch/sitedb/data/prod/esp-credit)\n
                                     or parsed together the federations (https://cmsweb.cern.ch/sitedb/data/prod/federations), the\n
                                     federation sites (https://cmsweb.cern.ch/sitedb/data/prod/federations-sites), and the
                                     federation pledges (https://cmsweb.cern.ch/sitedb/data/prod/federations-pledges).""",
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

    if(args.debug):
         print('Number of arguments:', len(sys.argv), 'arguments.')
         print('Argument List:', str(sys.argv))
         print("Argument ", args)
    
    getSiteInfo(**vars(args))


