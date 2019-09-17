*** Settings ***
Library    DSCP_verification
Test Timeout    2 minutes


*** Test Cases ***
Start capture
    set prio
    start capture
