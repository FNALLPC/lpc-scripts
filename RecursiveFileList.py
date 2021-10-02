#!/bin/env python3

"""Print a map of the directory/file structure of a given base path.
The module will print out a full map in dictionary format, a list of the files with their full paths,
and a list of directories with their full paths. The module can be run using the following command:

python3 RecursiveFileList.py <path>

It can also be imported by another python program and used like:

#import RecursiveFileList
RecursiveFileList.map_dir("<path>")
RecursiveFileList.get_file_list("<path>")
RecursiveFileList.get_dir_list("<path>")

The 'map_dir' will return a dictionary while the other two functions will return lists.

Created by: John Hakala, 03/28/2017
Modified by: Alexx Perloff, 10/01/2021
"""

from __future__ import absolute_import
from os import path, listdir

def map_dir(prefix, directory):
    """Return a dictionary of all of the files and folders below 'directory'."""
    this_dir = path.join(prefix, directory)
    child_map = {}
    contents = []
    for child in listdir(this_dir):
        if path.isfile(path.join(this_dir, child)):
            contents.append(child)
        elif path.isdir(path.join(this_dir, child)):
            contents.append(map_dir(this_dir, child))
    child_map[directory] = contents
    return child_map

def make_file_list(prefix, dir_map):
    """Return a list of file paths below the top level path in 'dir_map'."""
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
    """Returns a list of directory paths below the top level path in 'dir_amp'."""
    dir_list = []
    for key in dir_map.keys():
        for child in dir_map[key]:
            if isinstance(child, dict):
                dir_list.append(path.join(prefix, path.join(key, list(child.keys())[0])))
                for sub_dir in make_dir_list(path.join(prefix, key), child):
                    dir_list.append(path.join(path.join(prefix, key), sub_dir))
    return dir_list

def get_file_list(dir_name):
    """Returns a list of file paths below the base path 'dir_name'.
    This function provides one level of indirection for making the dir_map
    needed by make_file_list.
    """
    return make_file_list(dir_name, map_dir(dir_name, dir_name))

def get_dir_list(dir_name):
    """Returns a list of directory paths below the base path 'dir_name'.
    This function provides one level of indirection for making the dir_map
    needed by make_dir_list.
    """
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
