#!/bin/env python3

"""This module will recursively xrdcp (XRootD copy) files from a local directory to a XRootD endpoint.

Created by: John Hakala, 03/28/2017
Modified by: Alexx Perloff, 10/02/2021
"""

from __future__ import absolute_import
import argparse
import subprocess
import sys
from RecursiveFileList import get_file_list

parser = argparse.ArgumentParser()
parser.add_argument("-r", "--redir", metavar = "redirector", default = "root://cmseos.fnal.gov/",
                    help = "the XRootD endpoint (default = %(default)s)")
parser.add_argument("-s", "--source", metavar = "source",
                    help = "the source directory")
parser.add_argument("-t", "--target", metavar = "target",
                    help = "the target directory")
args = parser.parse_args()

if args.source is None or args.target is None:
    print("Error: please define the source and target")
    parser.print_help()
    sys.exit(1)

## Apparently this isn't needed on EOS: xrdcp will make any enclosing directories on eos
#from recursiveFileList import getDirList
#for sourceDir in getDirList(args.source):
#  targetDir = sourceDir.replace(args..source, args..target)
#  print getoutput('eosmkdir %s' % targetDir)

for sourceFile in get_file_list(args.source):
    targetFile = sourceFile.replace(args.source, args.target)
    command = f"xrdcp {sourceFile} {args.redir}/{targetFile}"
    output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True)
    print(command)
    print(output.decode('utf-8'))
