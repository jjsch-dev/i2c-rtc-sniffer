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

parser = argparse.ArgumentParser(description="analyzes the I2C bus sniffer output of an RTC M41T81")
parser.add_argument('--version', action='version', version='%(prog)s 0.1.1')
parser.add_argument("-f", "--filename", required=True, help="input filename, in text format.")
parser.add_argument("-o", "--output", required=False, help="output filename, in json format (i2c_rtc.json).")

args = parser.parse_args()

json_data = []

def parse_record(record):
    global json_data

    if len(record) == 39:
        x = record.split("a")
        if x[0] == "sD0" and x[2] == "sD1":
            json_data.append("{{year:{}, month:{}, day:{}, hour:{}, "
                          "minute:{}, seconds:{}, tenths:{}, status:\'ok\'}}".format(x[10], x[9], x[8],
                                                                             x[6], x[5], x[4], x[3]))
            print("{}:{}:{}:{} {}/{}/{} ok".format(x[6], x[5], x[4], x[3],
                                                     x[8], x[9], x[10]))
        else:
            print("{data:{}, status:\'Error\'}".format(record))
    elif record != "sD0a0CasD1a31np":
        print("{data:{}, status:\'Error\'}".format(record))

# Press the green button in the gutter to run the script.
if __name__ == '__main__':

    try:
        with open(args.filename) as f:
            lines = f.readlines()  # list containing lines of file

            for line in lines:
                line = line.strip()  # remove leading/trailing white spaces
#                columns = [item.strip() for item in line.split(' ')]
#                dt = columns[1].split('/')
#                tm = columns[2].split(':')
                parse_record(line)

    except FileNotFoundError:
        print("error file not found")

    try:
        if args.output is not None:
            with open(args.output, 'w') as outfile:
                json.dump(json_data, outfile, indent=4)
    except FileNotFoundError:
        print("error json file not found")
