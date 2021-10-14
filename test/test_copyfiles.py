#!/bin/env python3

"""Use:
    Basic:
    ======
    python3 test_copyfiles.py

    More verbosity:
    ===============
    python3 test_copyfiles.py -v

    More buffer stdout:
    ===================
    python3 test_copyfiles.py -b

    Run a single test case:
    =========================
    python3 -m unittest TestCopyfilesMethods.test_local_local_file

    Run all test cases in class:
    ============================
    python3 -m unittest TestCopyfilesMethods

    Run a whole test module:
    ========================
    python3 -m unittest test_copyfiles
    or
    python3 -m unittest lpc-scripts/test_copyfiles.py

    Run using test dicovery:
    ========================
    python3 -m unittest discover
    or
    python3 -m unittest discover [--start-directory [DIRECTORY]] [--pattern [PATTERN]] [--top-level-directory [DIRECTORY]]
"""

from __future__ import absolute_import
import unittest
import os
import shlex
import shutil
import subprocess

# pylint: disable=no-self-use
# pylint: disable=consider-using-with
# pylint: disable=invalid-name
# pylint: disable=too-many-public-methods
class TestCopyfilesMethods(unittest.TestCase):
    """This is the subclass of unittest.TestCase as defined in https://docs.python.org/3/library/unittest.html.
    Each member function which is prefixed with 'test_' is a test case.
    This code is also compatible with pytest.
    """
    __local_working_path = "/uscms_data/d1/" + os.environ['USER'] + "/copyfiles_test/"
    __fromPaths = ["folderFrom1/fileFrom1.txt", "folderFrom1/fileFrom2.txt", "folderFrom2/fileFrom1.txt",
                   "folderFrom2/FolderFrom2.1/fileFrom1.txt", "folderFrom2/FolderFrom2.1/fileFrom2.txt",
                   "folderFrom2/FolderFrom2.2/fileFrom1.txt"]

    def touch(self, path):
        """Create an empty file and update its access time."""
        with open(path, mode='a', encoding='utf-8'):
            os.utime(path, None)

    def tree(self, startpath):
        """Find all of the files and directories below a basepath.
        These will then be formatted to form a directory tree.
        """
        if startpath[-1]=="/":
            startpath=startpath[:-1]

        for root, _, files in os.walk(startpath):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 4 * (level)
            if root == startpath:
                print(f"{indent}{root}/")
            else:
                print(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for file in files:
                print(f"{subindent}{file}")

    def setUp(self):
        """A method which will run some instructions before each test.
        The instructions below will create a set of local files which will be used to perform the tests.
        """
        for path in self.__fromPaths:
            path = self.__local_working_path + path
            try:
                basedir = os.path.dirname(path)
                if not os.path.exists(basedir):
                    os.makedirs(basedir)
                self.touch(path)
            except OSError:
                #print ("\tCreation of the file/directory %s failed" % path)
                continue
            else:
                #print ("\tSuccessfully created the file %s " % path)
                continue

    def tearDown(self):
        """A method which will run some instructions after each test.
        These instructions will remove the files created in the setUp method.
        """
        path = self.__local_working_path
        print("\nRemoving this file/folder tree:")
        self.tree(path)
        try:
            shutil.rmtree(path)
        except OSError:
            print(f"\nDeletion of the directory {path} failed")
        else:
            print(f"\nSuccessfully deleted the directory {path}")

    def local_file_exits(self, filename):
        """Check if a local path exists and if it is a regular file."""
        return os.path.isfile(filename)

    def remote_xrootd_file_exits(self, filename, redir = "root://cmseos.fnal.gov/", verbose = False):
        """Check if a remote, XRootD accessible file exists."""
        command = f"xrdfs {redir} stat -q IsReadable {filename}"
        returncode = 0
        with subprocess.Popen(command,
                                   shell=True,
                                   stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT) as process:
            output = process.communicate()[0]
            if verbose:
                print('\n'.join(output.decode('utf-8').splitlines()))
            returncode = process.returncode
        return returncode == 0

    def check_popen(self, process, files_that_must_exist, expected_file_counts = None, redir = "", verbose = False):
        """Check the results of a subprocess.Popen() command.
        This member function also has the ability to check for the existence of local and remote files and
        compare the resulting file counts to some user provided expectations.
        """
        output = process.communicate()[0]
        if verbose:
            print('\n'.join(output.decode('utf-8').splitlines()))
        returncode = process.returncode
        self.assertEqual(returncode, 0)
        for path in files_that_must_exist:
            if redir == "":
                path = self.__local_working_path + path
                self.assertTrue(self.local_file_exits(path), (f"Cannot find the file {path}"))
            else:
                self.assertTrue(self.remote_xrootd_file_exits(path, redir, verbose), (f"Cannot find the file {redir}{path}"))
        if expected_file_counts is not None:
            for path, expected_count in expected_file_counts.items():
                if redir == "":
                    path = self.__local_working_path + path
                    actual_count = len([name for name in os.listdir(path) if os.path.isfile(os.path.join(path, name))])
                    self.assertTrue(actual_count == expected_count, (f"The file count in folder {path} ({actual_count:d}) "
                                                                 f"doesn't match the expected count of {expected_count:d}"))
                else:
                    raise Exception("Remote file checking not yet implemented")

    def test_local_local_file(self):
        """Copy a single file from a local source to a local destination."""
        destination_directory = self.__local_working_path + "folderTo1/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        os.mkdir(destination_directory)
        command = 'python3 copyfiles.py local ' + self.__local_working_path + 'folderFrom1/fileFrom1.txt local ' + \
                  destination_directory + '/fileTo1.txt'
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["folderTo1/fileTo1.txt"])

    def test_local_local_folder(self):
        """Copy an entire folder from a local source to a local destination."""
        command = 'python3 copyfiles.py local ' + self.__local_working_path + 'folderFrom1/ local ' + \
                  self.__local_working_path + 'folderTo1/ -r'
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["folderTo1/fileFrom1.txt", "folderTo1/fileFrom2.txt"])

    def test_local_local_folder_contents(self):
        """Copy the contents  from a local source to a local destination."""
        destination_directory = self.__local_working_path + "folderTo1/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        os.mkdir(destination_directory)
        command = 'python3 copyfiles.py local ' + self.__local_working_path + 'folderFrom1/* local ' + \
                  self.__local_working_path + 'folderTo1/ -r'
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["folderTo1/fileFrom1.txt", "folderTo1/fileFrom2.txt"])

    def test_remote_local_xrootd_file(self):
        """Copy a single file from a remote source to a local destination using XRootD."""
        source_directory = "test/testing/2017/facilitators/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory}/Alexx_Perloff.jpg local "
                   f"{self.__local_working_path} -su cmsdas -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["Alexx_Perloff.jpg"])

    def test_remote_local_xrootd_contents(self):
        """Copy the contents of a directory from a remote source to a local destination using XRootD."""
        source_directory = "test/testing/2017/facilitators/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory} local "
                   f"{self.__local_working_path} -su cmsdas -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["Alexx_Perloff.jpg", "Kevin_Pedro.jpg", "Marguerite_Tonjes.png"])

    def test_remote_local_xrootd_contents_recursive(self):
        """Recursively copy the contents of a directory from a remote source to a local destination using XRootD."""
        source_directory = "test/testing/2017/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory} local "
                   f"{self.__local_working_path} -su cmsdas -p xrootd -r -i .tgz .root")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["facilitators/Alexx_Perloff.jpg", "long_exercises/MonoHiggsHZZ/print_yields.py"])

    def test_remote_local_xrootd_contents_recursive_diff(self):
        """Recursively copy the contents of a directory from a remote source to a local destination using XRootD.
        This method first checks to see if there are existing files at the destination and does not try to copy those again.
        """
        print("\nMaking some, but not all of the folders/files at the destination ...")
        destination_directory = self.__local_working_path + "facilitators"
        os.mkdir(destination_directory)
        open(destination_directory + "/Alexx_Perloff.jpg", 'a', encoding = 'utf-8').close()

        source_directory = "test/testing/2017/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory} local "
                   f"{self.__local_working_path} -su cmsdas -p xrootd -r -i .tgz .root --diff")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["facilitators/Alexx_Perloff.jpg", "long_exercises/MonoHiggsHZZ/print_yields.py"],
                         expected_file_counts = {"facilitators": 33, "long_exercises/MonoHiggsHZZ": 8})

    def test_remote_local_gfal_file(self):
        """Copy a single file from a remote source to a local destination using gfal."""
        source_directory = "test/testing/2017/facilitators/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory}/Alexx_Perloff.jpg local "
                   f"{self.__local_working_path} -su cmsdas -p gfal")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["Alexx_Perloff.jpg"])

    def test_remote_local_gfal_contents_recursive(self):
        """Recursively copy the contents of a directory from a remote source to a local destination using gfal."""
        source_directory = "test/testing/2017/facilitators/"
        command = (f"python3 copyfiles.py T3_US_FNALLPC {source_directory} local "
                   f"{self.__local_working_path} -su cmsdas -p gfal -r")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, ["Alexx_Perloff.jpg"], expected_file_counts = {"./": 33})

    def test_local_remote_xrootd_file(self):
        """Copy a single file from a local source to a remote destination using XRootD."""
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom1/fileFrom1.txt "
                   f"T3_US_FNALLPC copyfiles_test/folderTo1/ -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_file = f"{destination_directory}/folderTo1/fileFrom1.txt"
        self.check_popen(process, [destination_file], redir = "root://cmseos.fnal.gov/")

        print(f"\nRemoving the remote directory '{destination_directory}'")
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_file}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/folderTo1/"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_local_remote_xrootd_contents(self):
        """Copy the contents of a directory from a local source to a remote destination using XRootD."""
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom2/FolderFrom2.1/ "
                   f"T3_US_FNALLPC copyfiles_test/ -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/fileFrom2.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/", verbose = True)

        print(f"\nRemoving the remote directory '{destination_directory}'")
        for file in destination_files:
            command = f"xrdfs root://cmseos.fnal.gov/ rm {file}"
            process = subprocess.Popen(shlex.split(command),
                                       stdout = subprocess.PIPE,
                                       stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_local_remote_xrootd_contents_recursive(self):
        """Recursively the contents of a directory from a local source to a remote destination using XRootD."""
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom2/ "
                   f"T3_US_FNALLPC copyfiles_test/ -p xrootd -r")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom2.txt",
                             f"{destination_directory}/FolderFrom2.2/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print(f"\nRemoving the remote directory '{destination_directory}'")
        for file in destination_files:
            command = f"xrdfs root://cmseos.fnal.gov/ rm {file}"
            process = subprocess.Popen(shlex.split(command),
                                       stdout = subprocess.PIPE,
                                       stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/FolderFrom2.1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/FolderFrom2.2"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_local_remote_xrootd_contents_recursive_diff(self):
        """Recursively copy the contents of a directory from a local source to a remote destination using XRootD.
        This method first checks to see if there are existing files at the destination and does not try to copy those again.
        """
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over one file before the test command")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom2/ "
                   f"T3_US_FNALLPC copyfiles_test/ -p xrootd -r --diff")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom2.txt",
                             f"{destination_directory}/FolderFrom2.2/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print(f"\nRemoving the remote directory '{destination_directory}'")
        for file in destination_files:
            command = f"xrdfs root://cmseos.fnal.gov/ rm {file}"
            process = subprocess.Popen(shlex.split(command),
                                       stdout = subprocess.PIPE,
                                       stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/FolderFrom2.1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/FolderFrom2.2"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_local_remote_gfal_file(self):
        """Copy a single file from a local source to a remote destination using gfal."""
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom1/fileFrom1.txt "
                   f"T3_US_FNALLPC copyfiles_test/ -p gfal")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_file = f"{destination_directory}/fileFrom1.txt"
        self.check_popen(process, [destination_file], redir = "root://cmseos.fnal.gov/")

        print(f"\nRemoving the remote directory '{destination_directory}'")
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_local_remote_gfal_contents_recursive(self):
        """Recursively copy the contents of a directory from a local source to a remote destination using gfal."""
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        print(f"\nMaking the destination directory '{destination_directory}' ...")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        command = (f"python3 copyfiles.py local {self.__local_working_path}/folderFrom2/ "
                   f"T3_US_FNALLPC copyfiles_test/ -p gfal -r")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom1.txt",
                             f"{destination_directory}/FolderFrom2.1/fileFrom2.txt",
                             f"{destination_directory}/FolderFrom2.2/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print(f"\nRemoving the remote directory '{destination_directory}'")
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_xrootd_file(self):
        """Copy a single file from a remote source to a remote destination using XRootD."""
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over one file before the test command")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC /copyfiles_test/fileFrom1.txt "
                   "T3_US_FNALLPC copyfiles_test2/fileFrom1.txt -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_file = f"{destination_directory}/fileFrom1.txt"
        self.check_popen(process, [destination_file], redir = "root://cmseos.fnal.gov/")

        print("\nRemoving the remote directories")
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_file}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_xrootd_contents(self):
        """Copy the contents of a directory from a remote source to a remote destination using XRootD."""
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory + "/folderFrom1"], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over two files before the test command")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")
        command = (f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt "
                   f"root://cmseos.fnal.gov/{source_directory}/folderFrom1/")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/folderFrom1/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC /copyfiles_test/ "
                   "T3_US_FNALLPC copyfiles_test2/ -p xrootd")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/", verbose = True)

        print("\nRemoving the remote directories")
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/folderFrom1/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_xrootd_contents_recursive(self):
        """Recursively copy the contents of a directory from a remote source to a remote destination using XRootD."""
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory + "/folderFrom1"], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over two files before the test command")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")
        command = (f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt "
                   f"root://cmseos.fnal.gov/{source_directory}/folderFrom1/")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/folderFrom1/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC /copyfiles_test/ "
                   "T3_US_FNALLPC copyfiles_test2/ -p xrootd -r")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/folderFrom1/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print("\nRemoving the remote directories")
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_directory}/folderFrom1/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/folderFrom1/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_xrootd_contents_recursive_diff(self):
        """Recursively copy the contents of a directory from a remote source to a remote destination using XRootD.
        This method first checks to see if there are existing files at the destination and does not try to copy those again.
        """
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory + "/folderFrom1"], redir = "root://cmseos.fnal.gov/")
        command = f"xrdfs root://cmseos.fnal.gov/ mkdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over two files before the test command")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")
        command = f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt root://cmseos.fnal.gov/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory+"/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")
        command = (f"xrdcp {self.__local_working_path}/folderFrom2/fileFrom1.txt "
                   f"root://cmseos.fnal.gov/{source_directory}/folderFrom1/")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory+"/folderFrom1/fileFrom1.txt"], redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC /copyfiles_test/ "
                   "T3_US_FNALLPC copyfiles_test2/ -p xrootd -r --diff")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt",
                             f"{destination_directory}/folderFrom1/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/", verbose = True)

        print("\nRemoving the remote directories")
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {destination_directory}/folderFrom1/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rm {source_directory}/folderFrom1/fileFrom1.txt"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}/folderFrom1"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"xrdfs root://cmseos.fnal.gov/ rmdir {source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_gfal_file(self):
        """Copy a single file from a remote source to a remote destination using gfal."""
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over some files before the test command")
        command = f"gfal-copy --recursive {self.__local_working_path} root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process,
                         [source_directory+"/folderFrom2/FolderFrom2.1/fileFrom1.txt"],
                         redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC copyfiles_test/folderFrom2/fileFrom1.txt "
                   "T3_US_FNALLPC copyfiles_test2/ -p gfal")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [f"{destination_directory}/fileFrom1.txt"]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print("\nRemoving the remote directories")
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

    def test_remote_remote_gfal_contents_recursive(self):
        """Recursively copy the contents of a directory from a remote source to a remote destination using gfal."""
        source_directory = f"/store/user/{os.environ['USER']}/copyfiles_test/"
        destination_directory = f"/store/user/{os.environ['USER']}/copyfiles_test2/"
        print("\nMaking the source and destination directories ...")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [source_directory], redir = "root://cmseos.fnal.gov/")
        command = f"gfal-mkdir gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process, [destination_directory], redir = "root://cmseos.fnal.gov/")

        print("\nCopying over some files before the test command")
        command = f"gfal-copy --recursive {self.__local_working_path} root://cmseos.fnal.gov/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        self.check_popen(process,
                         [source_directory + "/folderFrom2/FolderFrom2.1/fileFrom1.txt"],
                         redir = "root://cmseos.fnal.gov/")

        command = ("python3 copyfiles.py T3_US_FNALLPC copyfiles_test/ "
                   "T3_US_FNALLPC copyfiles_test2/ -p gfal -r")
        print(f"\nTesting the following command ... \n\t{command}")
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT)
        destination_files = [ f"{destination_directory}/{file}" for file in self.__fromPaths]
        self.check_popen(process, destination_files, redir = "root://cmseos.fnal.gov/")

        print("\nRemoving the remote directories")
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{source_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]
        command = f"gfal-rm -r gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms/{destination_directory}"
        process = subprocess.Popen(shlex.split(command), stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]

if __name__ == '__main__':
    unittest.main()
