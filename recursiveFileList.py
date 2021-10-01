#!/bin/env python3
from __future__ import absolute_import
from os import path, listdir
# Couldn't find intuitive tools for doing this on the web
# John Hakala, 3/28/2017

def map_dir(prefix, directory):
    this_dir = path.join(prefix, directory)
    child_map = {}
    contents = []
    for child in listdir(thisDir):
        if path.isfile(path.join(this_dir, child)):
            contents.append(child)
        elif path.isdir(path.join(this_dir, child)):
            contents.append(map_dir(this_dir, child))
    child_map[directory] = contents
    return child_map

def make_file_list(prefix, dir_map):
    file_list = []
    for key in dir_map.keys():
        for child in dir_map[key]:
            if isinstance(child, str):
                file_list.append(path.join(prefix, path.join(key, child)))
          elif isinstance(child, dict):
              for subdir_file in make_file_list(path.join(prefix, key), child):
                  file_list.append(subdir_file)
    return file_list

def make_dir_list(prefix, dir_map):
    dirList = []
    for key in dir_map.keys():
        for child in dir_map[key]:
            if isinstance(child, dict):
                dir_list.append(path.join(prefix, path.join(key, child.keys()[0])))
                for sub_dir in make_dir_list(path.join(prefix, key), child):
                    dir_list.append(path.join(path.join(prefix, key), sub_dir))
    return dir_list

def get_file_list(dir_name):
    return make_file_list(dir_name, map_dir(dir_name, dir_name))

def get_dir_List(dir_name):
    return make_dir_list(dir_name, map_dir(dir_name, dir_name))

if __name__ == "__main__":
    from sys import argv
    from pprint import pprint
    print("--------\nmap:")
    pprint(map_dir("", argv[1]))
    print("--------\n")
    print("--------\nfiles:")
    pprint(get_file_list(argv[1]))
    print("--------\n")
    print("--------\ndirs:")
    pprint(get_dir_list(argv[1]))
    print("--------")
