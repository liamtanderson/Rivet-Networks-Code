*** Settings ***
Library    bandwidth_maximum_test
Test Timeout    4 minutes
*** Test Cases ***
Max upload test
    run upload test
Max download test
    run download test
