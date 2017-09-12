#!/usr/bin/env python

# Load the libraries
import serial       # Serial communications
import time         # Timing utilities
import subprocess   # Shell utilities ... compressing data files
import requests     # Send data to Thingspeak


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

# Thingspeak address
thingspk = settings_file.readline().rstrip('\n')
# Thingspeak channel
channel = settings_file.readline().rstrip('\n')
# Thinkgspeak readkey
readkey = settings_file.readline().rstrip('\n')
# Thinkgspeak writekey
writekey = settings_file.readline().rstrip('\n')

# Close the settings file
settings_file.close()

# Hacks to work with custom end of line
eol = b'\n'
leneol = len(eol)
bline_co = bytearray()
bline_no2 = bytearray()
# Open the CO serial port and clean the I/O buffer
ser_co = serial.Serial(port_co, 9600, parity=serial.PARITY_NONE,
                    bytesize=serial.EIGHTBITS)
ser_co.flushInput()
ser_co.flushOutput()
# If the sensor was working in a continuous mode, stop it
ser_co.write('r\r')
# Open the no2 serial port and clean the I/O buffer
ser_no2 = serial.Serial(port_no2, 9600, parity=serial.PARITY_NONE,
                    bytesize=serial.EIGHTBITS)
ser_no2.flushInput()
ser_no2.flushOutput()
# If the sensor was working in a continuous mode, stop it
ser_no2.write('r\r')
# Wait 5 seconds to stabilize the sensors
time.sleep(5)
# Start the logging
while True:
    # Request a reading (send any character through the serial port)
    ser_co.write('g\r')
    ser_no2.write('g\r')
    # Get the line of data from the CO sensor
    while True:
        c = ser_co.read(1)
        bline_co += c
        if bline_co[-leneol:] == eol:
            break
    # Parse the data line
    line_co = bline_co.decode("utf-8")
    while True:
        c = ser_no2.read(1)
        bline_no2 += c
        if bline_no2[-leneol:] == eol:
            break
    # Parse the data line
    line_no2 = bline_no2.decode("utf-8")

    # Set the time for the record
    rec_time_s = int(time.time())
    rec_time = time.gmtime()
    timestamp = time.strftime("%Y/%m/%d %H:%M:%S GMT", rec_time)
    # SAMPLE LINE ONLY
    # line = '111416020452, -160, 20, 60, 32852, 24996, 34986, 00, 00, 02, 48'
    line_co = line_co.rstrip()
    line_no2 = line_no2.rstrip()
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
    bline_co = bytearray()
    bline_no2 = bytearray()
    ## Push data to thingspeak if required
    if flags[0] == 'online':
        # Is it the top of the minute?
        if rec_time[4] != prev_minute:
            print(timestamp + ": averagig and sending to thingspeak")
            prev_minute = rec_time[4]
            # YES! --> Update the Thinkgspeak channel
            # Average for the minute with what we have
            min_no2 = min_no2 / n_samples_no2
            min_temp_no2 = min_temp_no2 / n_samples_no2
            min_rawno2 = min_rawno2 / n_samples_no2
            min_rawtemp_no2 = min_rawtemp_no2 / n_samples_no2
            min_co = min_co / n_samples_co
            min_temp_co = min_temp_co / n_samples_co
            min_rawco = min_rawco / n_samples_co
            min_rawtemp_co = min_rawtemp_co / n_samples_co
            # Update thingspeak channel
            options = {'api_key':writekey,
            'field1':min_co,
            'field2':min_no2,
            'field3':min_rawco,
            'field4':min_rawno2,
            'field5':min_rawtemp_co,
            'field6':min_rawtemp_no2}
            try:
                req = requests.post(thingspk,data=options)
            except requests.exceptions.RequestException as e:
                print(timestamp + ": Didn't upload data")
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
    # Compress data if required
    # Is it the last minute of the day?
    if flags[1] == 1:
        if current_file_name != prev_file_name:
            subprocess.call(["gzip", prev_file_name])
            prev_file_name = current_file_name
    # Wait 5s for the next measurement --- OPTIONAL
    while int(time.time()) < (rec_time_s + 5):
        # wait a few miliseconds
        time.sleep(0.05)
print('I\'m done')
