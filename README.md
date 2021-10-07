# lpc-scripts
scripts of use on the cmslpc cluster

## Unit and Integration testing

### Automated
Some automated linting for both Python and Bash takes place using GitHub Actions. This testing is run on both pushes and pull requests. The jobs use pylint to check the Python code and ShellCheck to do the static checking of the Bash scripts.

### Manual
Much of the code contained here relies on certain mounts (i.e. cvmfs), specific disk systems (eos), or specially installed software (i.e. voms-proxy-init). The codes which rely on these can't be easily tested using automated GitHub Actions jobs. Below you will find some directions on how to manually test the code.

*Please note, these tests do not constitute complete coverage. Some additional manual testing may be necessary.*

#### Bats for Bash scripts

The [Bats](https://bats-core.readthedocs.io/en/stable/) tests are currently setup to test only the `eosdu` executable. Every effort has been made to test all of the options. Even so, full coverage is not guaranteed. These tests rely on the eos path `/store/user/cmsdas/test/` being stable.

First the Bats software needs to be setup. This is a process that only needs to happen once. To setup the software run the following command from within the `<path to lpc-scripts>/lpc-scripts` directory:
```bash
./test/bats_control.sh -s
```

Once the software is setup, you can run the tests using:
```bash
./test/bats_control.sh
```

If everything is working correctly, the output will be:
```
 ✓ Check eosdu basic
 ✓ Check eosdu usage message
 ✓ Check eosdu file count
 ✓ Check eosdu human readable
 ✓ Check eosdu recursive
 ✓ Check eosdu human readable bibytes
 ✓ Check eosdu human readable file count
 ✓ Check eosdu recursive human readable
 ✓ Check eosdu recursive file count
 ✓ Check eosdu recursive human readable file count
 ✓ Check eosdu grep
 ✓ Check eosdu human readable grep
 ✓ Check eosdu file count grep
 ✓ Check eosdu human readable file count grep

14 tests, 0 failures
```

To remove the Bats software run:
```bash
./test/bats_control.sh -r
```

#### Pytest for Python modules

To run the python unit/integration tests, you will need to have pytest installed. Currently the version of pytest in CMSSW_12_1_0_pre3 does not work and there is no pytest module installed on the cmslpc host machines. To create a local virtual environment with pytest installed, use the following commands from within the `<path to lpc-scripts>/lpc-scripts` directory:

```bash
source test/pytest_control.sh -s
```

You only have to run that command when setting up the virtual environment the first time. In subsequent sessions you can use the following command to enter the virtual environment:

```bash
source test/venv/bin/activate
```

You can then run the tests by using the command:

```bash
source test/pytest_control.sh
```

You should see an output similar to:
```
========================================================== test session starts ===========================================================
platform linux -- Python 3.6.8, pytest-6.2.5, py-1.10.0, pluggy-1.0.0
rootdir: <path to lpc-scripts>
collected 7 items

test/test.py s......                                                                                                               [100%]

====================================================== 6 passed, 1 skipped in 5.74s ======================================================
```

You can pass addition options to pytest using the `-o` flag. For example, you could run the following command to increase the verbosity of pytest:

```bash
source test/pytest_control.sh -o '"--verbosity=3"'
```

Other helpful pytest options include:
  - `-rp`: To see the output of successful tests. This is necessary because by default all of the output from the various tests is captured by pytest.
  - `-rx`: To see the output of failed tests (default).

Once you're finished, you can exit the virtual environment by using the command:
```bash
deactivate
```

To remove the virtual environment use the command:

```bash
source test/pytest_control.sh -r
```

which will simply remove the `venv` directory.
