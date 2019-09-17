#Public Test
#Written by William Anderson
#Creates/Reverts Snapshots for Rivet's VMWare vms
#Reliant on logger.py in same folder for debugging data

import atexit
import argparse
import sys
import time
import ssl
import yaml
from subprocess import call

#call(["pip", "install", "pyvim"]) #Adds Pyvim to the machine running the program
#call(["pip", "install", "pyVmomi"]) #Adds pyVmomi

from pyvim.task import WaitForTask
from pyvim import connect
from pyvim.connect import Disconnect, SmartConnect, GetSi
from pyVmomi import vim, vmodl


import logger

class snapshot_job:
    def __init__(self): #Initializes log
        log = logger.attach_to_logger(__name__)
        log.info('Starting: Snapshot Job')
    def get_obj(self, content, vimtype, name):
        """
        Get the vsphere object associated with a given text name
        """
        obj = None
        container = content.viewManager.CreateContainerView(
            content.rootFolder, vimtype, True)
        for c in container.view:
            if c.name == name:
                obj = c
                break
        return obj


    def list_snapshots_recursively(self, snapshots):
        snapshot_data = [] #Holds the info that the method will gather
        snap_text = "" #string variable that holds sequential data
        for snapshot in snapshots:
            snap_text = "Name: %s; Description: %s; CreateTime: %s; State: %s" % (
                                            snapshot.name, snapshot.description,
                                            snapshot.createTime, snapshot.state)
            snapshot_data.append(snap_text)
            snapshot_data = snapshot_data + self.list_snapshots_recursively(
                                            snapshot.childSnapshotList)
        return snapshot_data


    def get_snapshots_by_name_recursively(self, snapshots, snapname): #Acquires the name of the snapshots available
        snap_obj = []
        for snapshot in snapshots:
            if snapshot.name == snapname:
                snap_obj.append(snapshot)
            else:
                snap_obj = snap_obj + self.get_snapshots_by_name_recursively(
                                        snapshot.childSnapshotList, snapname)
        return snap_obj


    def get_current_snap_obj(self, snapshots, snapob): #Checks for latest snapshot
        snap_obj = []
        for snapshot in snapshots:
            if snapshot.snapshot == snapob:
                snap_obj.append(snapshot)
            snap_obj = snap_obj + self.get_current_snap_obj(
                                    snapshot.childSnapshotList, snapob)
        return snap_obj


    def main(self, vm_input, vm_job, vm_snapshot_name, precautionary):

        log = logger.attach_to_logger(__name__)
        log.info('Starting Operation: ' + vm_job + " " + vm_input)

        inputs = {'vcenter_ip': '10.200.100.1',
            'vcenter_password': 'rivetnetworks1',
            'vcenter_user': 'root',
            'vm_name': str(vm_input),
            # operation in 'create/remove/revert/
            # list_all/list_current/remove_all'
            'operation': str(vm_job),
            'snapshot_name': str(vm_snapshot_name),
            'ignore_ssl': True
            } #Holds the data needed to log in

        si = None #holds login token

        log.info("Connecting to VMWare Server...")
        log.info("Trying to connect to VCENTER SERVER . . .")

        context = None #Will hold ssl token
        if inputs['ignore_ssl'] and hasattr(ssl, "_create_unverified_context"): #If the connection needs to be unverified
            context = ssl._create_unverified_context() #Make the context unverified 

        si = connect.Connect(inputs['vcenter_ip'], 443,
                            inputs['vcenter_user'], inputs[
                                'vcenter_password'],
                            sslContext=context) #Login token 

        atexit.register(Disconnect, si) #Checks if the status is still disconnected to the vmware server

        log.info("Connection Affirmed")
        log.info("Connected to VCENTER SERVER !")

        content = si.RetrieveContent() #now that si is connected, refresh the context

        operation = inputs['operation'] #grabs what operation the software will be performing from inputs
        vm_name = inputs['vm_name'] #grabs the name of the vm the operation will be performed on

        vm = self.get_obj(content, [vim.VirtualMachine], vm_name) #Creates a vm obj to perform tasks on

        if not vm: #If that vm doesn't match a real vm, fail the test
            log.info("Virtual Machine %s doesn't exists" % vm_name)
            raise Exception("Virtual Machine %s doesn't exists" % vm_name)
            

        if operation != 'create' and vm.snapshot is None: #If there is no snapshot and the operation isn't to create one, fail test
            log.info("Virtual Machine %s doesn't have any snapshots" % vm.name)
            if precautionary == False:
                raise Exception("Virtual Machine %s doesn't have any snapshots" % vm.name)
            

        if operation == 'create': #If operation is create, take a snapshot
            snapshot_name = inputs['snapshot_name']
            description = "Test snapshot"
            dumpMemory = False
            quiesce = False

            log.info("Creating snapshot %s for virtual machine %s" % (
                                            snapshot_name, vm.name))
            WaitForTask(vm.CreateSnapshot(
                snapshot_name, description, dumpMemory, quiesce))
            #Warning: VMware only supports one snapshot at a time

        elif operation in ['remove', 'revert']: #If the plan is to remove a snapshot or revert, check if there is a snapshot with the given name
            snapshot_name = inputs['snapshot_name']
            snap_obj = self.get_snapshots_by_name_recursively(
                                vm.snapshot.rootSnapshotList, snapshot_name)
            # if len(snap_obj) is 0; then no snapshots with specified name
            if len(snap_obj) == 1:
                snap_obj = snap_obj[0].snapshot
                if operation == 'remove':
                    log.info("Removing snapshot %s" % snapshot_name)
                    WaitForTask(snap_obj.RemoveSnapshot_Task(True))
                else:
                    log.info("Reverting to snapshot %s" % snapshot_name)
                    WaitForTask(snap_obj.RevertToSnapshot_Task())
                    vm.PowerOn()#turns on vm after revert completed
            else:
                log.info("No snapshots found with name: %s on VM: %s" % (
                                                    snapshot_name, vm.name))
                if precautionary == False:
                    raise Exception("No snapshots found with name: %s on VM: %s" % (
                                                    snapshot_name, vm.name))

        elif operation == 'list_all': #This task is not currently in use but is left for possible future use
            log.info("Display list of snapshots on virtual machine %s" % vm.name)
            snapshot_paths = self.list_snapshots_recursively(
                                vm.snapshot.rootSnapshotList)
            for snapshot in snapshot_paths:
                log.info(snapshot)
        elif operation == 'activate_node':
            WaitForTask(vm.PowerOn())
            self.logIn(vm.name)


        elif operation == 'list_current': #This task is not currently in use but is left for possible future use
            current_snapref = vm.snapshot.currentSnapshot
            current_snap_obj = self.get_current_snap_obj(
                                vm.snapshot.rootSnapshotList, current_snapref)
            current_snapshot = "Name: %s; Description: %s; " \
                            "CreateTime: %s; State: %s" % (
                                    current_snap_obj[0].name,
                                    current_snap_obj[0].description,
                                    current_snap_obj[0].createTime,
                                    current_snap_obj[0].state)
            log.info("Virtual machine %s current snapshot is:" % vm.name)
            log.info(current_snapshot)

        elif operation == 'remove_all': #This task is not currently in use but is left for possible future use
            log.info("Removing all snapshots for virtual machine %s" % vm.name)
            WaitForTask(vm.RemoveAllSnapshots())

        else:
            log.info("Specify operation in "
                "create/remove/revert/list_all/list_current/remove_all")
    def logIn(self, name):
        vm_input_name = "10.200.100.101" #Shorten the name given to the operational name
        if name == "ppal-win10-02":
            vm_input_name = "10.200.100.102"
        if name == "ppal-win10-03":
            vm_input_name = "10.200.100.103"
        if name == "ppal-win10-04":
            vm_input_name = "10.200.100.104"
        #call(["psexec","\\\\" + vm_input_name, "-u", "test", "-p", "test",  "‪C:/Users/test/Desktop/slave-agent.jnlp"])
        
    #list of rivet's vms as of 7/18/2019
    #ppal-win10-01
    #ppal-win10-02
    #ppal-win10-03
    #ppal-win10-04
    #ppal-win10-99
    def receive(self):
        config = yaml.safe_load(open('snapshot_job.yaml')) #Parse YAML File
        config = config['snapshot_job'] #Grab Data
        log = logger.attach_to_logger(__name__)
        vm_input = config['vmInputGlobal'] #Grab the vm name
        vm_job = config['vmJobGlobal'] #Grab the job to be performed
        log.info(vm_input + " will perform a " + vm_job + " task")

        vm_job_name = "create" 
        if vm_job == ("Restore Snapshot"):
            vm_job_name = "revert"
        elif vm_job == ("Activate Nodes"):
            vm_job_name = "activate_node"
       

        vm_input_name = "ppal-win10-01" #Shorten the name given to the operational name
        if vm_input == "10.200.100.102/ppal-win10-02":
            vm_input_name = "ppal-win10-02"
        if vm_input == "10.200.100.103/ppal-win10-03":
            vm_input_name = "ppal-win10-03"
        if vm_input == "10.200.100.104/ppal-win10-04":
            vm_input_name = "ppal-win10-04"
        if vm_input == "10.200.100.199/ppal-win10-99":
            vm_input_name = "ppal-win10-99"

        if vm_input == 'Select All': 
            if vm_job_name == ("create"):
                self.main('ppal-win10-01',"remove_all",'ppal-win10-01_automated_snapshot', True)
                self.main('ppal-win10-02',"remove_all",'ppal-win10-02_automated_snapshot', True)
                self.main('ppal-win10-03',"remove_all",'ppal-win10-03_automated_snapshot', True)
                self.main('ppal-win10-04',"remove_all",'ppal-win10-04_automated_snapshot', True)
                self.main('ppal-win10-99',"remove_all",'ppal-win10-99_automated_snapshot', True)
            self.main('ppal-win10-01',vm_job_name,'ppal-win10-01_automated_snapshot', False)
            self.main('ppal-win10-02',vm_job_name,'ppal-win10-02_automated_snapshot', False)
            self.main('ppal-win10-03',vm_job_name,'ppal-win10-03_automated_snapshot', False)
            self.main('ppal-win10-04',vm_job_name,'ppal-win10-04_automated_snapshot', False)
            self.main('ppal-win10-99',vm_job_name,'ppal-win10-99_automated_snapshot', False)
        else:
            if vm_job_name == ("create"):
                self.main(vm_input_name, "remove_all", str(vm_input_name + "_automated_snapshot"), True)
            self.main(vm_input_name, vm_job_name, str(vm_input_name + "_automated_snapshot"), False)
