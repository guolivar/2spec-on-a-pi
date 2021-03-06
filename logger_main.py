#!/usr/bin/env python3

# Load the libraries
#this is to test something
import serial	   # Serial communications
import time		 # Timing utilities
import subprocess   # Shell utilities ... compressing data files
import os,sys		   # OS utils to keep working directory
import json # To send JSON object to MQTT broker
import paho.mqtt.client as mqtt # MQTT publishing
import boto3 # AWS client
from botocore.config import Config # Configure AWS client

# Manual, more flexible, "serial readline"
def Serial_Readline(_ser, _eol):
	leneol = len(_eol)
	_bline = bytearray()
	while True:
		c = _ser.read(1)
		_bline += c
		if _bline[-leneol:] == _eol:
			break
	## Parse the data line
	_line = _bline.decode("utf-8").rstrip()
	return _line

aws_secrets = open("./secret_aws.txt")
aws_cred = aws_secrets.readline().split(';')

my_S3_config = Config(
	region_name = 'ap-southeast-2',
	signature_version = 'v4',
	retries = {
		'max_attempts': 10,
		'mode': 'standard'
	}
)

clientS3 = boto3.client(
	's3',
	aws_access_key_id=aws_cred[0],
	aws_secret_access_key=aws_cred[1],
	config = my_S3_config
)
# Let's use Amazon S3
s3 = boto3.resource('s3')

# Set the time constants
rec_time = time.gmtime()
start_time = int(time.time())
timestamp = time.strftime("%Y/%m/%d %H:%M:%S GMT", rec_time)
prev_minute = rec_time[4]
# Set the minute averaging variables
min_no2 = 0
min_temp_no2 = 0
min_rawno2 = 0
min_rawtemp_no2 = 0
n_samples_no2 = 0
min_co = 0
min_temp_co = 0
min_rawco = 0
min_rawtemp_co = 0
n_samples_co = 0
# Read the settings from the settings file
settings_file = open("./config/settings.txt")
# CO Serial port e.g. "/dev/ttyUSB0"
port_co = settings_file.readline().rstrip('\n')
print(timestamp + port_co)
# NO2 Serial port e.g. "/dev/ttyUSB0"
port_no2 = settings_file.readline().rstrip('\n')
print(timestamp + port_no2)
# path for data files
# e.g. "/home/logger/datacpc3010/"
datapath = settings_file.readline().rstrip('\n')
print(timestamp + datapath)
prev_file_name = datapath + time.strftime("%Y%m%d.txt", rec_time)
flags = settings_file.readline().rstrip().split(',')
print(timestamp + flags[0])

current_LOG_name = datapath + time.strftime("%Y%m%d.LOG", rec_time)
current_file = open(current_LOG_name, "a")
current_file.write(timestamp + " Logging starts\n")
current_file.write(timestamp + " " + port_co + "\n")
current_file.write(timestamp + " " + port_no2 + "\n")
current_file.write(timestamp + " " + datapath + "\n")
current_file.write(timestamp + " " + flags[0] + "\n")
current_file.flush()
current_file.close()

# MQTT address
phant_server = settings_file.readline().rstrip('\n')
# MQTT topic 
publickey = settings_file.readline().rstrip('\n')

# Close the settings file
settings_file.close()

fields = ["co", "no2", "co_t", "no2_t", "serial_co", "serial_no2"] # Your feed's data fields

# Hacks to work with custom end of line
eol = b'\n'

# Wait 5 seconds to stabilize the sensors
time.sleep(5)
# Start the logging
while True:
	try:
		# Open the CO serial port and clean the I/O buffer
		ser_co = serial.Serial(port_co, 9600, parity=serial.PARITY_NONE,
							bytesize=serial.EIGHTBITS)
		ser_co.flushInput()
		ser_co.flushOutput()
		# If the sensor was working in a continuous mode, stop it
		ser_co.write('\r')
		# Open the no2 serial port and clean the I/O buffer
		ser_no2 = serial.Serial(port_no2, 9600, parity=serial.PARITY_NONE,
							bytesize=serial.EIGHTBITS)
		ser_no2.flushInput()
		ser_no2.flushOutput()
		# If the sensor was working in a continuous mode, stop it
		ser_no2.write('\r')
		# Request a reading (send any character through the serial port)
		ser_co.write('\r')
		ser_no2.write('\r')
		# Get the line of data from the CO sensor
		line_co = Serial_Readline(ser_co,eol)
		# Get the line of data from the NO2 sensor
		line_no2 = Serial_Readline(ser_no2,eol)

		# Set the time for the record
		rec_time_s = int(time.time())
		rec_time = time.gmtime()
		timestamp = time.strftime("%Y/%m/%d %H:%M:%S GMT", rec_time)
		# SAMPLE LINE ONLY
		# line = '111416020452, -160, 20, 60, 32852, 24996, 34986, 00, 00, 02, 48'
		line_co = line_co.rstrip()
		line_no2 = line_no2.rstrip()
		print(rec_time[4])
		print(timestamp + line_co)
		print(timestamp + line_no2)
		# Make the line pretty for the file
		# If it has been within 1 hour of the start, flag the data by adding X to
		# serialn
		if ((rec_time_s - start_time) < 3600):
			file_line = timestamp + ', X' + line_co + ', X' +  line_no2
		else:
			if (flags[0] == 'clean'):
				ser_co.write('g')
				ser_co.write('Z')
				ser_co.write('12345\r')
				ser_no2.write('g')
				ser_no2.write('Z')
				ser_no2.write('12345\r')
				# Wait 2 seconds for the setting to be active
				time.sleep(2)
				# clear the serial buffer
				ser_co.flushInput()
				ser_no2.flushInput()
				flags[0] = 'local'
			file_line = timestamp + ',' + line_co + ',' + line_no2
		json_line = json.dumps(file_line.sep(','))
		sep_line_co = line_co.split(',')
		sep_line_no2 = line_no2.split(',')
		if flags[0]=='online':
			min_co = min_co + eval(sep_line_co[1])
			min_temp_co = min_temp_co + eval(sep_line_co[2])
			min_rawco = min_rawco + eval(sep_line_co[4])
			min_rawtemp_co = min_rawtemp_co + eval(sep_line_co[5])
			n_samples_co = n_samples_co + 1
			min_no2 = min_no2 + eval(sep_line_no2[1])
			min_temp_no2 = min_temp_no2 + eval(sep_line_no2[2])
			min_rawno2 = min_rawno2 + eval(sep_line_no2[4])
			min_rawtemp_no2 = min_rawtemp_no2 + eval(sep_line_no2[5])
			n_samples_no2 = n_samples_no2 + 1
		# Save it to the appropriate file
		current_file_name = datapath + time.strftime("%Y%m%d.txt", rec_time)
		current_file = open(current_file_name, "a")
		current_file.write(file_line + "\n")
		current_file.flush()
		current_file.close()
		line_co = ""
		line_no2 = ""
		#Send concentration only data to mqtt_server
		print("Sending an update!")
		client.publish(mqtt_topic,json_line)
		# Compress data if required
		# Is it the last minute of the day?
		if flags[1] == 1:
			if current_file_name != prev_file_name:
				subprocess.call(["gzip", prev_file_name])
				current_LOG_name = datapath + time.strftime("%Y%m%d.LOG", rec_time)
				current_file = open(current_LOG_name, "a")
				current_file.write(timestamp + ": Previous data file compressed\n")
				current_file.flush()
				current_file.close()
				prev_file_name = current_file_name
		ser_co.close()
		ser_no2.close()
	except:
		current_LOG_name = datapath + time.strftime("%Y%m%d.LOG", rec_time)
		current_file = open(current_LOG_name, "a")
		current_file.write(timestamp + ": Unexpected error - NO DATA\n")
		current_file.flush()
		current_file.close()
	# Wait 5s for the next measurement --- OPTIONAL
	while int(time.time()) < (rec_time_s + 5):
		# wait a few miliseconds
		time.sleep(0.05)
print('I\'m done')
