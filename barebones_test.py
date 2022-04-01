#!/usr/bin/env python3
import json
import websocket
import requests
import time
from datetime import datetime, timezone

# webnsockets TODO: config file not here
public_websocket = 'wss://ws.okex.com:8443/ws/v5/public?' # TODO check this broker and remove if not needed
#private_websocket = 'wss://ws.okex.com:8443/ws/v5/private?' # TODO check and remove the brokerIDd bit later

websocket.enableTrace(False)

class conn(object):
    # object for printing stuff to screen
    def __init__(self, name='test_connection'):
        self.name = name  # name of connection

        # Below relates only to the exchange you want to trade on (currently set up for one exchange at a time
        self.subscription_list = None  # dict holding all the products you want to see
        self.curves = {} # dict of fully interpolated yield curves by number of days (this is the main one to look at)
        self.d = None # keep track of raw messages from server

        self.res = None  # results of streaming data held here
        self.ping_clock = self.pm_ping_clock = time.time()  # keep track of when the last messages were received
        self.ping_time = 0  # keep track of how many seconds passed since last message update (needed for keepAlive function)
        self.pm_ping_time = 0  # keep track of how many seconds passed since last private message update (needed for keepAlive function)

        self.stack1 = None # temp holder for stack info
        self.stack_snap1 = None
        self.stack2 = None # temp holder for stack info
        self.stack_snap2 = None

        self.inst1 = 'BTC-USD-SWAP'
        self.inst2 = None

        self.t1 = None
        self.t1_total = 0
        self.t1_count = 0
        self.t1_min = None
        self.t1_max = None
        self.t1_mean = None
        self.t1_sd = None

        self.t2 = None
        self.t2_total = 0
        self.t2_count = 0
        self.t2_min = None
        self.t2_max = None
        self.t2_mean = None
        self.t2_sd = None

        self.t_since_last_msg = None
        self.t_last_msg = time.perf_counter_ns()
        self.t_last_min = None
        self.t_last_max = None
        self.t_last_mean = None
        self.t_last_count = 0
        self.t_last_total = 0

    def ws_message(self, ws, message):
        try:
            t_now = time.perf_counter_ns()
            self.t_since_last_msg = round((t_now - self.t_last_msg) / 1000000,1)
            self.t_last_msg = t_now
            self.t_last_count += 1
            self.t_last_total += self.t_since_last_msg

            if not self.t_last_min:
                self.t_last_min = self.t_last_max = self.t_last_mean = self.t_since_last_msg

            if self.t_since_last_msg < self.t_last_min:
                self.t_last_min = self.t_since_last_msg

            elif self.t_since_last_msg > self.t_last_max:
                self.t_last_max = self.t_since_last_msg

            self.t_last_mean = round(self.t_last_total / self.t_last_count,1)

            if self.t_last_count == 1000:
                self.t_last_count = 0
                self.t_last_min = self.t_last_max = self.t_last_mean = self.t_since_last_msg
                self.t_last_total = 0

            d = json.loads(message)  # raw storage of all incoming messages
            #print(d)

            if d['arg']['channel'] == 'books50-l2-tbt':
                if d['arg']['instId'] == self.inst1:

                    if d['action'] == 'snapshot':
                        pass
                        #self.stack1 = self.build_base(d['data'][0])
                        # take snap and build base stack1
                    else:
                        ts = int(d['data'][0]['ts'])
                        sysTS = (time.time() * 1000)
                        #print(f'sysTS={sysTS} serverTS={ts} diff = {round(sysTS-ts, 1)}')

                        # timer should be here
                        self.t1 = round(sysTS - ts, 1)

                        self.t1_count += 1
                        self.t1_total += self.t1

                        # initialise
                        if not self.t1_min:
                            self.t1_min = self.t1_max = self.t1_mean = self.t1

                        #cap min/max/mean
                        if self.t1 < self.t1_min:
                            self.t1_min = self.t1

                        elif self.t1 > self.t1_max:
                            self.t1_max = self.t1

                        self.t1_mean = round(self.t1_total / self.t1_count, 1)

                        _=(f'count={self.t1_count} time={self.t1} min/max/mean={self.t1_min}/{self.t1_max}/{self.t1_mean}    Time between msg updates={self.t_since_last_msg} {self.t_last_min}/{self.t_last_max}/{self.t_last_mean}')
                        print(_)
                        # reset afte 1000 datapoints
                        if self.t1_count == 1000:
                            self.t1_count = 0
                            self.t1_total = 0
                            self.t1_min = self.t1_max = self.t1

                else:
                    print(d)

        except Exception as e:
            print(e)


    def on_error(self, ws, e):
        print(e)

    def on_close(self, ws, *args):
        print(f'closed connection: and ping_time={self.ping_time} ping_clock={self.ping_clock}')

    def on_close_connection(self, ws, a, b):
        print('connection closed.')


    def ws_subscribe(self, ws):
        # subscribe to Public feeds based on instruments listed in subscription_list
        try:
            inst_list = []
            # DEBUG ONLY # test stack
            inst_list.append({"channel": "books50-l2-tbt", "instId": self.inst1})
            #inst_list.append({"channel": "books50-l2-tbt", "instId": self.inst2})

            # subscription request below
            sub_param = {"op": "subscribe", "args": inst_list}
            sub_str = json.dumps(sub_param)
            ws.send(sub_str)
            print(f'subscriptions added {sub_str}')
        except Exception as e:
            print (f'ws_subscribe error: {e}')


    def reconnect(self):
        self.connection_errors += 1  # track number of reconnections
        time.sleep(10)
        print(f'reconnecting and starting new threads')
        #_thread.start_new_thread(self.ws_thread_subscribe, ())  # launch a thread for derivatives prices
        #_thread.start_new_thread(self.periodic_events, ())  # launch a thread that does periodic updates

    """ stack functions go here """

    """ threaded functions go here ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ """
    def ws_thread_subscribe(self, *args):
        try:
            print('subscribing')
            self.ws = websocket.WebSocketApp(public_websocket, on_open=self.ws_subscribe, on_message=self.ws_message, on_error = self.on_error, on_close= self.on_close)
            #self.ws = websocket.WebSocketApp(private_websocket, on_open=self.ws_subscribe, on_message=self.ws_message, on_error = self.on_error, on_close= self.on_close)
            self.ws.run_forever()
        except Exception as e:
            print(e)


    def _get_timestamp(self):
        API_URL = 'https://www.okex.com'
        url = API_URL + '/api/v5/public/time'
        response = requests.get(url)
        if response.status_code == 200:
            res = (response.json())
            res = int(res['data'][0]['ts'])
        else:
            print ('nothing')

        return (res)


    ########################################################################################################
    def run_main(self):
        urlTS = self._get_timestamp()
        print(urlTS)
        sysTS = 1000* time.time()
        print('System vs server TS comparison')
        print(f'diff is {round(sysTS-urlTS, 1)} urlTS = {urlTS} vs system TS = {round(sysTS, 0)}')
        _ = input('....')

        self.ws_thread_subscribe()  # launch a thread for derivatives prices
        print('running...')
        c = 1
        while True:
            try:
                pass
            except Exception as e:
                print(e)


    ###########################################################################################################


Test = conn()
Test.run_main()
