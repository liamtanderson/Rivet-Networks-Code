#Public Test
#This file is executed by bandwidth_maximum_test.robot and has a primary purpose of setting a max bandwidth and testing the accuracy
#Written by William Anderson, contact at liamtanderson@gmail.com with questions
from subprocess import call
import subprocess
from xml.dom import minidom
import xml.etree.ElementTree as ET
import selenium
from selenium import webdriver
from timeit import default_timer as timer
import time

import requests
import yaml

import logger

class RobotFatalError(RuntimeError): #Default robot error class
	''' 
	Raised when the test fails and you need to exit with a failiure
	'''
	ROBOT_EXIT_ON_FAILURE = True

class automated_iperf_test: #Test case

    def __init__(self): #Initializes log
        log = logger.attach_to_logger(__name__)
        log.info('Starting: Iperf Test')

    def run_test(self): #Runs test
        log = logger.attach_to_logger(__name__)
        bandwidthup = "100000000" #100mbs, an easy value for testing the feature 
        bandwidthdown = "100000000"

        log.info("Turning off Killer Networking Service")
        call(["sc", "stop", "Killer Network Service x64"]) #Stops killer network service via command line
        call(["sc", "stop", "KfeCoSvc"]) 
        call(["reg", "add", R"HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\KfeCoSvc\Parameters", "/v", "BypassLocalLan", "/t", "REG_DWORD", "/d", "0"])
        
        log.info("Lan Exceptions registry key remade")

        #Now that killer network service is stopped, user.xml can be updated
        tree = ET.parse('C:/ProgramData/RivetNetworks/Killer/user.xml') #Loads file, the files location should be consistent across all computers due to Killer's install process
        root = tree.getroot() #Gets root out of the tree parse
        sh = root.find('NetworkInfos') #Finds parent
        networkinfo = sh.find('NetworkInfo') #Finds child which contains the attributes we are looking for
        
        networkinfo.set('BandwidthUp', bandwidthup) #Updates bandwidth upload max speed value
        networkinfo.set('BandwidthDown', bandwidthdown) #Updates bandwith download max speed value
        tree.write('C:/ProgramData/RivetNetworks/Killer/user.xml') #Overrides the old user.xml file with a new updated file.

        #Now we need to start Killer and see if change is made
        call(["sc", "start", "Killer Network Service x64"]) #Starts killer network service via command line
        call(["sc", "start", "KfeCoSvc"]) 
        
        log = logger.attach_to_logger(__name__)
        log.info('Attempting to log in:')
        call(["psexec","\\\\10.200.100.199", "-u", "test", "-p", "test",  "C:/Users/test/Desktop/iperf-3.0.11-win64/iperf3.exe", "-s"])
        log.info('logged in')
        log.info('Server Client running')
        time.sleep(15)
        command = ["iperf3.exe", "-c", "10.200.100.199", "-t", "60"]
        result = subprocess.run(command, stdout=subprocess.PIPE)
        log.info(result)
        output = str(result)
        log.info("Iperf Test Output:" + output)
        index = output.rfind('bits')
        log.info(output[index - 1])
        if (output[index - 1] == "M"):
            log.info("In Megabits")
        log.info("Download Speed: " + output[index - 6: index])
        downloadSpeed = float(output[index - 6: index - 2])
        uploadSpeedString = output[1: index - 9]
        index = uploadSpeedString.rfind('bits')
        log.info(uploadSpeedString[index - 1])
        if (uploadSpeedString[index - 1] == "M"):
            log.info("In Megabits")
        log.info("Upload Speed: " + uploadSpeedString[index - 6: index])
        uploadSpeed = float(uploadSpeedString[index - 6: index - 2])

        log.info('Download Speed: ' + str(downloadSpeed)) #Adds data to log for debugging
        log.info('Upload Speed: ' + str(uploadSpeed))
        
        downloadSpeed = downloadSpeed * 1000000 #Converts from mb to bits
        uploadSpeed = uploadSpeed * 1000000

        downloadError = 0.93 - downloadSpeed/float(bandwidthdown) #Finds the % off the test was
        uploadError = 0.93 - uploadSpeed/float(bandwidthup) #Killer automatically sets the max bandwidth to 93% of value set so the error formula reflects that

        log.info('Download Error: ' + str(downloadError)) #Adds data to log for debugging
        log.info('Upload Error: ' + str(uploadError))

        #Now the script determines if the test failed and returns info to Jenkins
        #Error < 1% = Perfect pass
        #Error < 3% = Pass with warning
        #Error > 3% = Fail  
        if downloadError>-0.01 and downloadError<0.01:#If download error passes perfectly
            if uploadError>-0.01 and uploadError<0.01:#If upload error also passes perfectly, pass test
                return 'PASS'
            elif uploadError>-0.03 and uploadError<0.03:
                return 'WARN due to upload speed error being bigger than 1%'
            else: 
                raise Exception("Test failed because of upload speed error being > 3%")     

        elif downloadError>-0.03 and downloadError<0.03: #If within 3%, Warn
            if uploadError >0.03 or uploadError <-0.03:
                raise Exception("Test failed because of upload speed error being > 3%") 
            elif uploadError>-0.01 and uploadError<0.01:
                return 'WARN due to download speed error being > 1%' 
            else:
                return 'WARN due to both download and upload speed error being > 1%'    

        else: #If > 3% error fail the test
            if uploadError>-0.01 and uploadError<0.01:
                raise Exception("Test failed because of download error being > 0.03 but upload error is less than 1%")
            elif uploadError>-0.03 and uploadError<0.03:
                raise Exception('Test failed because of download error being > 0.03 but upload error is less than 3%')
            else:
                raise Exception('Test failed because both upload and download error are > 3%')
