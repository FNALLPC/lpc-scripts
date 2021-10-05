# lpc-scripts
scripts of use on the cmslpc cluster

## Unit and Integration testing

### Automated
Some automated linting for both Python and Bash takes place using GitHub Actions. This testing is run on both pushes and pull requests. The jobs use pylint to check the Python code and ShellCheck to do the static checking of the Bash scripts.

### Manual
Much of the code contained here relies on certain mounts (i.e. cvmfs), specific disk systems (eos), or specially installed software (i.e. voms-proxy-init). The codes which rely on these can't be easily tested using automated GitHub Actions jobs. Below you will find some directions on how to manually test the code.

**Please note***, these tests do not constitute complete coverage. Some additional manual testing may be necessary.*

#### Bats for Bash scripts

The [Bats](https://bats-core.readthedocs.io/en/stable/) tests are currently setup to test only the `eosdu` executable. Every effort has been made to test all of the options. Even so, full coverage is not guaranteed. These tests rely on the eos path `/store/user/cmsdas/test/` being stable.

```bash
cd <path to lpc-scripts>/lpc-scripts
git clone https://github.com/bats-core/bats-core.git test/bats
git clone https://github.com/bats-core/bats-support.git test/test_helper/bats-support
git clone https://github.com/bats-core/bats-assert.git test/test_helper/bats-assert
./test/bats/bin/bats test/test.bats
```

Expected output:
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
