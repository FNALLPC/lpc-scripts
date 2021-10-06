#!/usr/bin/env python3

from __future__ import absolute_import
from io import StringIO
import os
import sys
sys.path.insert(1, os.path.dirname(os.path.realpath(__file__))+'/..')
import pytest
import GetPythonVersions
import GetSiteInfo
import RecursiveFileList
import toolgenie

class Capturing(list):
    """A context manager which captures stdout and returns it as a list of strings, one for each line.
    This class is based on https://stackoverflow.com/questions/16571150/how-to-capture-stdout-output-from-a-python-function-call
    """
    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self
    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        del self._stringio    # free up some memory
        sys.stdout = self._stdout

@pytest.mark.skip(reason="taskes a long time to run")
class TestGetPythonVersions:
    _known_output = ['WARNING::getPythonVersions::Do not setup CMSSW and LCG software in the same environment.',
'Bad things will happen.',
'',
'To setup the LCG software do:',
'  source /cvmfs/sft.cern.ch/lcg/views/<LCG Version>/<Architecture>/setup.(c)sh',
'',
'Version | LCG_Versions | Architectures         | Setup   | Notes                      ',
'--------+--------------+-----------------------+---------+----------------------------',
'3.6.8   | N/A          | x86_64-centos7-gcc485 | Unknown | Currently running version  ',
'2.7.5   | N/A          | x86_64-centos7-gcc485 | N/A     | Default system python (sl7)']

    def test_get_python_versions(self):
        with Capturing() as output:
            GetPythonVersions.get_python_versions(agrep = "x86_64-centos7-gcc485", pgrep = "3.6.8", shorten = True)
        print(output)
        assert output == self._known_output

class TestGetSiteInfo:
    def test_get_site_info(self):
        site = GetSiteInfo.get_site_info(site_alias = "T3_US_FNALLPC",
                                         env = True,
                                         quiet = True,
                                         shell = None)
        assert site.name == site.alias == site.rse == "T3_US_FNALLPC"
        assert len(site.endpoints) == 3
        assert site.pfn == "gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms"

    def test_get_site_info_env_shell(self):
        with Capturing() as output:
            site = GetSiteInfo.get_site_info(site_alias="T3_US_FNALLPC",
                                             env=True,
                                             quiet=False,
                                             shell = ['rse','pfn'])
        assert site.name == site.alias == site.rse == "T3_US_FNALLPC"
        assert len(site.endpoints) == 3
        assert site.pfn == "gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms"
        assert "rse=T3_US_FNALLPC" in output
        assert "pfn=gsiftp://cmseos-gridftp.fnal.gov:2811/eos/uscms" in output

class TestRecursiveFileList:
    def test_map_dir(self):
        prefix = "/eos/uscms/store/user/cmsdas/"
        directory = "test"
        output = RecursiveFileList.map_dir(prefix, directory)
        assert len(output[directory][0]['testing'][0]['2017'][0]['facilitators']) == 33

    def test_make_file_list(self):
        path = "/eos/uscms/store/user/cmsdas/test"
        output = RecursiveFileList.make_file_list(path, RecursiveFileList.map_dir(path, path))
        assert isinstance(output, list)
        assert len(output) == 62

    def test_make_dir_list(self):
        path = "/eos/uscms/store/user/cmsdas/test"
        output = RecursiveFileList.make_dir_list(path, RecursiveFileList.map_dir(path, path))
        assert isinstance(output, list)
        assert len(output) == 6

    def test_make_dir_list(self):
        path = "/eos/uscms/store/user/cmsdas/test"
        output = RecursiveFileList.get_file_list(path)
        assert isinstance(output, list)
        assert len(output) == 62

    def test_make_dir_list(self):
        path = "/eos/uscms/store/user/cmsdas/test"
        output = RecursiveFileList.get_dir_list(path)
        assert isinstance(output, list)
        assert len(output) == 6

class TestToolgenie:
    _known_output=['Based on your input (slc7_amd64_gcc900), the selected SCRAM architectures are:',
                   '\tslc7_amd64_gcc900',
                   '',
                   'You selected the release(s):',
                   "\tRelease(architecture='slc7_amd64_gcc900', label='CMSSW_12_0_1', type='Production', state='Announced', prodarch=1)",
                   '',
                   'You selected the tools(s):',
                   '\tboost',
                   '',
                   "The following is a summary of the information for the tool 'boost':",
                   '|    SCRAM_ARCH     |   Release    |    Version     |                                                      ConfigPath                                                       |                              Location                              |',
                   '| ----------------- | ------------ | -------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |',
                   '| slc7_amd64_gcc900 | CMSSW_12_0_1 | 1.75.0-llifpc2 | /cvmfs/cms.cern.ch/slc7_amd64_gcc900/cms/cmssw/CMSSW_12_0_1/config/toolbox/slc7_amd64_gcc900/tools/selected/boost.xml | /cvmfs/cms.cern.ch/slc7_amd64_gcc900/external/boost/1.75.0-llifpc2 |',
                   '',
                   '']

    def test_toolgenie(self):
        with Capturing() as output:
            tools = toolgenie.toolgenie(architecture = "slc7_amd64_gcc900",
                                        cmssw = "CMSSW_12_0_1",
                                        tool = "boost",
                                        quiet = True)
        print(tools)
        assert tools[0].Architectures == ["slc7_amd64_gcc900"]
        assert tools[0].Releases == ['CMSSW_12_0_1']
        assert tools[0].Name == 'boost'
        assert output == self._known_output
