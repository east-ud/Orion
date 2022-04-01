import hmac
import json
import base64
#import time
from datetime import datetime, timezone, timedelta
import const as c
import pickle
import logging
import csv
import os
import time
from math import log10 , floor
# encryption
from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes
# import hashlib
from base64 import b64encode, b64decode
# stack management and checksum
import zlib
import itertools


log = logging.getLogger(__name__)
log.info("Hello logging: utils is on")

## Debuggint tools
def raise_sys_exit():
    raise SystemExit

def interactive_mode():
    try:
        __import__('code').interact(banner="launched interactive mode--- press ctrl+d to exit", exitmsg="exiting interactive mode now", local=dict(globals(), **locals()))

    except SystemExit:
        pass
    except ValueError as e:
        log.debug(f'value error from interactive mode: {e}')

def log_error(e):
    template = "on_error exception of type {0} occurred. Arguments:\n{1!r}"
    error_message = template.format(type(e).__name__, e.args)
    return error_message

## keys and hashing

#encrypt and decrypt files usiing AED 256 (source cryptodome)
def encryptfile(filename, key_location='./my_key.bin'):
    file_exists = os.path.isfile(key_location)
    if file_exists:
        log.error('key file already exists.  Need another filename')
        return

    key = get_random_bytes(32) # Use a stored / generated key
    key_decoded = b64encode(key).decode('utf-8')

    # Save the key to a file
    #file_out = open(key_location, "wb") # wb = write bytes
    file_out = open(key_location, "w") # wb = write bytes
    file_out.write(key_decoded)
    file_out.close()

    # === Encrypt ===
    # Open the input and output files
    buffer_size = 65536 # 64kb
    input_file = open(filename, 'rb')
    output_file = open(filename + '.ENK', 'wb')

    # Create the cipher object and encrypt the data
    cipher_encrypt = AES.new(key, AES.MODE_CFB)

    # Initially write the iv to the output file
    output_file.write(cipher_encrypt.iv)

    # Keep reading the file into the buffer, encrypting then writing to the new file
    buffer = input_file.read(buffer_size)
    while len(buffer) > 0:
        ciphered_bytes = cipher_encrypt.encrypt(buffer)
        output_file.write(ciphered_bytes)
        buffer = input_file.read(buffer_size)

    # Close the input and output files
    input_file.close()
    output_file.close()
    return key_decoded  # store this somewhere


def readenkjson(filename, key_location = './my_key.bin'):
    # === Decrypt ===
    # reads and loads enKrypted json file
    # first we check if a file has been given as key_location,
    # if not, assume its the key

    file_exists = os.path.isfile(key_location)
    if not file_exists:  # try key directly
        key_from_file = b64decode(key_location)
    else:
        file_in = open(key_location, "r") # Read string
        key_from_file = file_in.read() # key is in utf-8 format
        key_from_file = b64decode(key_from_file)
        file_in.close()

    # Open the input and output files
    buffer_size = 65536 # 64kb
    input_file = open(filename, 'rb')

    # Read in the iv
    iv = input_file.read(16)

    # Create the cipher object and encrypt the data
    cipher_encrypt = AES.new(key_from_file, AES.MODE_CFB, iv=iv)

    # Keep reading the file into the buffer, decrypting then writing to the new file
    buffer = input_file.read(buffer_size)
    full = ''

    while len(buffer) > 0:
        decrypted_bytes = cipher_encrypt.decrypt(buffer)
        decrypted_utf8 = decrypted_bytes.decode('utf-8').replace("'", '"')
        full = full + decrypted_utf8
        buffer = input_file.read(buffer_size)

    # Close the input and output files
    input_file.close()
    return json.loads(full)



def decryptfile(filename, key_location = './my_key.bin'):
    # === Decrypt ===
    # get key
    file_in = open(key_location, "rb") # Read bytes
    key_from_file = file_in.read() # This key should be the same
    key_from_file = b64decode(key_from_file)
    file_in.close()

    # Open the input and output files
    buffer_size = 65536 # 64kb
    input_file = open(filename, 'rb')
    output_file = open(filename[:-4] + '.DEK', 'wb')

    # Read in the iv
    iv = input_file.read(16)

    # Create the cipher object and encrypt the data
    cipher_encrypt = AES.new(key_from_file, AES.MODE_CFB, iv=iv)

    # Keep reading the file into the buffer, decrypting then writing to the new file
    buffer = input_file.read(buffer_size)
    while len(buffer) > 0:
        decrypted_bytes = cipher_encrypt.decrypt(buffer)
        output_file.write(decrypted_bytes)
        print(decrypted_bytes)
        buffer = input_file.read(buffer_size)

    # Close the input and output files
    input_file.close()
    output_file.close()

def sign(message, secretKey):
    mac = hmac.new(bytes(secretKey, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d)

def pre_hash(timestamp, method, request_path, body):
    return str(timestamp) + str.upper(method) + request_path + body

def get_header(api_key, sign, timestamp, passphrase):
    header = dict()
    header[c.CONTENT_TYPE] = c.APPLICATION_JSON
    header[c.OK_ACCESS_KEY] = api_key
    header[c.OK_ACCESS_SIGN] = sign
    header[c.OK_ACCESS_TIMESTAMP] = str(timestamp)
    header[c.OK_ACCESS_PASSPHRASE] = passphrase

    return header

def parse_params_to_str(params):
    url = '?'
    for key, value in params.items():
        url = url + str(key) + '=' + str(value) + '&'

    return url[0:-1]

def signature(timestamp, method, request_path, body, secret_key):
    if str(body) == '{}' or str(body) == 'None':
        body = ''
    message = str(timestamp) + str.upper(method) + request_path + str(body)
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.B64encode(d)


### date/time tools
def get_timestamp():
    now = datetime.now(timezone.utc)
    t = now.isoformat("T", "milliseconds")
    t = t.replace("+00:00", "Z")
    return t

def human_time(timestamp):
    ts = datetime.fromtimestamp(int(timestamp) / 1000)

    #ts = datetime.strftime('%A %d-%m-%Y, %H:%M:%S')
    return ts

def elapsed_seconds(timestamp):
    elapsed = datetime.now() - (datetime.fromtimestamp(int(timestamp) / 1000))
    elapsed = elapsed.seconds
    return elapsed

def elapsed_ms(timestamp):
    elapsed = datetime.now()*1000 - (datetime.fromtimestamp(int(timestamp) / 1000))
    elapsed = elapsed.seconds
    return elapsed


def calc_days_rem(product):
    expiry = product[-6:]
    date = datetime(year=int('20' + expiry[0:2]), month = int(expiry[2:4]), day = int(expiry[4:6]), hour = 9)  # TODO: confirm if expiry is noon

    days_rem = date - datetime.now()
    days_rem = round(days_rem.total_seconds()/(60*60*24),5)
    #ays_rem = (days_rem.seconds)
    return days_rem

def calc_days_rem_expiry(expiry):
    date = datetime(year=int('20' + expiry[0:2]), month = int(expiry[2:4]), day = int(expiry[4:6]), hour = 9)  # TODO: confirm if expiry is noon

    days_rem = date - datetime.now()
    days_rem = round(days_rem.total_seconds()/(60*60*24),5)
    #ays_rem = (days_rem.seconds)
    return days_rem

def calc_days_rem_direct(expiry):
    try:
        #date = datetime(year=int('20' + expiry[0:2]), month = int(expiry[2:4]), day = int(expiry[4:6]), hour = 12)  # TODO: confirm if expiry is noon
        days_rem = expiry - datetime.now()
        days_rem = round(days_rem.total_seconds()/(60*60*24),5)
        #ays_rem = (days_rem.seconds)
        return days_rem
    except Exception as e:
        log.error(f'calc days rem direct: {e}')

def convert_to_date(expiry):
    try:
        date = datetime(year=int('20' + expiry[0:2]), month = int(expiry[2:4]), day = int(expiry[4:6]), hour = 12)  # TODO: confirm if expiry is noon
        return date
    except Exception as e:
        log.error(f'convert to date: {e} input was {expiry}')

def get_tom_date():

    tom = datetime.now() + timedelta(days=1)
    tom = datetime(tom.year, tom.month, tom.day, 12, 0, 0) # adjust the time to match expiries
    return tom


## read/write

def write_this(this, file_name, dir_name='.', add_time=True):
    # append a dictionary line to a file
    header_present = False

    def write_as_dict():
        with open(logfile, 'a') as f:
            if add_time:  # option to include timestamp
                dt_now = {'time': datetime.now()}
                save_row = {**dt_now, **this}  # just combines the two dictionaries
            else:
                save_row = this  # just combines the two dictionaries

            w = csv.DictWriter(f, save_row.keys())
            if not file_exists:
                w.writeheader()  # file doesnt exist yet, write a header
            w.writerow(save_row)

    try:
        logfile = os.path.join(dir_name, file_name)
        file_exists = os.path.isfile(logfile)
        now = datetime.now()

        if type(this) == dict:
            write_as_dict()

        elif type(this) == list:
            if type(this[0]) == dict:  # if we have a list of dicts
                with open(logfile, 'a') as f:
                    for row in this:
                        if add_time:  # option to include timestamp
                            dt_now = {'time': now}
                            row_wStamp = {**dt_now, **row}  # just combines the two dictionaries
                        else:
                            row_wStamp = this  # just combines the two dictionaries

                        w = csv.DictWriter(f, row_wStamp.keys())
                        if not file_exists and not header_present:
                            w.writeheader()  # file doesnt
                            header_present = True


                        w.writerow(row_wStamp)

            else:
                with open(logfile, 'a') as f:
                    if add_time:  # option to include timestamp
                        save_row = [datetime.now()] + this  # just combines the two dictionaries
                    else:
                        save_row = this

                    w = csv.writer(f)
                    w.writerow(save_row)

    except Exception as e:
        log.error(f'error writing: {this} as {e}')

# saving objects (dicts, etc)
def save_obj(obj, name, location = './'):
    with open(location + name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def load_obj(name, location = './'):
    with open(location + name + '.pkl', 'rb') as f:
        return pickle.load(f)


# Send email

def send_email(subject="subject=", body="body="):
    log.debug('email utility started')
    import configparser
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    config = configparser.RawConfigParser()
    config.read('.orion_rc')

    mail_content = body

    #The mail addresses and password

    sender_address = config['email']['sender_address']
    sender_pass = config['email']['sender_pass']
    receiver_address = config['email']['receiver_address']
    log.info('details received from config file')

    #Setup the MIME
    message = MIMEMultipart()
    message['From'] = sender_address
    message['To'] = receiver_address
    message['Subject'] = subject
    #The body and the attachments for the mail
    message.attach(MIMEText(mail_content, 'plain'))
    #Create SMTP session for sending the mail
    session = smtplib.SMTP('smtp.gmail.com', 587) #use gmail with port
    session.starttls() #enable security
    session.login(sender_address, sender_pass) #login with mail_id and password
    text = message.as_string()
    session.sendmail(sender_address, receiver_address, text)
    session.quit()
    log.info('Email Sent')


class TimerError(Exception):
    """An exception used to report errors in use of Timer class"""

class eztimer:
    def __init__(self, text="{:0,.4f}ms", sample=1000, ignore_restarts=True, name='timer'):
        self.name = name
        self.timer = 0
        self._start_time = None
        self.text = text
        self.elapsed = None
        self.counts = 0
        self.incomplete_counts = 0
        self.mean = None
        self.min = None
        self.max = None
        #self.sd = None  # standard deviation
        self.sample = sample  # takes a sample size for averaging
        self.ignore_restarts = ignore_restarts

    def start(self):
        if self._start_time is not None and self.ignore_restarts is False:
            # if timer is already running and you try to start it again, you can choose to ignore
            #log.error('Timer is running.  Use stop() to stop it')
            raise TimerError(f"Timer is running.  Use .stop() to stop it")

        elif self._start_time is not None and self.ignore_restarts is True:
            self.incomplete_counts += 1

            self._start_time = time.perf_counter_ns()

            # we use the previous start_time and ignore this one.  This is useful in situations
            # where a loop may have errors and does not complete, but you want to measure those incompletions
            # as part of performance

        elif self._start_time is None:
            self._start_time = time.perf_counter_ns()

    def stop(self):
        if self._start_time is None:
            #log.error('Timer is not running.  Use start() to start()')
            raise TimeoutError(f"Timer is not running.  Use .start() to start") # better to keep this silent
        # stop timer and report elapsed time
        elif self._start_time is not None:
            elapsed_time = (time.perf_counter_ns() - self._start_time) / 1000000  # convert back to milliseconds from nanoseconds

            self._start_time = None
            # Use the user provided string as the output string
            #print("")
            self.text = self.text.format(elapsed_time)
            self.timer += elapsed_time

            self.elapsed = round(elapsed_time, 1)
            # Add times measured by the same timers

            if self.min == None:
                self.min = self.elapsed
            if self.max == None:
                self.max = self.elapsed

            if self.elapsed > self.max:
                self.max = self.elapsed
            elif self.elapsed < self.min:
                self.min = self.elapsed

            self.counts += 1

            self.mean = round((self.timer / self.counts), 1)  # get mean

            if self.counts >= self.sample:
                # sample size reached
                #self.per_incomplete = round(100*(self.incomplete_counts / self.sample), 2) # percentage incomplete
                self.max, self.min, self.timer = None, None, 0 # reset coutners
                self.counts = 1  # reset counters
                self.incomplete_counts = 0 # reset counters

            return round(elapsed_time, 1)

class latency_timer:
    def __init__(self, text="{:0,.4f}ms", sample=1000, name = 'latency_timer'):
        # this will compare ts(stop) to last ts(start)

        self.name = name
        self.ts = None # this is timestamp from server
        self.timer = 0
        self._start_time = None
        self.text = text
        self.elapsed = None
        self.counts = 0
        self.mean = None
        self.min = None
        self.max = None
        #self.sd = None  # standard deviation
        self.sample = sample  # takes a sample size for averaging

        # initialise
        # if no prev time stamp, then current one is start

    def update(self, ts):
        try:

            self.ts = int(ts)
            self.elapsed = round((time.time() * 1000) - self.ts, 1)

            # reset start time
            self.text = self.text.format(self.elapsed)
            self.timer += self.elapsed

            # Add times measured by the same timers

            if self.min == None:
                self.min = self.elapsed
            if self.max == None:
                self.max = self.elapsed

            if self.elapsed > self.max:
                self.max = self.elapsed
            elif self.elapsed < self.min:
                self.min = self.elapsed

            self.counts += 1

            self.mean = round((self.timer / self.counts), 1)  # get mean

            if self.counts >= self.sample:  # burn first data point as it is usuallyu very long compared to reast
                # sample size reached
                #self.per_incomplete = round(100*(self.incomplete_counts / self.sample), 2) # percentage incomplete
                self.max, self.min, self.timer = None, None, 0 # reset coutners
                self.counts = 0  # reset counters

        #return round(self.elapsed, 2)
        except Exception as e:
            log.error(f'timer error: {e}', exc_info=True)
            return 0

class requests_timer:
    def __init__(self, period=2000, name='requests_timer'):
        # measure how many tickets/2000 ms
        # measures are in number of requests per period

        self.name = name
        self.last_stamp = None
        self.total_elapsed = 0
        self.elapsed = 0
        self.counts = 0
        self.batches = 0
        self.mean = None
        self.min = None
        self.max = None
        self.min_batches = None
        self.max_batches = None
        self.period = period

        # initialise
        # if no prev time stamp, then current one is start

    def lap(self):
        # time since last stamp
        now = time.perf_counter_ns()
        if self.last_stamp:
            return round((now - self.last_stamp) / 1000000, 1)  # convert back to milliseconds from nanoseconds
        else:
            return 0

    def update(self, n=1):
        # update is also start()
        try:
            if not self.last_stamp:
                # first update sets initial start time
                self.last_stamp = time.perf_counter_ns()
                return
            elif self.last_stamp:
                now = time.perf_counter_ns()

                self.elapsed = round((now - self.last_stamp) / 1000000, 1)  # time since last update
                self.total_elapsed += round(self.elapsed, 0)
                self.last_stamp = now

                if self.elapsed >= self.period or self.total_elapsed >= self.period:
                    self.elapsed = self.total_elapsed = self.total_elapsed % self.period  # get remainder for current period

                    if not self.min:
                        self.min = self.counts
                        self.min_batches = self.batches
                    if not self.max:
                        self.max = self.counts
                        self.max_batches = self.batches

                    if self.counts > self.max:
                        self.max = self.counts
                    elif self.counts < self.min:
                        self.min = self.counts

                    if self.batches > self.max_batches:
                        self.max_batches = self.batches
                    elif self.batches < self.min_batches:
                        self.min_batches = self.batches

                    self.counts = n  # reset counters
                    self.batches = 1

                else:
                    self.counts += n  # add n new counts to timer (if you are doing a batch update)
                    self.batches += 1
                    self.mean = round(self.total_elapsed / self.counts, 1)

        except Exception as e:
            log.error(f'timer error: {e}', exc_info=True)
            return 0

class regen_timer:
    def __init__(self, period=60000, name='regen_timer'):
        # measure how many tickets/2000 ms
        # measures are in number of requests per period

        self.name = name
        self.pre_hedged = True
        self.hedge_priority = False

        self.start = None
        self.period = period

        # initialise
        # if no prev time stamp, then current one is start

    def lap(self):
        # time since last stamp
        now = time.perf_counter_ns()
        if self.start:
            return round((now - self.start) / 1000000, 1)  # convert back to milliseconds from nanoseconds
        else:
            return 0

    def widen_factor(self):
        # widens out to 60
        now = time.perf_counter_ns()
        if self.start:
            WF = round((self.period / ((now - self.start) / 1000000)) - 1, 3)   # a number that widens out and then goes to 0 over the course of a minute

            if WF < 0:  # reset
                WF = 0
                self.start = None
            elif WF > 20:
                WF = 20

            return WF
        else:
            return 0

    def percentage(self):
        # returns percentage regenration completed
        now = time.perf_counter_ns()
        if self.start:
            percent = round(((now - self.start) / 1000000) / self.period, 3)   # percentage of regen time completed
            if percent > 1:  # reset
                percent = 1
                self.start = None
            return percent
        else:
            return 1

    def cancel_regen(self):
        # cancels regen
        self.start = None
        self.pre_hedged = True
        self.hedge_priority = False

    def start_regen(self):
        # update is also start()
        try:
            #  TODO, handle if start_regen already running... this should add another bump to it
            now = time.perf_counter_ns()

            self.start = now
            self.pre_hedged = False  # refers to initil zero time hedging required (like moving prices out of the way)
            self.hedge_priority = True

        except Exception as e:
            log.error(f'timer error: {e}', exc_info=True)
            return 0



## config setup

def create_config():
    import configparser
    config = configparser.ConfigParser()
    config['email'] = {'sender_address': 'sender@something.com',
                         'sender_pass': 'apasswordgoeshere',
                         'receiver_address': 'sender@something.com'}

    config['email_updates'] = {}
    config['email_updates']['user1'] = 'hg'

    config['directories'] = {'logs': './logs',
            'encoded_key1': 'EMPTY',
            'encoded_key2': 'EMPTY'
            }

    config['yield_parameters'] = {}
    config['yield_parameters']['set_denominator'] = 'index'  #this can be index or spot price
    config['yield_parameters']['day_count'] = '365'

    with open('.orion_rc', 'w') as configfile:
      config.write(configfile)


## managing stack and checksum
def get_signed_value(unsigned_value):
    bitsize = 32
    return unsigned_value if unsigned_value < (1 << bitsize-1) else unsigned_value - (1 << bitsize)

def create_checksum_string(bids, asks):
    bids = (f"{price}:{qty}" for price, qty, _, _ in bids)
    asks = (f"{price}:{qty}" for price, qty, _, _ in asks)
    merged = [item
              for pair in itertools.zip_longest(bids, asks)
              for item in pair
              if item is not None]
    return ":".join(merged)

def check_checksum(item):
    bids = item['bids'][:25]
    asks = item['asks'][:25]
    string = create_checksum_string(bids, asks)
    checksum = item['checksum']
    unsigned = zlib.crc32(string.encode('utf8'))
    signed = get_signed_value(unsigned)
    return signed == checksum

def update_side(old_levels, new_levels, reverse):
    level_map = {k[0]: k for k in old_levels}

    for update in new_levels:
        price, qty, _, _ = update
        if qty == 0:
            level_map.pop(price, None)
        else:
            level_map[price] = update
    return [level_map[k] for k in sorted(level_map.keys(), reverse=reverse)]


## Others

def checkfloat(x):
    try:
        x = f"{float(x):.5g}"

        return x
    except Exception:
        return x

def round_it(x, sig=5):
    try:
        if isinstance(x, str):
            x = float(x)
        if x != 0 and x is not None:
            x = round(x, sig-int(floor(log10(abs(x))))-1)
            return x
        elif x == 0 or x is None:
            return 0
    except Exception as e:
        log.error(f'round_it error: {e}\n x={x} and type is = {type(x)}')
