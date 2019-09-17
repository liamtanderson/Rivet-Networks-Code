#Public Test
#This file is executed by bandwidth_maximum_test.robot and has a primary purpose of setting a max bandwidth upload and download speed and testing the accuracy
#This file is reliant on having chromedriver.exe in the same folder due to its use of selenium to perform a network test
#This file is also reliant on having logger.py in the same folder as logger.py is used to generate data for debugging
#Written by William Anderson, contact at liamtanderson@gmail.com with questions

from subprocess import call #Used to start and stop killer network services via command line
from xml.dom import minidom #Used to parse the user.xml file
import xml.etree.ElementTree as ET #Uses to parse and edit the user.xml file
import selenium #Used to access online speedtest
from selenium import webdriver
from timeit import default_timer as timer #Used to wait for speedtest to finish
import time

import requests 
import yaml

import logger #used to log metadata

class RobotFatalError(RuntimeError): #Default robot error class
	''' 
	Raised when the test fails and you need to exit with a failiure
	'''
	ROBOT_EXIT_ON_FAILURE = True

#These tests function by editing the max bandwidth in killer via the user.xml file and then logging onto an online speedtest to check validity
class bandwidth_maximum_test: #Test case

    def __init__(self): #Initializes log
        log = logger.attach_to_logger(__name__)
        log.info('Starting: Bandwidth Maximum Test')

    def run_upload_test(self): #Runs test
        log = logger.attach_to_logger(__name__)
        log.info('Starting: Upload Maximum Test')
        bandwidthup = "10000000" #10mbs, an easy value for testing the feature
        bandwidthdown = "10000000" 

        call(["sc", "stop", "Killer Network Service x64"]) #Stops killer network service via command line

        #Now that killer network service is stopped, user.xml can be updated
        tree = ET.parse('C:/ProgramData/RivetNetworks/Killer/user.xml') #Loads file, the files location should be consistent across all computers due to Killer's install process
        root = tree.getroot() #Gets root out of the tree parse
        sh = root.find('NetworkInfos') #Finds parent
        networkinfo = sh.find('NetworkInfo') #Finds child which contains the attributes we are looking for
        
        networkinfo.set('BandwidthUp', bandwidthup) #Updates bandwidth upload max speed value
        networkinfo.set('BandwidthDown', bandwidthdown) #Updates bandwidth download max speed
        tree.write('C:/ProgramData/RivetNetworks/Killer/user.xml') #Overrides the old user.xml file with a new updated file.

        #Now we need to start Killer and see if change is made
        call(["sc", "start", "Killer Network Service x64"]) #Starts killer network service via command line
        global driver
        driver = webdriver.Chrome(executable_path = 'chromedriver.exe') #Logs in as a chrome user
        driver.get('http://killernetworking.speedtestcustom.com/')#Opens up killer's speed test via chrome
        id_box = driver.find_element_by_xpath('//*[@id="main-content"]/div[1]/div/button')#Isolates the "go" button
        id_box.click()#clicks go button
        time.sleep(60)#waits for test to be completed
        upload_element = driver.find_element_by_xpath('//*[@id="root"]/div/div[2]/div[2]/main/div[2]/div[2]/div[2]/div[2]/div/div/span')#Grabs upload element via xpath
        uploadSpeed = upload_element.text #Grabs upload speed from element

        #Adds data to log for debugging
        log.info('Upload Speed: ' + str(uploadSpeed))
        
        #Converts from mb to bits
        uploadSpeed = float(uploadSpeed) * 1000000

        uploadError = 0.93 - uploadSpeed/float(bandwidthup) #Killer automatically sets the max bandwidth to 93% of value set so the error formula reflects that

        #Adds data to log for debugging
        log.info('Upload Error: ' + str(uploadError))

        #Now the script determines if the test failed and returns info to Jenkins
        #Error < 1% = Perfect pass
        #Error < 3% = Pass with warning
        #Error > 3% = Fail  
        if uploadError > 0.03 or uploadError < -0.03:
            raise Exception('Upload error greater than 3%')
        elif uploadError > 0.01 or uploadError < -0.01:
            log.info("Upload error greater than 1%")
        else:
            log.info("Upload error within 1%")
        

    def run_download_test(self): #Runs test
        log = logger.attach_to_logger(__name__)
        log.info('Starting: Download Speed Test')
        bandwidthdown = "10000000"
        download_element = driver.find_element_by_xpath('//*[@id="root"]/div/div[2]/div[2]/main/div[2]/div[2]/div[1]/div[2]/div/div/span')#Grabs download element via xpath
        downloadSpeed = download_element.text #Grabs download speed from element

        #Adds data to log for debugging
        log.info('download Speed: ' + str(downloadSpeed))
        
        #Converts from mb to bits
        downloadSpeed = float(downloadSpeed) * 1000000

        downloadError = 0.93 - downloadSpeed/float(bandwidthdown) #Killer automatically sets the max bandwidth to 93% of value set so the error formula reflects that

        #Adds data to log for debugging
        log.info('Download error: ' + str(downloadError))

        #Now the script determines if the test failed and returns info to Jenkins
        #Error < 1% = Perfect pass
        #Error < 3% = Pass with warning
        #Error > 3% = Fail  
        if downloadError > 0.03 or downloadError < -0.03:
            raise Exception('Download error greater than 3%')
        elif downloadError > 0.01 or downloadError < -0.01:
            log.info("Download error greater than 1%")
        else:
            log.info("Download error within 1%")   
