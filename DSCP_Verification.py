import pyshark
import ftplib
import sys
from ctypes import cdll, POINTER
from comtypes.automation import VARIANT
import os

import logger
import yaml

import subprocess

from threading import Thread

import install_software

class RobotFatalError(RuntimeError):
	"""Raised when the test fails and you need to exit with a failiure"""

	ROBOT_EXIT_ON_FAILURE = True

class DSCP_verification:

	_WORKSPACE = os.getenv('WORKSPACE', default=R'C:\opt\ci\jenkins\workspace\Killer_Automation')
	_BCMWRAPPER_LIBRARY_PATH = _WORKSPACE + '\\BCMWrapper.dll'
	_UPLOAD_FILE_PATH = _WORKSPACE + '\\test_upload.exe'

	def __init__(self, filepath_to_bcmwrapper=None):
		log = logger.attach_to_logger(__name__)

		if filepath_to_bcmwrapper is None:
			self.filepath_to_bcmwrapper = self._BCMWRAPPER_LIBRARY_PATH
		else:
			self.filepath_to_bcmwrapper = filepath_to_bcmwrapper

		self.config = self.parse_yaml_config_file()
		self.ip_address, self.interface_name = self.get_ip_info()

	@staticmethod
	def preconditions():
		"""check a few things before we run the test:
		Verify killer is installed and service is running
		"""
		try:
			install_software.start_service_and_processes()
		except Exception as e:
			log.error(e)
			raise RobotFatalError("Starting Killer service and proccesses failed. Failing test....")


	@staticmethod
	def parse_yaml_config_file(yaml_config_filename=None):
		r"""Parse the arguments from a yaml file.
		Example file contents:
			  priority:
			  - 5
			  DSCP:
			  - 0x00000098
			  - 0x00000028
		"""

		log = logger.attach_to_logger(__name__)

		if yaml_config_filename is None:
			yaml_config_filename = 'DSCP_verification.yaml'

		log.info(f'Parsing YAML config file: {yaml_config_filename}')

		try:
			yaml_config_file = yaml.safe_load(open(yaml_config_filename))
			return yaml_config_file['DSCP_verification']
		except yaml.YAMLError as ye:
			log.error(f'Error loading config file {yaml_config_filename}: {ye}')
		except Exception as e:
			log.warning(f'Error: {e}')
			log.warning(f'Stack trace: {sys.exc_info()}')

	@staticmethod
	def get_ip_info():
		log = logger.attach_to_logger(__name__)
		#Grabs the ip adress and interface name
		#sets self.ip_adress, self.interface_name
		import socket
		#get's ip adress
		ip_address = socket.gethostbyname(socket.gethostname())

		log.info('Getting network interface name for ethernet adapter...')
		os.environ["COMSPEC"] = 'powershell'
		#cmd_str = R'powershell "$ip = "10.200.150.200";foreach($int in (gwmi Win32_NetworkAdapter)) {gwmi Win32_NetworkAdapterConfiguration -Filter """Index = $($int.index)""" | ? {$_.IPAddress -contains $ip} | % {$int.NetConnectionID} }"'
		cmd_str = f"$ip = '{ip_address}';" + R'foreach($int in (gwmi Win32_NetworkAdapter)) {gwmi Win32_NetworkAdapterConfiguration -Filter """Index = $($int.index)""" | ? {$_.IPAddress -contains $ip} | % {$int.NetConnectionID} }'
		log.info(cmd_str)
		try:
			output = subprocess.check_output(cmd_str, stderr=subprocess.STDOUT, shell=True)
		except Exception as e:
			log.warning(f'get interface name powershell command failed with error: {e}')

		interface_name = output.decode("utf-8").rstrip()
		log.info(ip_address)
		log.info(interface_name)

		return ip_address, interface_name

		#powershell "$ip = '10.200.150.200';foreach($int in (gwmi Win32_NetworkAdapter)) {gwmi Win32_NetworkAdapterConfiguration -Filter """Index = $($int.index)""" | ? {$_.IPAddress -contains $ip} | % {$int.NetConnectionID} }"

	def upload_file(self):
		log = logger.attach_to_logger(__name__)
		ftps = ftplib.FTP_TLS()
		ftps.connect('ftp.rivetnetworks.com', 21)
		ftps.auth()
		ftps.login('rivettemp','killernetworks2015')
		ftps.prot_p()
		ftps.cwd('/Test')
		file = open(self._UPLOAD_FILE_PATH,'rb')
		try:
			log.info('Starting ftps file upload')
			ftps.storbinary('STOR test_upload.exe', file)
		except EOFError as e:
			log.info(f'EOF Error: {e}')
		except Exception as e:
			log.info(f'Exception caught when uploading file. Error: {e}')
		ftps.quit()
		file.close()

	def start_capture(self):
		log = logger.attach_to_logger(__name__)
		prio = self.config['priority']

		cap = pyshark.LiveCapture(interface=self.interface_name, bpf_filter=f'src {self.ip_address} and port 21', output_file=f'pyshark_{prio}.pcap')
		log.info('Capture started')
		#Create a thread that uploads the file while the capture is sniffing packets
		file_upload_thread = Thread(target=self.upload_file)
		file_upload_thread.start()
		log.info('sniffing...')
		count = 0
		cap.sniff(packet_count=8)
		for packet in cap:
			if 'IP' in packet:
				packet_result = self.print_dscp_info(packet)
				if packet_result:
					count += 1
					log.debug(packet['ip'])
					if count == 5:
						log.info('Test PASSED')
						passed = True
						break
				else:
					#log.debug('aint it')
					pass
		cap.close()
		if count < 5:
			raise RobotFatalError(f'{count} packets were tagged properly. Failing test...')



	def print_dscp_info(self, packet):
		log = logger.attach_to_logger(__name__)
		#if the TCP destination port is 21, then it's FTP traffic
		if packet['ip'].dsfield in self.config['dscp']:
			log.info('Test passed: found a packet with correct dscp number')
			return True
		else:
			return False

	def set_prio(self):
		log = logger.attach_to_logger(__name__)
		log.info('Setting priority....')
		BCMWrapper = cdll.LoadLibrary(self._BCMWRAPPER_LIBRARY_PATH)
		#program = bR"c:\Program Files (x86)\Java\jre1.8.0_144\bin\java.exe"
		#program = bR"c:\Windows\System32\svchost.exe"
		program = bR"C:\Users\Rivet\AppData\Local\Programs\Python\Python37\python.exe"
		BCMWrapper.set_priority(program, int(self.config['priority']))


if __name__ == '__main__':
    dscp_obj = DSCP_verification()
    dscp_obj.set_prio()
    dscp_obj.start_capture()
