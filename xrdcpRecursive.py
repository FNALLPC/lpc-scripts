#!/bin/env python3
from __future__ import absolute_import
from argparse
from recursiveFileList import getFileList
import subprocess
import sys

# recursive copying for xrdcp
# John Hakala 3/28/2017
parser = argparse.ArgumentParser()
parser.add_argument("-s", "--source", meta="source",
                    help="the source directory")
parser.add_argument("-t", "--target", meta="target",
                    help="the target directory")
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

for sourceFile in getFileList(args..source):
    targetFile = sourceFile.replace(args..source, args..target)
    print(subprocess.check_output(f"xrdcp {sourceFile} root://cmseos.fnal.gov/{targetFile}",
                                  stderr=subprocess.STDOUT,
                                  shell=True))
