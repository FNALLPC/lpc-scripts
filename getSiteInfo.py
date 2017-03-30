#!/usr/bin/env python
import os, sys, getopt, argparse, fnmatch, errno, subprocess, tempfile, shlex, pycurl
from StringIO import StringIO
from collections import namedtuple

siteDBDict = {
#   alias: (local_redirector, 'xrootd_endpoint', 'local_path_to_store')
    'T1_US_FNAL'    : ('cmsxrootd-site.fnal.gov', '' ,                   ''),
    'T2_CH_CERN'    : ('',                        'eoscms.cern.ch',      ''),
    'T3_US_FNALLPC' : ('',                        'cmseos.fnal.gov',     '/eos/uscms/'),
    'T3_US_TAMU'    : ('',                        'srm.brazos.tamu.edu', '/fdata/hepx/')
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

class Responsibility(namedtuple('Responsibility', 'username role')):
     __slots__ = ()
     def __str__(self):
         return '%s %s' % (self.username, self.role)


class Site(object):
    """Class for storing OSG site information from SiteDB"""
    def __init__(self,alias):
        self.name = ""
        self.alias = alias
        self.types = []
        self.element_type = ""
        self.fqdn = ""
        self.local_redirector = ""
        self.xrootd_endpoint = ""
        self.local_path_to_store = ""
        self.is_primary = False
        self.parent_site = ""
        self.child_sites = []
        self.pledges = []
        self.responsibilities = []

    def print_site_info(self,fast):
        print "Site Information:"
        print "\tName:",self.name
        print "\tAlias:",self.alias
        print "\tTypes:",self.types
        print "\tElement Type:",self.element_type
        print "\tfqdn:",self.fqdn
        print "\tlocal_redirector:",self.local_redirector
        print "\txrootd_endpoint:",self.xrootd_endpoint
        print "\tlocal_path_to_store:",self.local_path_to_store
        print "\tis_primary:",self.is_primary
        if not fast:
            print "\tparent_site:",self.parent_site
            print "\tchild_sites:",self.child_sites
            print "\tPledges:",Pledge._fields
            for ipledge in self.pledges:
                print "\t\t",ipledge
            print "\tResponsibilities:",Responsibility._fields
            for iresp in self.responsibilities:
                print "\t\t",iresp

def run_checks(quiet):
    if not quiet: print "Running sanity checks before proceeding ..."

    with open(os.devnull, 'wb') as devnull:
        process = subprocess.Popen(['voms-proxy-info'], stdout=devnull, stderr=subprocess.STDOUT)
        returncode = process.wait()
        if returncode!=0 :
            print "\tWARNING::You must have a valid proxy for this script to work.\nRunning \"voms-proxy-init -voms cms\"...\n"
            subprocess.call("voms-proxy-init -voms cms -valid 192:00", shell=True)
            process = subprocess.Popen(['voms-proxy-info'], stdout=devnull, stderr=subprocess.STDOUT)
            returncode = process.wait()
            if returncode!=0 :
                print "\tERROR::Sorry, but I still could not find your proxy.\nWithout a valid proxy, this program will fail spectacularly.\nThe program will now exit." 
                sys.exit()

    return os.environ['X509_USER_PROXY']

def getCurlInfo(url):
    buffer = StringIO()
    c = pycurl.Curl()
    c.setopt(c.URL, url)
    c.setopt(pycurl.SSL_VERIFYPEER, 1)
    c.setopt(pycurl.SSL_VERIFYHOST, 2)
    c.setopt(pycurl.SSLKEY, X509_USER_PROXY)
    c.setopt(pycurl.SSLCERT, X509_USER_PROXY)
    c.setopt(c.WRITEDATA, buffer)
    c.perform()
    c.close()
    return buffer.getvalue()

def findNameFromAlias(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-names')
    if debug: print "getSiteInfo::findNameFromAlias()"
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<6: continue
        current_alias = ibody.split('"')[5]
        if debug: print "\t",ibody," current_alias:", current_alias
        if current_alias == site.alias:
            site.name = ibody.split('"')[3]
            site.types.append(ibody.split('"')[1])

def findSEInfo(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-resources')
    if debug: print "getSiteInfo::findSEInfo()"
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<8: continue
        current_site = ibody.split('"')[1]
        if debug: print "\t",ibody," current_site:", current_site
        if current_site == site.name:
            site.element_type = ibody.split('"')[3]
            site.fqdn = ibody.split('"')[5]
            site.is_primary = bool(ibody.split('"')[7])

def getSiteAssociations(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-associations')
    if debug: print "getSiteInfo::getSiteAssociations()"
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<5: continue
        current_parent = ibody.split('"')[1]
        current_child = ibody.split('"')[3]
        if debug: print "\t",ibody," current_parent:", current_parent," current_child:", current_child
        if current_parent == site.name:
            site.child_sites.append(ibody.split('"')[3])
        if current_child == site.name:
            site.parent_site = ibody.split('"')[1]
    if site.parent_site == "":
        site.parent_site = "None"

def getPledges(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/resource-pledges')
    if debug: print "getSiteInfo::getPledges()"
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<3: continue
        current_site = ibody.split('"')[1]
        if debug: print "\t",ibody," current_site:", current_site
        if current_site == site.name:
            pledge_list = ibody.split('"')[2].split(",")
            local_store = float(pledge_list[6].split(']')[0]) if is_number(pledge_list[6].split(']')[0]) else "null"
            site.pledges.append(Pledge(float(pledge_list[1]),int(pledge_list[2]),float(pledge_list[3]),float(pledge_list[4]),float(pledge_list[5]),local_store))

def getSiteResponsibilities(site, debug = False):
    body = getCurlInfo('https://cmsweb.cern.ch/sitedb/data/prod/site-responsibilities')
    if debug: print "getSiteInfo::getSiteResponsibilities()"
    for ibody in body.split('\n'):
        if len(ibody.split('"'))<6: continue
        current_site = ibody.split('"')[3]
        if debug: print "\t",ibody," current_site:", current_site
        if current_site == site.name:
            site.responsibilities.append(Responsibility(ibody.split('"')[1],ibody.split('"')[5]))

def addInformationNotInSiteDB(site):
    if site.alias in siteDBDict:
        site.local_redirector    = siteDBDict[site.alias][0] if siteDBDict[site.alias][0]!='' else "None"
        site.xrootd_endpoint     = siteDBDict[site.alias][1] if siteDBDict[site.alias][1]!='' else "None"
        site.local_path_to_store = siteDBDict[site.alias][2] if siteDBDict[site.alias][2]!='' else "None"

def getSiteInfo(site_alias,debug,fast,quiet):
    site = Site(site_alias)
    findNameFromAlias(site, debug)
    findSEInfo(site, debug)
    if not fast:
        getSiteAssociations(site, debug)
        getPledges(site, debug)
        getSiteResponsibilities(site, debug)
    addInformationNotInSiteDB(site)
    if not quiet: site.print_site_info(fast)
    return site

def main(site_alias,debug,fast,quiet):
    global X509_USER_PROXY
    X509_USER_PROXY = run_checks(quiet)
    return getSiteInfo(site_alias,debug,fast,quiet)

if __name__ == '__main__':
    #program name available through the %(prog)s command
    parser = argparse.ArgumentParser(description="""Access SiteDB to retrieve a sites information.\n
                                     Information on how this information is obtained can be found at https://cms-http-group.web.cern.ch/cms-http-group/apidoc/sitedb/current/introduction.html\n
                                     Haven't yet implemented esp-credit (https://cmsweb.cern.ch/sitedb/data/prod/esp-credit)\n
                                     or parsed together the federations (https://cmsweb.cern.ch/sitedb/data/prod/federations), the\n
                                     federation sites (https://cmsweb.cern.ch/sitedb/data/prod/federations-sites), and the
                                     federation pledges (https://cmsweb.cern.ch/sitedb/data/prod/federations-pledges).""",
                                     epilog="And those are the options available. Deal with it.")
    parser.add_argument("site_alias", help="The alias of the server whose information you want to retrieve")
    parser.add_argument("-d","--debug", help="Shows some extra information in order to debug this program", action="store_true")
    parser.add_argument("-f","--fast", help="Retrieves less information, but will run faster", action="store_true")
    parser.add_argument("-q","--quiet", help="Print the resulting information to stdout", action="store_true")
    parser.add_argument('--version', action='version', version='%(prog)s 1.0b')
    args = parser.parse_args()

    if(args.debug):
         print 'Number of arguments:', len(sys.argv), 'arguments.'
         print 'Argument List:', str(sys.argv)
         print "Argument ", args
    
    main(args.site_alias, args.debug, args.fast, args.quiet)



