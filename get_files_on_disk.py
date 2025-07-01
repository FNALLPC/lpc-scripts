#!/usr/bin/env python3

"""Returns a list of files from a dataset including only files that are hosted on disk."""

import os,sys,getpass,warnings,glob,shlex,subprocess,argparse # pylint: disable=multiple-imports
from collections import defaultdict

# prevent this script from ever being used in a batch job
# to avoid DDOS of Rucio
if "_CONDOR_SCRATCH_DIR" in os.environ:
    print("Error: this script cannot be used in batch jobs")
    sys.exit(1)

def getOS():
    """Gets OS version from shell (other methods return host OS when in container)"""
    cmd = r"sed -nr 's/[^0-9]*([0-9]+).*/\1/p' /etc/redhat-release"
    osv = subprocess.check_output(shlex.split(cmd), encoding="utf-8").rstrip()
    return osv

def getRucio(user):
    """Adds Rucio libraries to python path with requisite environment variables"""
    osv = getOS()
    rucio_path = f'/cvmfs/cms.cern.ch/rucio/x86_64/rhel{osv}/py3/current'
    os.environ['RUCIO_HOME'] = rucio_path
    os.environ['RUCIO_ACCOUNT'] = user
    full_rucio_path = glob.glob(rucio_path+'/lib/python*.*')[0]
    sys.path.insert(0,full_rucio_path+'/site-packages/')

def getHosted(dataset, user, allow=None, block=None):
    """Gets list of files on disk for a dataset, and list of sites along with how many files each site has"""
    if allow is not None and block is not None:
        raise RuntimeError("Cannot specify both allow list and block list, pick one")

    getRucio(user)

    warnings.filterwarnings("ignore", message=".*cryptography.*")
    from rucio.client.client import Client # pylint: disable=import-error,import-outside-toplevel
    client = Client()

    # loop over blocks to avoid timeout error from too-large response
    all_blocks = list(client.list_content(scope='cms',name=dataset))
    # batch some blocks together for fewer requests
    # not fully optimized, but n=10 tested to be ~15% faster than n=1
    nblocks = 10
    block_groups = [all_blocks[i:i+nblocks] for i in range(0, len(all_blocks), nblocks)]

    from rucio.client.replicaclient import ReplicaClient # pylint: disable=import-error,import-outside-toplevel
    rep_client = ReplicaClient()

    filelist = set()
    sitelist = defaultdict(int)
    def sitecond(site):
        return ("_Tape" not in site) and (allow is None or site in allow) and (block is None or site not in block)
    for block_group in block_groups:
        reps = list(rep_client.list_replicas([{'scope': 'cms', 'name': block['name']} for block in block_group]))
        for rep in reps:
            for site,state in rep['states'].items():
                if state=='AVAILABLE' and sitecond(site):
                    filelist.add(rep['name'])
                    sitelist[site] += 1

    sys.path.pop(0)
    return filelist, sitelist

def main(dataset, user, outfile=None, verbose=False, allow=None, block=None):
    """Prints file list and site list"""
    filelist, sitelist = getHosted(dataset, user, allow=allow, block=block)

    if verbose:
        print("Site list:")
        print("\n".join(f'{k}: {v}' for k,v in sitelist.items()))

    file = open(outfile,'w') if outfile is not None else sys.stdout # pylint: disable=consider-using-with,unspecified-encoding
    print("\n".join(filelist), file=file)
    if outfile is not None: file.close() # pylint: disable=multiple-statements

if __name__=="__main__":
    default_user = getpass.getuser()
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Find all available files (those hosted on disk) for a given dataset"
    )
    site_args = parser.add_mutually_exclusive_group(required=False)
    site_args.add_argument("-a","--allow",type=str,default=None,nargs='*',help="allow only these sites")
    site_args.add_argument("-b","--block",type=str,default=None,nargs='*',help="block these sites")
    parser.add_argument("-o","--outfile",type=str,default=None,help="write to this file instead of stdout")
    parser.add_argument("-u","--user",type=str,default=default_user,help="username for rucio")
    parser.add_argument("-v","--verbose",default=False,action="store_true",help="print extra information (site list)")
    parser.add_argument("dataset",type=str,help="dataset to query")
    args = parser.parse_args()

    main(args.dataset, args.user, outfile=args.outfile, verbose=args.verbose, allow=args.allow, block=args.block)
