#!/bin/env python3
from __future__ import absolute_import`
from os import path, listdir
# Couldn't find intuitive tools for doing this on the web
# John Hakala, 3/28/2017

def mapDir(prefix, directory):
  thisDir = path.join(prefix, directory)
  childMap = {}
  contents = []
  for child in listdir(thisDir):
    if path.isfile(path.join(thisDir, child)):
      contents.append(child)
    elif path.isdir(path.join(thisDir, child)):
      contents.append(mapDir(thisDir, child))
  childMap[directory] = contents
  return childMap
  
def makeFileList(prefix, dirMap):
  fileList = []
  for key in dirMap.keys():
    for child in dirMap[key]:
      if type(child) is str:
        fileList.append(path.join(prefix, path.join(key, child)))
      elif type(child) is dict:
        for subdirFile in makeFileList(path.join(prefix, key), child):
          fileList.append(subdirFile)
  return fileList

def makeDirList(prefix, dirMap):
  dirList = []
  for key in dirMap.keys():
    for child in dirMap[key]:
      if type(child) is dict:
        dirList.append(path.join(prefix, path.join(key, child.keys()[0])))
        for subDir in makeDirList(path.join(prefix, key), child):
          dirList.append(path.join(path.join(prefix, key), subDir))
  return dirList
      
def getFileList(dirName):
  return makeFileList(dirName, mapDir(dirName, dirName))

def getDirList(dirName):
  return makeDirList(dirName, mapDir(dirName, dirName))

if __name__ == "__main__":
  from sys import argv
  from pprint import pprint
  print("--------\nmap:")
  pprint(mapDir("", argv[1]))
  print("--------\n")
  print("--------\nfiles:")
  pprint(getFileList(argv[1]))
  print("--------\n")
  print("--------\ndirs:")
  pprint(getDirList(argv[1]))
  print("--------")
