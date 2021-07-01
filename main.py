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
from datetime import datetime

parser = argparse.ArgumentParser(description="analyzes the I2C bus sniffer output of an RTC M41T81")
parser.add_argument('--version', action='version', version='%(prog)s 0.1.9')
parser.add_argument("-f", "--filename", required=False, help="input filename, in text format.")
parser.add_argument("-o", "--output", required=False, help="output filename, in json format (i2c_rtc.json).")
parser.add_argument("-p", "--port", required=False, help="serial com port (win = COMxxx, linux = ttyXXXX)")
parser.add_argument("-b", "--baudrate", help="serial transfer rate (def = 230400)", default="230400")
parser.add_argument("-t", "--read_timeout", type=int, help="serial read timeout in mS (def = 10000)", default=10000)
parser.add_argument("-r", "--raw_filename", help="save the capture to a text file (raw_filename.txt)")

args = parser.parse_args()

records = 0
datetime_errors = []
halttime_errors = []
dt_last = datetime.min
datetime_invalid = []
datetime_out_sequence = []


# Although the decoded date and time comply with the i2c protocol, it can contain
# out-of-range values, for example, months greater than 12 and days greater than 31.
# This routine first verifies that the date is valid and then that it is greater
# than the previous.
def check_datetime(year, month, day, hour, minute, seconds):
    global dt_last, datetime_invalid, datetime_out_sequence, records

    str_log = "mark:{} year:{} "\
              "month:{} day:{} hour:{} "\
              "minute:{} seconds: {}".format(records,
                                             year,
                                             month,
                                             day,
                                             hour,
                                             minute,
                                             seconds)
    try:
        dt = datetime(year=(2000 + year), month=month, day=day,
                      hour=hour, minute=minute, second=seconds)
        if dt < dt_last:
            datetime_out_sequence.append(str_log)
        dt_last = dt
    except ValueError:
        datetime_invalid.append(str_log)


# It converts the digits of the date and time to an integer, and when
# it detects invalid characters it indicates it with -1.
def dt_to_int(val):
    try:
        return int(val)
    except:
        return -1


# The i2c frame is verified: date and alarm record, and also the validity of
# the date and if it is incremental.
def update_error_counter(data, line):
    global records, datetime_errors, halttime_errors
    # The record counters are only updated when the line contains a valid i2c frame.
    if data["status"] != "empty" and data["status"] != "ok" and data["status"] != "device unknow":

        str_log = "{} {} {}".format(records, line.strip(), data["status"])
        if data["word"] == "00":
            datetime_errors.append(str_log)
        elif data["word"] == "0C":
            halttime_errors.append(str_log)

    if data["status"] == "ok" and data["word"] == "00":
        check_datetime(year=dt_to_int(data["year"]),
                       month=dt_to_int(data["month"]),
                       day=dt_to_int(data["day"]),
                       hour=dt_to_int(data["hour"]),
                       minute=dt_to_int(data["minute"]),
                       seconds=dt_to_int(data["seconds"]))

    records = records + 1


# Updates the output console with the processing information from the i2c frame.
def show_record(data, line):
    if data["status"] != "empty" and data["status"] != "device unknow":
        line = line.strip()
        if data["word"] == "00":
            if data["status"] != "ok":
                print("{} {}".format(line, data["status"]))
            else:
                print("{}:{}:{}:{} {}/{}/{} {}".format(data["hour"],
                                                       data["minute"],
                                                       data["seconds"],
                                                       data["tenths"],
                                                       data["day"],
                                                       data["month"],
                                                       data["year"],
                                                       data["status"]))
        elif data["word"] == "0C":
            if data["status"] != "ok":
                print("{} {}".format(line, data["status"]))
        else:
            print("{}".format(line))


# Converts the alarm control register that is in string hexadecimal format
# to an integer. Returns 0xFF when it contains invalid characters.
def get_alarm_register(field):
    try:
        field = field.split("n")
        val = int(field[0], 16)
    except:
        val = 0xFF

    return val


# Verify that the register (byte read) contains valid information,
# between 0 and 255, and may contain an 'n' or 'p' to indicate the stop
# condition and the nak.
# Returns the character '.' to indicate empty value.
def get_val(registers, index):
    try:
        return registers[index]
    except:
        return "."


# The i2c frames must end with a NAK before the stop condition.
def is_nack_stop(register, index):
    val = get_val(register, index)
    try:
        return val[-2] == 'n' and val[-1] == 'p'
    except:
        return False


# Analyze the records sent by the tracker finished in LF CR.
# Returns False when there are no valid characters.
def parse_record(line):
    line = line.strip()  # remove leading/trailing white spaces

    json_data = {}
    if not line:
        json_data["status"] = "empty"
        return json_data

    ack = x = line.split("a")

    # The date and time of the RTC is obtained with the following procedure:
    # First write to the I2C address of the device (D0), the address of the RTC register pointer to zero.
    # And then it reads with D1 (1 indicates reading) the nine 8-bit registers that contain the date and
    # time, and in its 9 bits it sends ack, and ends with nak.
    if get_val(ack, 0) == "sD0":
        json_data["slave"] = "D0"
        if get_val(ack, 1) == "00":
            json_data["word"] = "00"
            if get_val(ack, 2) == "sD1":
                json_data["year"] = get_val(ack, 10)
                json_data["month"] = get_val(ack, 9)
                json_data["day"] = get_val(ack, 8)
                json_data["hour"] = get_val(ack, 6)
                json_data["minute"] = get_val(ack, 5)
                json_data["seconds"] = get_val(ack, 4)
                json_data["tenths"] = get_val(ack, 3)

                json_data["status"] = "ok" if is_nack_stop(ack, 11) else "nack-stop"
            else:
                json_data["status"] = "not-read"
        # Read the alarm register (0x0C), and verify if the halt update bit (6) is set.									*/
        elif get_val(ack, 1) == "0C":
            json_data["word"] = "0C"
            if get_val(ack, 2) == "sD1":
                if not get_alarm_register(get_val(ack, 3)) and 0x40:
                    json_data["status"] = "halt"
                elif is_nack_stop(ack, 3):
                    json_data["status"] = "ok"
                else:
                    json_data["status"] = "nack-stop"
            else:
                json_data["status"] = "not-read"
        else:
            json_data["status"] = "word unknow"
    elif len(ack) > 0:
        json_data["status"] = "device unknow"

    return json_data


# Processes i2c frames stored in a text file that has the following format:
# sD0a0CasD1a11np
# sD0a00asD1a16a39a09a16a03a08a06a21a80np
# sD0a0CasD1a11np
# sD0a00asD1a22a39a09a16a03a08a06a21a80np
# ....
# When finished, it displays the i2c frame analysis result and the validity
# of the date and time.
def parse_raw_file(filename):
    global records, datetime_errors, halttime_errors
    try:
        with open(filename) as f:
            lines = f.readlines()  # list containing lines of file

            for line in lines:
                data = parse_record(line)
                show_record(data, line)
                save_json(args.output, data)
                update_error_counter(data, line)
    except FileNotFoundError:
        print("error file not found")

    if len(datetime_errors):
        print("\ndatetime frame with errors\n")
        for item in datetime_errors:
            print(item)

    if len(halttime_errors):
        print("\nhalt timer frame with errors\n")
        for item in halttime_errors:
            print(item)

    if len(datetime_invalid):
        print("\ninvalid datetime\n")
        for item in datetime_invalid:
            print(item)

    if len(datetime_out_sequence):
        print("\ndatetime out of sequence\n")
        for item in datetime_out_sequence:
            print(item)

    print("\nfrom {} records, {} have error in frame datetime, "
          "{} error in frame halt time, "
          "{} have invalid datetime, "
          "{} dates are out of sequence".format(records,
                                        len(datetime_errors),
                                        len(halttime_errors),
                                        len(datetime_invalid),
                                        len(datetime_out_sequence)))


# Save i2c frames stored to a text file with the the following format:
# sD0a0CasD1a11np
# sD0a00asD1a16a39a09a16a03a08a06a21a80np
# sD0a0CasD1a11np
# sD0a00asD1a22a39a09a16a03a08a06a21a80np
# ....
def save_raw(filename, line):
    if filename is not None:
        try:
            line = line.strip()
            if line:
                line = "{}\r".format(line)
                with open(filename, "a") as f:
                    f.write(line)
                    f.close()
        except FileNotFoundError:
            print("error can't write raw file")


# It opens a serial port and waits for lines from the i2c frames that have the following format:
# sD0a0CasD1a11np
# sD0a00asD1a16a39a09a16a03a08a06a21a80np
# sD0a0CasD1a11np
# sD0a00asD1a22a39a09a16a03a08a06a21a80np
# ....
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
                    line = line.decode('utf-8')
                    data = parse_record(line)
                    save_json(args.output, data)
                    save_raw(args.raw_filename, line)
                    show_record(data, line)
            except serial.SerialException as e:
                print("error reading serial port")


# Save the i2c frame processing in json format:
# {"slave": "D0", "word": "00", "year": "21", "month": "06", "day": "04",
# "hour": "19", "minute": "19", "seconds": "51", "tenths": "80", "status": "ok"},
def save_json(file_name, data):
    if data["status"] == "empty" or data["status"] == "device unknow":
        return

    # Successful timer off bit read operations are not saved.
    if data["word"] == "0C" and data["status"] == "ok":
        return

    try:
        if file_name is not None:
            with open(file_name, 'a') as f:
                f.write("{},\r".format(json.dumps(data)))
                f.close()
    except FileNotFoundError:
        print("error json file not found")

if __name__ == '__main__':

    if args.port is not None:
        parse_serial_com(args.port, args.baudrate)
    elif args.filename is not None:
        parse_raw_file(args.filename)
