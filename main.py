"""Analyzes the traffic of an RTC M41T8x.
   It requires hardware based on the USI of the ATtiny85 and the code
   developed by: Peter Dannegger

   https://www.avrfreaks.net/projects/i2c-twi-sniffer

   that generates an output through a serial port with the
   format: sD0a00asD1a55a06a30a16a03a01a06a21a80np.

   NOTE: for generate win32 use: WINEARCH=win32 WINEPREFIX=~/win32 wine pyinstaller.exe --onefile xml_datetime.py
      for run win32: WINEARCH=win32 WINEPREFIX=~/win32 sudo wine ./xml_datetime.exe

"""
import argparse
import json
import serial

parser = argparse.ArgumentParser(description="analyzes the I2C bus sniffer output of an RTC M41T81")
parser.add_argument('--version', action='version', version='%(prog)s 0.1.4')
parser.add_argument("-f", "--filename", required=False, help="input filename, in text format.")
parser.add_argument("-o", "--output", required=False, help="output filename, in json format (i2c_rtc.json).")
parser.add_argument("-p", "--port", required=False, help="serial com port (win = COMxxx, linux = ttyXXXX)")
parser.add_argument("-b", "--baudrate", help="serial transfer rate (def = 230400)", default="230400")
parser.add_argument("-t", "--read_timeout", type=int, help="serial read timeout in mS (def = 10000)", default=10000)

args = parser.parse_args()

json_data = []

# Analyze the records sent by the tracker finished in LF CR.
# Returns False when there are no valid characters.
def parse_record(line):
    global json_data
    line = line.strip()  # remove leading/trailing white spaces

    # The date and time of the RTC is obtained with the following procedure:
    # First write to the I2C address of the device (D0), the address of the RTC register pointer to zero.
    # And then it reads with D1 (1 indicates reading) the nine 8-bit registers that contain the date and
    # time, and in its 9 bits it sends ack, and ends with nak.
    if len(line) == 39:
        x = line.split("a")
        if len(x) == 12 and x[0] == "sD0" and x[2] == "sD1":
            json_data.append("{{year:{}, month:{}, day:{}, hour:{}, "
                             "minute:{}, seconds:{}, tenths:{}, status:\'ok\'}}".format(x[10], x[9], x[8],
                                                                                        x[6], x[5], x[4], x[3]))
            print("{}:{}:{}:{} {}/{}/{} ok".format(x[6], x[5], x[4], x[3],
                                                   x[8], x[9], x[10]))
        else:
            json_data.append("{{data:{}, status:\'nak\'}}".format(line))
            print("{} nak".format(line))
    elif line != "sD0a0CasD1a31np" and len(line) > 0:
        print("{}, unk".format(line))
        json_data.append("{{data:{}, status:\'unk\'}}".format(line))
    else:
        return False
    return True


def parse_file(filename):
    try:
        with open(filename) as f:
            lines = f.readlines()  # list containing lines of file

            for line in lines:
                parse_record(line)
    except FileNotFoundError:
        print("error file not found")


def parse_serial_com(port, baudrate):
    device = None
    try:
        device = serial.Serial(port, baudrate, 8, 'N', 1, timeout=args.read_timeout/1000)
    except:
        print("error can't open the serial port: {}".format(port))

    if device is not None:
        while True:
            try:
                line = device.readline()
                if line:
                    if parse_record(line.decode('utf-8')):
                        save_json(args.output)
            except serial.SerialException as e:
                print("error reading serial port")


def save_json(file_name):
    try:
        if file_name is not None:
            with open(file_name, 'w') as outfile:
                json.dump(json_data, outfile, indent=4)
    except FileNotFoundError:
        print("error json file not found")

if __name__ == '__main__':

    if args.port is not None:
        parse_serial_com(args.port, args.baudrate)
    elif args.filename is not None:
        parse_file(args.filename)

    save_json(args.output)
