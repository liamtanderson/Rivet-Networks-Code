*** Settings ***
Library    automated_iperf_test
Test Timeout    4 minutes
*** Test Cases ***
Run iperf bandwidth test
    run test
