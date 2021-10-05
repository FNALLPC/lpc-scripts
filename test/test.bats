#!/usr/bin/env bats

setup() {
	load '/test_helper/bats-support/load'
    load '/test_helper/bats-assert/load'

    # get the containing directory of this file
    # use $BATS_TEST_FILENAME instead of ${BASH_SOURCE[0]} or $0,
    # as those will point to the bats executable's location or the preprocessed file respectively
    DIR="$( cd "$( dirname "$BATS_TEST_FILENAME" )" >/dev/null 2>&1 && pwd )"
    # make executables in src/ visible to PATH
    PATH="$DIR/..:$PATH"
}

@test "Check eosdu basic" {
    run eosdu /store/user/cmsdas/test/
    assert_output '50336470076'
}

@test "Check eosdu usage message" {
	run eosdu -u /store/user/cmsdas/test/
	assert_output --partial 'usage: eosdu [options] <LFN>'
}

@test "Check eosdu file count" {
	run eosdu -f /store/user/cmsdas/test/
	assert_output '68'
}

@test "Check eosdu human readable" {
	run eosdu -h /store/user/cmsdas/test/
	assert_output '50.3365 GB'
}

@test "Check eosdu recursive" {
	run eosdu -r /store/user/cmsdas/test/testing/2017
	assert_output --partial 'facilitators 13274777'
}

@test "Check eosdu human readable bibytes" {
	run eosdu -hb /store/user/cmsdas/test/
	assert_output '46.8795 GiB'
}

@test "Check eosdu human readable file count" {
	run eosdu -hf /store/user/cmsdas/test/
	assert_output '68 files '
}

@test "Check eosdu recursive human readable" {
	run eosdu -hr /store/user/cmsdas/test/testing/2017
	assert_output --partial 'facilitators 13.2748 MB'
}

@test "Check eosdu recursive file count" {
	run eosdu -fr /store/user/cmsdas/test/testing/2017
	assert_output --partial 'facilitators 33'
}

@test "Check eosdu recursive human readable file count" {
	run eosdu -hfr /store/user/cmsdas/test/testing/2017
	assert_output --partial 'facilitators 33 files'
}

@test "Check eosdu grep" {
	run eosdu -g facilitators /store/user/cmsdas/test/testing/2017/
	assert_output '13274777'
}

@test "Check eosdu human readable grep" {
	run eosdu -h -g facilitators /store/user/cmsdas/test/testing/2017
	assert_output '13.2748 MB'
}

@test "Check eosdu file count grep" {
	run eosdu -f -g facilitators /store/user/cmsdas/test/testing/2017
	assert_output '1'
}

@test "Check eosdu human readable file count grep" {
	run eosdu -hf -g facilitators /store/user/cmsdas/test/testing/2017
	assert_output '1 files '
}
