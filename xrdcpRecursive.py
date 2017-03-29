from commands import getoutput
from recursiveFileList import getFileList, getDirList
from optparse import OptionParser

# recursive copying for xrdcp
# John Hakala 3/28/2017
parser = OptionParser()
parser.add_option("-s", "--source", dest="source",
                  help="the source directory"      )
parser.add_option("-t", "--target", dest="target",
                  help="the target directory"      )
(options, args) = parser.parse_args()

if options.source is None or options.target is None:
  print "Error: please define the source and target"
  parser.print_help()
  exit(1)

## Apparently this isn't needed on EOS: xrdcp will make any enclosing directories on eos
#for sourceDir in getDirList(options.source):
#  targetDir = sourceDir.replace(options.source, options.target)
#  print getoutput('eosmkdir %s' % targetDir)

for sourceFile in getFileList(options.source):
  targetFile = sourceFile.replace(options.source, options.target)
  print getoutput("xrdcp %s root://cmseos.fnal.gov/%s" % (sourceFile, targetFile))
