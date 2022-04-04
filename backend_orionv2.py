#!/usr/bin/env python3
import asyncio
import base64
import datetime
from datetime import datetime, timezone
import pandas as pd
import const as c
import hmac
import json
import time
import zlib
import logging
import requests
import websockets
import pyinputplus as pyip
import utils
import configparser
import os

#extras
from utils import round_it
from const import *
import exceptions

# get config details
config = configparser.RawConfigParser()
if os.path.isfile('.orion_rc'):
    config.read('.orion_rc')
else:
    utils.create_config()
    config.read('.orion_rc')

# set up logging (order of imports somehow affects how this works)
dir_name = config['directories']['logs']
filename = datetime.now().strftime("%H%M_%d%m")
filename = filename + '_orion'
suffix = '.log'

#logging setup
logfile = os.path.join(dir_name, filename + suffix)
logging.basicConfig(format='%(asctime)s:%(msecs)d:%(levelname) -8s [%(filename)s:%(lineno)d] %(message)s', datefmt='%H:%M:%S', level=logging.DEBUG, filename=logfile)
#logging.basicConfig(format='%(asctime)s:%(msecs)d:%(levelname) -8s [%(filename)s:%(lineno)d] %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=logging.WARNING, filename=logfile)
#$logging.basicConfig(format='%(asctime)s:%(msecs)d:%(levelname) -8s [%(filename)s:%(lineno)d] %(message)s', datefmt='%H:%M:%S', level=logging.INFO, filename=logfile)
logging.getLogger("asyncio").setLevel(logging.DEBUG)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
log = logging.getLogger(__name__)
log.info("Hello logging!: back_end is up")


#  URL locations
public_url = "wss://ws.okex.com:8443/ws/v5/public"
private_url = "wss://ws.okex.com:8443/ws/v5/private"

def partial(res):
    data_obj = res['data'][0]
    bids = data_obj['bids']
    asks = data_obj['asks']
    instrument_id = res['arg']['instId']
    return bids, asks, instrument_id

def get_timestamp():
    now = datetime.datetime.now()
    t = now.isoformat("T", "milliseconds")
    return t + "Z"

def get_server_time():
    url = "https://www.okex.com/api/v5/public/time"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['data'][0]['ts']
    else:
        return ""


def get_local_timestamp():
    return int(time.time())


def login_params(timestamp, api_key, passphrase, secret_key):
    message = timestamp + 'GET' + '/users/self/verify'

    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)

    login_param = {"op": "login", "args": [{"apiKey": api_key,
                                            "passphrase": passphrase,
                                            "timestamp": timestamp,
                                            "sign": sign.decode("utf-8")}]}
    login_str = json.dumps(login_param)
    return login_str


def update_bids(res, bids_p):
    # 获取增量bids数据
    bids_u = res['data'][0]['bids']
    # print('new bids：' + str(bids_u))
    # print('len new bids：' + str(len(bids_u)))
    # bids合并
    for i in bids_u:
        bid_price = i[0]
        for j in bids_p:
            if bid_price == j[0]:
                if i[1] == '0':
                    bids_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                bids_p.append(i)
    else:
        bids_p.sort(key=lambda price: sort_num(price[0]), reverse=True)
        # print('sorted total bids：' + str(bids_p) + '，len total bids：' + str(len(bids_p)))
    return bids_p


def update_asks(res, asks_p):
    # asks
    asks_u = res['data'][0]['asks']
    # print('***new offers：' + str(asks_u))
    # print('len new offers：' + str(len(asks_u)))
    # offers
    for i in asks_u:
        ask_price = i[0]
        for j in asks_p:
            if ask_price == j[0]:
                if i[1] == '0':
                    asks_p.remove(j)
                    break
                else:
                    del j[1]
                    j.insert(1, i[1])
                    break
        else:
            if i[1] != "0":
                asks_p.append(i)
    else:
        asks_p.sort(key=lambda price: sort_num(price[0]))
        # print('Sorted offers：' + str(asks_p) + '，len total offers:' + str(len(asks_p)))
    return asks_p


def sort_num(n):
    if n.isdigit():
        return int(n)
    else:
        return float(n)


def check(bids, asks):
    # bid
    bids_l = []
    bid_l = []
    count_bid = 1
    while count_bid <= 25:
        if count_bid > len(bids):
            break
        bids_l.append(bids[count_bid - 1])
        count_bid += 1
    for j in bids_l:
        str_bid = ':'.join(j[0: 2])
        bid_l.append(str_bid)
    # offer
    asks_l = []
    ask_l = []
    count_ask = 1
    while count_ask <= 25:
        if count_ask > len(asks):
            break
        asks_l.append(asks[count_ask - 1])
        count_ask += 1
    for k in asks_l:
        str_ask = ':'.join(k[0: 2])
        ask_l.append(str_ask)
    num = ''
    if len(bid_l) == len(ask_l):
        for m in range(len(bid_l)):
            num += bid_l[m] + ':' + ask_l[m] + ':'
    elif len(bid_l) > len(ask_l):
        # bid ask
        for n in range(len(ask_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(ask_l), len(bid_l)):
            num += bid_l[l] + ':'
    elif len(bid_l) < len(ask_l):
        # ask  bid
        for n in range(len(bid_l)):
            num += bid_l[n] + ':' + ask_l[n] + ':'
        for l in range(len(bid_l), len(ask_l)):
            num += ask_l[l] + ':'

    new_num = num[:-1]
    int_checksum = zlib.crc32(new_num.encode())
    fina = change(int_checksum)
    return fina


def change(num_old):
    num = pow(2, 31) - 1
    if num_old > num:
        out = num_old - num * 2 - 2
    else:
        out = num_old
    return out

def adj_bps(px, bps):
    # adjusts price by required bps
    new = px * (1 + (bps / 10000))
    return utils.round_it(new, 6)

# unsubscribe channels
async def unsubscribe(url, api_key, passphrase, secret_key, channels):
    async with websockets.connect(url) as ws:
        # login
        timestamp = str(get_local_timestamp())
        login_str = login_params(timestamp, api_key, passphrase, secret_key)
        await ws.send(login_str)
        # print(f"send: {login_str}")

        res = await ws.recv()
        print(f"recv: {res}")

        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        print(f"send: {sub_str}")

        res = await ws.recv()
        print(f"recv: {res}")


# unsubscribe channels
async def unsubscribe_without_login(url, channels):
    async with websockets.connect(url) as ws:
        # unsubscribe
        sub_param = {"op": "unsubscribe", "args": channels}
        sub_str = json.dumps(sub_param)
        await ws.send(sub_str)
        print(f"send: {sub_str}")

        res = await ws.recv()
        print(f"Unsubscribe res= {res}")

class conn(object):
    # object for printing stuff to screen
    def __init__(self):

        # Below relates only to the exchange you want to trade on (currently set up for one exchange at a time
        self.name = 'connection class'
        self.orion_version = 'Orion v2.1 (Jan22)' # version 2.1 is atually fast
        self.api_key = None
        self.passphrase = None
        self.secret_key = None

        self.use_server_time = False

        # timers
        self.main_timer = utils.eztimer(name='Main timer')
        self.stack_update_timer = utils.eztimer(name='stack update', ignore_restarts = False)
        self.get_data_timer = utils.eztimer(name='ws1: public data freq')
        self.overwatch_timer = utils.eztimer(name='overwatch')
        self.update_risk_timer = utils.eztimer(name='update_risk')
        self.get_pm_timer = utils.eztimer(name='ws2: private data freq')
        self.req_timer = utils.requests_timer(name='req_timer')  # requests timer
        self.heartbeat_timer = utils.eztimer(name='heartbeat_timer')  # requests timer
        self.vwap_timer = utils.eztimer(name='vwap_timer')  # requests timer
        self.update_tickets_timer = utils.eztimer(name='update_tickets_timer')  # requests timer
        self.check_if_update_req_timer = utils.eztimer(name='check_if_update_req')
        self.calc_targets_timer = utils.eztimer(name='calc_targets')
        self.trade_timer = utils.eztimer(name='trade_timer')  # requests timer


        # regen timer
        self.regen_timer = utils.regen_timer()  # regeneration timer

        # overwatch
        self.balance_and_position = None  # rename this disaster of a name
        self.positions = None
        self.account = None
        self.risk = {}  # dict of ccys and risk

        self.fill_count = 0 # count number of fills
        self.all_NOP = 0  # NOP from all trades executed during session
        self.prev_allNOP = 0 # store prev NOP here for comparisons
        self.all_cumPNL = 0  # cumulative sum of value from hedging (postive is money)
        self.prev_cumPNL = 0  # track prev cumul PNL
        self.all_unbPNL = 0  # PNL from positions that have not yet been hedged
        self.fwds_PNL = 0  # captures PNL from bid/offer on fwds
        self.all_unbPNL_longs = 0  # PNL from positions that have not yet been hedged
        self.all_unbPNL_shorts = 0  # PNL from positions that have not yet been hedged

        self.all_longNOP = 0  # NOP from all trades executed during session
        self.all_shortNOP = 0  # NOP from all trades executed during session
        self.all_lastLongPx = None  # last long price
        self.all_lastShortPx = None  # last short price
        self.all_avgPx = None  # NOP from all trades executed during session
        self.all_avgLongPx = None  # NOP from all trades executed during session
        self.all_avgShortPx = None  # NOP from all trades executed during session
        self.all_count = 0  # counter for number of round-trips done

        self.all_avgVal = 0  # value of unhedged positions
        self.all_longVal = 0
        self.all_shortVal = 0

        self.SL_amnt = -1  # stop loss trigger for unhedged postitions

        # Mean reversion portfolio
        self.MR_unbPNL = 0  # PNL from positions that have not yet been hedged
        self.MR_longNOP = 0
        self.MR_longVal = 0
        self.MR_shortNOP = 0
        self.MR_shortVal = 0
        self.MR_NOP = 0
        self.MR_avgLongPx = None
        self.MR_avgShortPx = None
        self.MR_bid_BE_dist = None
        self.MR_off_BE_dist = None

        self.total_NOP = 0 # addition of two portfolios

        self.orion_orders = []
        self.fills = []
        self.orders_hist = []
        self.okex_orders = []
        self.test = []  # used to test appending process

        self.stack_swap = {'bids': [], 'offers': []}  # stacks are held here
        self.stack_fwd1 = {'bids': [], 'offers': []}
        self.stack_fwd2 = {'bids': [], 'offers': []}
        self.stack_fwd3 = {'bids': [], 'offers': []}

        # TODO: automate popoualting this
        self.ccy = 'ADA'

        self.index_label = self.ccy + '-USD'
        self.swap = self.ccy + '-USD-SWAP'
        self.fwd1 = self.ccy + '-USD-220408'
        self.fwd2 = self.ccy + '-USD-220415'
        self.fwd3 = self.ccy + '-USD-220624'
        self.fwd4 = self.ccy + '-USD-220930'
        #self.fwd4 = self.ccy + '-USD-220930'

        # list of instruments to trade live
        self.included = {'mmSwB', 'mmSwO', 'mmF1B', 'mmF1O', 'mmF2B', 'mmF2O', 'mmF3B', 'mmF3O'}  # list of instruments we want trading
        self.hedge = {'mmSwB': True, 'mmSwO': True, 'mmF1B': True, 'mmF1O': True, 'mmF2B': True, 'mmF2O': True, 'mmF3B': True, 'mmF3O': True}  # list of instruments used for hedging

        self.days_rem_fwd1 = round(utils.calc_days_rem_expiry(self.fwd1[-6:]), 2)
        self.days_rem_fwd2 = round(utils.calc_days_rem_expiry(self.fwd2[-6:]), 1)
        self.days_rem_fwd3 = round(utils.calc_days_rem_expiry(self.fwd3[-6:]), 1)

        # track latency of price feeds
        self.latencyT_swap = utils.latency_timer(name='ws1: latency swap')
        self.latencyT_f1 = utils.latency_timer(name='ws1: latency fwd1')
        self.latencyT_f2 = utils.latency_timer(name='ws1: latency fwd2')
        self.latencyT_f3 = utils.latency_timer(name='ws1: latency fwd3')
        self.latencyT_idx = utils.latency_timer(name='ws1: latency index')
        #self.pm_latency = utils.latency_timer(name='ws2: Private data latency')

        # holder for index, vwap and best bid/offer prices
        self.idxPx = None  # price of index
        self.vwap_swap = {'bid': None, 'offer': None}  # reg vwap prices
        self.vwap_fwd1 = {'bid': None, 'offer': None}
        self.vwap_fwd2 = {'bid': None, 'offer': None}
        self.vwap_fwd3 = {'bid': None, 'offer': None}
        self.min_swap = {'bid': None, 'offer': None}  # min vwap prices
        self.min_fwd1 = {'bid': None, 'offer': None}
        self.min_fwd2 = {'bid': None, 'offer': None}
        self.min_fwd3 = {'bid': None, 'offer': None}

        self.swap_dist_bbid = 999
        self.swap_dist_boffer = 999
        self.fwd1_dist_bbid = 999
        self.fwd1_dist_boffer = 999
        self.fwd2_dist_bbid = 999
        self.fwd2_dist_boffer = 999
        self.fwd3_dist_bbid = 999
        self.fwd3_dist_boffer = 999

        self.conf = []  # confirmed system wide trades
        self.pnd_conf = []  # pending confirmation system wide trades
        self.prev_conf = []  # track changes
        self.prev_pnd_conf = []  # track changes

        # starting bid/offer spreads  TODO: to be adjusted based on moving average of market bid/offer
        #self.i1bo_sprd = 5  # inst1 bid to mid spread


        self.safety_shutdown = False
        self.connected_private = False
        self.data_flow = False  # turns true when all data points are coming in
        self.notification = 'All good'
        self.msg1 = ""
        self.msg2 = None

        self.pm = None  # private connection message

        # loads up existing call_levels/executed trades (if exists) and starts monitoring them (self.monitor) on start

        self.reset_dist()
        self.reset_live_dists()  # resets indicator of live prices as spreads on exchange
        try:
            # load order watch file, if not there, create it
            if not os.path.isfile('.orion_odas.pkl'):
                utils.save_obj([], '.orion_odas')  # and save it just in case something lost along the way
                log.info('creating initial order watch file')
            else:
                self.orion_odas = utils.load_obj('.orion_odas')
                log.info('loaded order watch file')

            # load executed orders file, if not there, create it
            if not os.path.isfile('.executed_orders.pkl'):
                utils.save_obj([], '.executed_orders')  # and save it just in case something lost along the way
                log.info('creating initial executed orders file')
            else:
                self.executed_orders = list(reversed(utils.load_obj('.executed_orders'))) # read in reverse to preserve most recent data at top
                log.info('loaded executed orders file')
        except Exception as e:
            log.error(f'orion_odas file missing error= {e}')


    def raise_sys_exit():
        raise SystemExit

    # interactive mode for debugging
    def interactive_mode(self):
        Screen.restorescreen()
        log.info('launched interactive mode')

        try:
            __import__('code').interact(banner="launched interactive--- press ctrl+d to exit", exitmsg="exiting interactive mode now", local=dict(globals(), **locals()))
            Screen.clear_it()
        except SystemExit:
            Screen.restorescreen()
            Screen.clear_it()
        except ValueError as e:
            log.error(f'value error from interactive mode: {e}')

    ## accounting
    def funding_history_to_csv(self):
        #  gets history for all available ccys
        res = pd.DataFrame()

        for ccy in ['BTC-USD-SWAP', 'ETH-USD-SWAP', 'ADA-USD-SWAP']:
                _ = self.get_historical_funding(ccy)
                res[ccy] = _.realizedRate

        res.to_csv('funding_hist', index=True)

    def pos_to_csv(self):
        # appends positions data to csv file
        res = self.positions['data']
        utils.write_this(res, 'pos_data.csv')


    '''OKX specific get funcitons '''

    def get_funding(self, instId='BTC-USD-SWAP'):
        params = {"instId": instId}
        res = self._request_with_params(GET, FUNDING, params)
        bps = float(res['data'][0]['fundingRate'])*10000
        time = int(res['data'][0]['fundingTime'])
        time = utils.human_time(time).strftime('%D %H:%M')


        next_bps = float(res['data'][0]['nextFundingRate'])*10000
        next_time = int(res['data'][0]['nextFundingTime'])

        next_time = utils.human_time(next_time).strftime('%D %H:%M')

        return (bps, time, next_bps, next_time)

    def get_historical_funding(self, instId='BTC-USD-SWAP', froms='', to='', limit=''):
        #  gets a single ccy's history
        try:
            params = {}
            params['instId'] = instId
            if froms:
                params['from'] = froms
            if to:
                params['to'] = to
            if limit:
                params['limit'] = limit

            results = self._request_with_params(GET, SWAP_FUNDING, params)  # returns a list item

            results = results['data']
            results = pd.DataFrame(results)
            results.set_index (pd.to_datetime(results.fundingTime.astype(int) / 1000, unit='s'), inplace=True)
            results.realizedRate = results.realizedRate.astype(float)
            results = results.sort_index()
            return results
        except Exception as e:
            log.error(f'get_historical_funding_rate: {e}')



    # dist to best from actual prices
    def reset_dist(self):
        self.live_swap_dist_bbid = 999
        self.live_swap_dist_boffer = 999
        self.live_fwd1_dist_bbid = 999
        self.live_fwd1_dist_boffer = 999
        self.live_fwd2_dist_bbid = 999
        self.live_fwd2_dist_boffer = 999
        self.live_fwd3_dist_bbid = 999
        self.live_fwd3_dist_boffer = 999

        self.live_fwd1_bspread = 0
        self.live_fwd1_ospread = 0
        log.debug('reset of dist to best bid/offers done')

    def reset_live_dists(self):
        # resets distances to to live prics on exchange
        self.live_swap_bspread = ['---', '---']
        self.live_fwd1_bspread = ['---', '---']
        self.live_fwd2_bspread = ['---', '---']
        self.live_fwd3_bspread = ['---', '---']
        self.live_swap_ospread = ['---', '---']
        self.live_fwd1_ospread = ['---', '---']
        self.live_fwd2_ospread = ['---', '---']
        self.live_fwd3_ospread = ['---', '---']
        log.debug('reset live dists done')

    def reset_NOPs(self):
        # resets NOP counters

        self.prev_cumPNL = round(self.all_cumPNL, 5)  # tracks prev cumulatice PNL
        self.all_cumPNL += round((((1 / self.all_avgLongPx) - (1 / self.all_avgShortPx)) * self.all_NOP * 10), 5)   # sums value of hedges

        log.debug(f'reset_NOPS> pre-reset longNOP = {self.all_longNOP} shortNOP = {self.all_shortNOP} longVal = {self.all_longVal} shortVal = {self.all_shortVal} cumPNL = {self.all_cumPNL}')

        self.all_longNOP = 0
        self.all_shortNOP = 0
        self.all_longVal = 0
        self.all_shortVal = 0
        self.all_lastLongPx = None
        self.all_lastShortPx = None
        self.all_avgLongPx = None
        self.all_avgShortPx = None
        self.all_count += 1

        log.debug(f'reset_NOPS> cumulPNL = {self.all_cumPNL}, prev cumulPNL={self.prev_cumPNL} trades count = {self.all_count} ')

    def update_NOPs(self, fillSz_wSign, ref_swap_px):
        log.debug(f'update_NOPS> fillsz_sSign={fillSz_wSign}; ref_swap_px = {ref_swap_px}; longval before = {self.all_longVal} shortval before = {self.all_shortVal}')
        # updates NOPs and average long/short prices
        if fillSz_wSign > 0:
            self.all_longNOP += fillSz_wSign
            self.all_longVal += round(-fillSz_wSign * ref_swap_px, 6)  # ref swap price is confirmed price for the SWAPs

            self.all_lastLongPx = ref_swap_px  # last traded price ref
            self.all_avgLongPx = utils.round_it(-self.all_longVal / self.all_longNOP, 6)  #longVal is negtative, so needs to hv sign to calc price
            log.debug(f'process_private> update_NOP> longVal changed to : {self.all_longVal}; shortVal remains {self.all_shortVal} avgLongPx={self.all_avgLongPx}')

        elif fillSz_wSign < 0:
            self.all_shortNOP += fillSz_wSign
            self.all_shortVal += round(-fillSz_wSign * ref_swap_px, 6)  # ref swap price is confirmed price for the SWAPs
            self.all_lastShortPx = ref_swap_px  # last traded price ref
            self.all_avgShortPx = utils.round_it(self.all_shortVal / -self.all_shortNOP, 6)
            log.debug(f'process_private> update_NOP> shortVal changed to : {self.all_shortVal} longVal remains {self.all_longVal} avgShortPx={self.all_avgShortPx}')


    ''' calc helpers '''

    def get_vwap(self, stack, excl):

        try:
            self.vwap_timer.start()
            # calculated Volume weighted avergae bid and offer for given stack list
            t_size1 = 10  # target size1 in contracts  (used as minimum to get best bid/offer)
            t_size2 = 1000 # target size2 in contracts (used as a relaiable measure of bid/offer at realistic liquidity)
            # need to adjust for confirmed prices already there so we are not double counting

            excl_bid = excl + 'B'
            _res_bid = next(([v['last'], v['sz']] for d in self.conf for k, v in d.items() if excl_bid in k), None)

            excl_offer = excl + 'O'
            _res_offer = next(([v['last'], v['sz']] for d in self.conf for k, v in d.items() if excl_offer in k), None)

            def calc(side, ex):
                exVol = 0

                cumVal1 = 0
                cumVol1 = 0

                cumVal2 = 0
                cumVol2 = 0

                t1_reached = False

                for p, v, _, _ in stack[side]:
                    # must remove excluded stuff
                    p = float(p)
                    v = int(v)

                    if ex:
                        # this amount is excluded from the vwap calc as its our own price/size
                        if p == ex[0]:  # take out the size if it matches our own size on exchange
                            if v + exVol >= ex[1]:
                                v = v - ex[1] - exVol
                            else:
                                exVol += ex[1] - v
                                v = 0

                    value = p * v

                    if cumVol1 + v <= t_size1:
                        cumVal1 += value
                        cumVol1 += v
                    elif cumVol1 + v > t_size1 and not t1_reached:
                        rem_size1 = (t_size1 - cumVol1)
                        value1 = p * rem_size1
                        cumVal1 += value1
                        cumVol1 += rem_size1
                        t1_reached = True  # tells us to stop updating vwap for target1 in the stack

                    if cumVol2 + v <= t_size2:
                        cumVal2 += value
                        cumVol2 += v
                    elif cumVol2 + v > t_size2:
                        rem_size2 = (t_size2 - cumVol2)
                        value2 = p * rem_size2
                        cumVal2 += value2
                        cumVol2 += rem_size2
                        break

                    else:
                        log.error('error in getting vwaps')
                        break

                if cumVol1 == 0 or cumVol2 == 0:
                    log.error(f"vwap error> side={side} ex= {ex}; cumval1/cumvol1:{cumVal1}/{cumVol1} and cumVal2/cumVol2: {cumVal2}/{cumVol2}")
                    log.error(f"stack top 10 of {side} ={stack[side][:10]}")

                return utils.round_it((cumVal1 / cumVol1), 6), utils.round_it((cumVal2 / cumVol2), 6)

            vwap_bid1, vwap_bid2 = calc('bids', ex=_res_bid)  # get vwaps, exclude bid price/size
            vwap_offer1, vwap_offer2 = calc('offers', ex=_res_offer)  # get vwaps exclude offer price/size

            self.vwap_timer.stop()

        except Exception as e:
            log.error(e, exc_info=True)

        #log.debug(f"vwap_timer = c={self.vwap_timer.counts} elapsed={self.vwap_timer.elapsed} mean={self.vwap_timer.mean}")

        return vwap_bid1, vwap_offer1, vwap_bid2, vwap_offer2

    def spreads_one_stop_shop(self):

        # bid/offer spreads
        self.bbid_swap = float(next(iter(self.stack_swap['bids']))[0])
        self.bbid_fwd1 = float(next(iter(self.stack_fwd1['bids']))[0])
        self.bbid_fwd2 = float(next(iter(self.stack_fwd2['bids']))[0])
        self.bbid_fwd3 = float(next(iter(self.stack_fwd3['bids']))[0])

        self.boffer_swap = float(next(iter(self.stack_swap['offers']))[0])
        self.boffer_fwd1 = float(next(iter(self.stack_fwd1['offers']))[0])
        self.boffer_fwd2 = float(next(iter(self.stack_fwd2['offers']))[0])
        self.boffer_fwd3 = float(next(iter(self.stack_fwd3['offers']))[0])

        # spreads to index
        self.SwapVsIndex_mid = round(10000 * (self.vwap_swap['mid'] - self.idxPx) / self.idxPx, 1)
        self.SwapVsIndex_bid = round(10000 * (self.vwap_swap['bid'] - self.idxPx) / self.idxPx, 1)
        self.SwapVsIndex_offer = round(10000 * (self.vwap_swap['offer'] - self.idxPx) / self.idxPx, 1)

        self.fwd1VsIndex_mid = round(10000 * (self.vwap_fwd1['mid'] - self.idxPx) / self.idxPx, 1)
        self.fwd1VsIndex_bid = round(10000 * (self.vwap_fwd1['bid'] - self.idxPx) / self.idxPx, 1)
        self.fwd1VsIndex_offer = round(10000 * (self.vwap_fwd1['offer'] - self.idxPx) / self.idxPx, 1)

        self.fwd2VsIndex_mid = round(10000 * (self.vwap_fwd2['mid'] - self.idxPx) / self.idxPx, 1)
        self.fwd2VsIndex_bid = round(10000 * (self.vwap_fwd2['bid'] - self.idxPx) / self.idxPx, 1)
        self.fwd2VsIndex_offer = round(10000 * (self.vwap_fwd2['offer'] - self.idxPx) / self.idxPx, 1)

        self.fwd3VsIndex_mid = round(10000 * (self.vwap_fwd3['mid'] - self.idxPx) / self.idxPx, 1)

        # use swap/inst1 mids
        self.fwd1VsSwap_mid = round(10000 * (self.vwap_fwd1['mid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd1VsSwap_offer = round(10000 * (self.vwap_fwd1['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd1VsSwap_bid = round(10000 * (self.vwap_fwd1['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)

        # using best bids/offers
        self.swapVsSwap_moffer = round(10000 * (self.min_swap['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.swapVsSwap_mbid = round(10000 * (self.min_swap['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_swapVsSwap_min = round(self.swapVsSwap_moffer - self.swapVsSwap_mbid, 1)

        self.fwd1VsSwap_boffer = round(10000 * (self.boffer_fwd1 - self.bbid_swap) / self.bbid_swap, 1)
        self.fwd1VsSwap_bbid = round(10000 * (self.bbid_fwd1 - self.boffer_swap) / self.boffer_swap, 1)
        self.sprd_fwd1VsSwap = round(self.fwd1VsSwap_offer - self.fwd1VsSwap_bid, 1)

        # bid/offers to best(min acceptable prices)
        self.fwd1VsSwap_moffer = round(10000 * (self.min_fwd1['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd1VsSwap_mbid = round(10000 * (self.min_fwd1['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_fwd1VsSwap_min = round(self.fwd1VsSwap_moffer - self.fwd1VsSwap_mbid, 1)

        self.fwd2VsSwap_moffer = round(10000 * (self.min_fwd2['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd2VsSwap_mbid = round(10000 * (self.min_fwd2['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_fwd2VsSwap_min = round(self.fwd2VsSwap_moffer - self.fwd2VsSwap_mbid, 1)

        self.fwd3VsSwap_moffer = round(10000 * (self.min_fwd3['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd3VsSwap_mbid = round(10000 * (self.min_fwd3['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_fwd3VsSwap_min = round(self.fwd3VsSwap_moffer - self.fwd3VsSwap_mbid, 1)

        self.fwd2VsSwap_mid = round(10000 * (self.vwap_fwd2['mid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd2VsSwap_offer = round(10000 * (self.vwap_fwd2['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd2VsSwap_bid = round(10000 * (self.vwap_fwd2['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_fwd2VsSwap = round(self.fwd2VsSwap_offer - self.fwd2VsSwap_bid, 1)

        self.fwd3VsSwap_mid = round(10000 * (self.vwap_fwd3['mid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd3VsSwap_offer = round(10000 * (self.vwap_fwd3['offer'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.fwd3VsSwap_bid = round(10000 * (self.vwap_fwd3['bid'] - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)
        self.sprd_fwd3VsSwap = round(self.fwd3VsSwap_offer - self.fwd3VsSwap_bid, 1)

        self.fwd2Vsfwd1_mid = round(10000 * (self.vwap_fwd2['mid'] - self.vwap_fwd1['mid']) / self.vwap_fwd1['mid'], 1)
        self.fwd2Vsfwd1_offer = round(10000 * (self.vwap_fwd2['offer'] - self.vwap_fwd1['mid']) / self.vwap_fwd1['mid'], 1)
        self.fwd2Vsfwd1_bid = round(10000 * (self.vwap_fwd2['bid'] - self.vwap_fwd1['mid']) / self.vwap_fwd1['mid'], 1)
        self.sprd_fwd2Vsfwd1 = round(self.fwd2Vsfwd1_offer - self.fwd2Vsfwd1_bid, 1)

        self.fwd3Vsfwd2_mid = round(10000 * (self.vwap_fwd3['mid'] - self.vwap_fwd2['mid']) / self.vwap_fwd2['mid'], 1)

        # bid/offer spreads on individual instruments
        self.sprd_swap = round(10000 * (self.vwap_swap['offer'] - self.vwap_swap['bid']) / ((self.vwap_swap['bid'] + self.vwap_swap['offer']) / 2), 1)   # using mids as denomonitor
        self.sprd_fwd1 = round(10000 * (self.vwap_fwd1['offer'] - self.vwap_fwd1['bid']) / ((self.vwap_fwd1['bid'] + self.vwap_fwd1['offer']) / 2), 1)   # using mids as denomonitor
        self.sprd_fwd2 = round(10000 * (self.vwap_fwd2['offer'] - self.vwap_fwd2['bid']) / ((self.vwap_fwd2['bid'] + self.vwap_fwd2['offer']) / 2), 1)   # using mids as denomonitor
        self.sprd_fwd3 = round(10000 * (self.vwap_fwd3['offer'] - self.vwap_fwd3['bid']) / ((self.vwap_fwd3['bid'] + self.vwap_fwd3['offer']) / 2), 1)   # using mids as denomonitor

        self.msprd_swap = round(10000 * (self.min_swap['offer'] - self.min_swap['bid']) / (self.min_swap['mid']), 1)   # using mids as denomonitor
        self.msprd_fwd1 = round(10000 * (self.min_fwd1['offer'] - self.min_fwd1['bid']) / (self.min_fwd1['mid']), 1)   # using mids as denomonitor
        self.msprd_fwd2 = round(10000 * (self.min_fwd2['offer'] - self.min_fwd2['bid']) / (self.min_fwd2['mid']), 1)   # using mids as denomonitor
        self.msprd_fwd3 = round(10000 * (self.min_fwd3['offer'] - self.min_fwd3['bid']) / (self.min_fwd3['mid']), 1)   # using mids as denomonitor

    ''' Requests '''
    def _request(self, method, request_path, params, cursor=False):
        #log.info(f'_request used (should be for backup purposes only): {params}')
        # used for nonwebsocket requests

        if method == c.GET:
            request_path = request_path + utils.parse_params_to_str(params)
        # url
        url = c.API_URL + request_path

        timestamp = utils.get_timestamp()
        # sign & header
        if self.use_server_time:
            timestamp = self._get_timestamp()
        body = json.dumps(params).replace(' ', '') if method == c.POST else ""

        sign = utils.sign(utils.pre_hash(timestamp, method, request_path, str(body)), self.secret_key)
        header = utils.get_header(self.api_key, sign, timestamp, self.passphrase)

        # send request
        response = None
        if method == c.GET:
            response = requests.get(url, headers=header)
        elif method == c.POST:
            response = requests.post(url, data=body, headers=header)
            #response = requests.post(url, json=body, headers=header)
        elif method == c.DELETE:
            response = requests.delete(url, headers=header)

        # exception handle
        if not str(response.status_code).startswith('2'):
            raise exceptions.OkexAPIException(response)
            log.debug('_request raises an OKEX exception')

        try:
            res_header = response.headers
            if cursor:
                r = dict()
                try:
                    r['before'] = res_header['OK-BEFORE']
                    r['after'] = res_header['OK-AFTER']
                except Exception as e:
                    log.error(f'_request blank ....{e}')

                log.debug(f'response: {response.json(), r}')
                return response.json(), r
            else:
                #log.debug(f'else response: {response.json()}')
                return response.json()
        except ValueError:
            raise exceptions.OkexRequestException('Invalid Response: %s' % response.text)
        except Exception as e:
            log.error(e)

    def _request_without_params(self, method, request_path):
        return self._request(method, request_path, {})

    def _request_with_params(self, method, request_path, params, cursor=False):
        return self._request(method, request_path, params, cursor)

    def _get_timestamp(self):
        url = API_URL + SERVER_TIMESTAMP_URL
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()['iso']
        else:
            return ""

    async def connect_public(self):
        log.info('requesting public data connection')
        self.ws_public = await websockets.connect(public_url)
        log.info('connected socket to public url')
        await self.subscribe_public()
        log.debug('done with subscribing public')

    async def connect_private(self):
        try:
            log.info('requesting private data connection and login')
            self.ws_private = await websockets.connect(private_url)
            await self.login()
            await self.subscribe_private()
        except Exception as e:
            log.error(e, exc_info=True)

    async def login(self):
        # login
        timestamp = str(get_local_timestamp())
        login_str = login_params(timestamp, self.api_key, self.passphrase, self.secret_key)
        log.info('sent login_str')
        await self.ws_private.send(login_str)
        res = await self.ws_private.recv()
        log.info(f'res of login= {res}')

    async def subscribe_public(self):
        # Subscribe
        log.debug('subscribe_public> appending channels')
        public_channels = []
        public_channels.append({"channel": "books50-l2-tbt", "instId": self.swap})
        public_channels.append({"channel": "books50-l2-tbt", "instId": self.fwd1})
        public_channels.append({"channel": "books50-l2-tbt", "instId": self.fwd2})
        public_channels.append({"channel": "books50-l2-tbt", "instId": self.fwd3})
        public_channels.append({"channel": "index-tickers", "instId": self.index_label})

        sub_param = {"op": "subscribe", "args": public_channels}
        sub_str = json.dumps(sub_param)
        log.info(f'sent public subscription {sub_str}')
        await self.ws_public.send(sub_str)
        log.info('subscribed to public data')

        l = []
        while True:

            # get data
            try:
                self.main_timer.start()  # overall timer
                self.get_data_timer.start()   # get public data start

                #log.debug('subscribe_public while True loop starts **************************************')
                res = await asyncio.wait_for(self.ws_public.recv(), timeout=25)
                res = eval(res)
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                try:
                    await self.ws_public.send('ping')
                    res = await self.ws_public.recv()
                    continue
                except Exception as e:
                    log.error(f"ws connection ping prob= {e}")
                    break

            self.get_data_timer.stop()  # get public data timer stop
            #log.debug(f'Rcvd public data: {self.get_data_timer.elapsed}ms to get new data.   count={self.get_data_timer.counts} ')

            try:
                # check latency incoming inst1 and inst2
                if 'data' in res:  # TODO: is data always present with action? If yes, then move this to if action:
                    ts = res['data'][0]['ts']

                    if res['arg']['instId'] == self.swap:
                        self.latencyT_swap.update(ts)
                        #log.debug(f'latency1 elapsed = {self.latencyT_swap.elapsed} c={self.latencyT_swap.counts} ')

                    elif res['arg']['instId'] == self.fwd1:
                        self.latencyT_f1.update(ts)
                        #log.debug(f'latency2 elapsed = {self.latencyT_f1.elapsed} c={self.latencyT_f1.counts}')

                    elif res['arg']['instId'] == self.fwd2:
                        self.latencyT_f2.update(ts)
                        #log.debug(f'latency3 elapsed = {self.latencyT_f2.elapsed} c={self.latencyT_f2.counts} ')

                    elif res['arg']['instId'] == self.fwd3:
                        self.latencyT_f3.update(ts)
                        #log.debug(f'latency3 elapsed = {self.latencyT_f3.elapsed} c={self.latencyT_f3.counts} ')

                    elif res['arg']['instId'] == self.index_label:
                        self.latencyT_idx.update(ts)
                        #log.debug(f'latencyIdx elapsed = {self.latencyT_idx.elapsed}')

                if 'event' in res:
                    # structure is: event: subscribe args: {channel;: positions, etc...}
                    if res['event'] == 'subscribe':
                        log.info(f'subscription confirmed by exchange: {res}')

                if 'arg' in res:
                    try:
                        if res['arg']['channel'] == 'index-tickers':
                            self.idxPx = float(res['data'][0]['idxPx'])
                    except KeyError:
                        pass
                    except Exception as e:
                        log.error(e, exc_info= True)

                if 'action' in res:
                    for i in res['arg']:
                        # append and checksum

                        if 'books50-l2-tbt' in res['arg'][i]:   # TODO: this is looking up channel as well as instId when only needs to look at channel.  Maybe rewrite
                            # Get initial snapshot
                            if res['action'] == 'snapshot':
                                inst = res['arg']['instId']
                                log.info(f"recv initial snapshot data {inst}")

                                for m in l:
                                    if res['arg']['instId'] == m['instrument_id']:
                                        l.remove(m)
                                bids_p, asks_p, instrument_id = partial(res)
                                d = {}
                                d['instrument_id'] = instrument_id
                                d['bids_p'] = bids_p
                                d['asks_p'] = asks_p
                                l.append(d)

                                # checksum
                                checksum = res['data'][0]['checksum']
                                check_num = check(bids_p, asks_p)

                                if check_num == checksum:
                                    log.info(f'{inst} initial snapshot checksum OK')
                                else:
                                    log.error("checksum：False，restart connection")

                                    await unsubscribe_without_login(public_url, public_channels)
                                    async with websockets.connect(public_url) as self.ws_public:
                                        sub_param = {"op": "subscribe", "args": public_channels}
                                        sub_str = json.dumps(sub_param)
                                        await self.ws_public.send(sub_str)

                            elif res['action'] == 'update':
                                # log.debug('stack update started')
                                self.stack_update_timer.start()
                                for j in l:

                                    if res['arg']['instId'] == j['instrument_id']:
                                        # get bids/offers
                                        bids_p = j['bids_p']
                                        asks_p = j['asks_p']

                                        # updte bids/offers dict
                                        bids_p = update_bids(res, bids_p)
                                        asks_p = update_asks(res, asks_p)

                                        # checksum
                                        checksum = res['data'][0]['checksum']
                                        check_num = check(bids_p, asks_p)

                                        if check_num == checksum:
                                            # checksum passes -> data is good
                                            # get VWAPS
                                            if j['instrument_id'] == self.swap:
                                                self.stack_swap = {'bids': bids_p, 'offers': asks_p}
                                                min_bid, min_offer, vwap_bid, vwap_offer = self.get_vwap(self.stack_swap, excl='mmSw')
                                                self.vwap_swap = {'bid': vwap_bid, 'offer': vwap_offer, 'mid': utils.round_it((vwap_bid + vwap_offer) / 2, 6)}
                                                self.min_swap = {'bid': min_bid, 'offer': min_offer, 'mid': utils.round_it((min_bid + min_offer) / 2, 6)}

                                            elif j['instrument_id'] == self.fwd1:
                                                self.stack_fwd1 = {'bids': bids_p, 'offers': asks_p}
                                                min_bid, min_offer, vwap_bid, vwap_offer = self.get_vwap(self.stack_fwd1, excl='mmF1')
                                                self.vwap_fwd1 = {'bid': vwap_bid, 'offer': vwap_offer, 'mid': utils.round_it((vwap_bid + vwap_offer) / 2, 6)}
                                                self.min_fwd1 = {'bid': min_bid, 'offer': min_offer, 'mid': utils.round_it((min_bid + min_offer) / 2, 6)}

                                            elif j['instrument_id'] == self.fwd2:
                                                self.stack_fwd2 = {'bids': bids_p, 'offers': asks_p}
                                                min_bid, min_offer, vwap_bid, vwap_offer = self.get_vwap(self.stack_fwd2, excl='mmF2')
                                                self.vwap_fwd2 = {'bid': vwap_bid, 'offer': vwap_offer, 'mid': utils.round_it((vwap_bid + vwap_offer) / 2, 6)}
                                                self.min_fwd2 = {'bid': min_bid, 'offer': min_offer, 'mid': utils.round_it((min_bid + min_offer) / 2, 6)}

                                            elif j['instrument_id'] == self.fwd3:
                                                self.stack_fwd3 = {'bids': bids_p, 'offers': asks_p}
                                                min_bid, min_offer, vwap_bid, vwap_offer = self.get_vwap(self.stack_fwd3, excl='mmF3')
                                                self.vwap_fwd3 = {'bid': vwap_bid, 'offer': vwap_offer, 'mid': utils.round_it((vwap_bid + vwap_offer) / 2, 6)}
                                                self.min_fwd3 = {'bid': min_bid, 'offer': min_offer, 'mid': utils.round_it((min_bid + min_offer) / 2, 6)}

                                            ## spreads one stop show
                                            try:
                                                data_list = [self.vwap_swap['bid'], self.vwap_fwd3['bid'], self.idxPx]   # list of data holders than must be populated before continuing
                                                if data_list.count(None) == 0:
                                                    self.spreads_one_stop_shop()  # update all the spreads
                                                    self.data_flow = True
                                            except StopIteration:
                                                pass

                                            except Exception as e:
                                                log.error(e, exc_info=True)

                                        else:
                                            log.error("stack checksum failed.. restarting connection")
                                            await unsubscribe_without_login(public_url, public_channels)
                                            async with websockets.connect(public_url) as self.ws_public:
                                                sub_param = {"op": "subscribe", "args": public_channels}
                                                sub_str = json.dumps(sub_param)
                                                await self.ws_public.send(sub_str)
                                                log.info(f"send: {sub_str}")


                                self.stack_update_timer.stop()
                                #log.debug(f'Stack update took: {self.stack_update_timer.elapsed}ms')

                                # run overwatch
                                await self.overwatch()  # call overwatch after stack update in prices


               # Track main timer
                self.main_timer.stop()
                #log.debug(f'Subscribe_public (main_timer) loop ended = {self.main_timer.elapsed} __________________________')

            except Exception as e:
                log.error(e, exc_info=True)

    async def subscribe_private(self):
        # subscribe public channel
        log.info('about to subscribe private')
        try:
            sub_param = {"op": "subscribe", "args": [{"channel": "account"}, {"channel": "positions", "instType": "ANY"},
                {"channel": "orders", "instType": "ANY"}, {"channel": "balance_and_position"}, {"channel": "liquidation-warning", "instType": "ANY"}]}
            sub_str = json.dumps(sub_param)
            #log.debug(f'sub str = {sub_str}')
            log.debug(f'sent private subscription {sub_str}')

            await self.ws_private.send(sub_str)
            log.debug('subscribed private')
        except Exception as e:
            log.error(e)

        while True:
            try:
                self.get_pm_timer.start()   # get public data start
                log.debug('subscribe_private> awaiting recv pm_data~~~~~~~~~~~~~~~~~~~')
                res = await asyncio.wait_for(self.ws_private.recv(), timeout=25)
                self.pm = eval(res)
                #log.debug(f'pm res = {self.pm}')
                self.get_pm_timer.stop()
                await self.process_private()

                log.debug(f'recvd private data: took {self.get_pm_timer.elapsed}ms count={self.get_pm_timer.counts} ~~~~~~~~~~~~~~ ')
            except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                try:
                    await self.ws_private.send('ping')
                    res = await self.ws_private.recv()
                    _ = (f'recvd res= {res}')
                    log.error(_)
                    continue
                except Exception as e:
                    log.error(f"subscription> {e}")
                    break
            except Exception as e:
                log.error(e, exc_info=True)

    async def process_private(self):
        # this is now a non IO loop. which can be run as a seperate thread?  Or could even be run as async for btter control
        try:
            if 'code' in self.pm:
                # code is either 0 or 1, and represents ack of request from server (where 1 is error and 0 is ok)
                if self.pm['code'] == '1':
                    _ = (f'process_private> exchange sees error: {self.pm} req_timer: elapsed: {self.req_timer.total_elapsed} counts: {self.req_timer.counts}')
                    log.error(_)

                    try:

                        if self.pm['data'][0]['sCode'] == '51112':
                            _ = ('Close order size exceeds available size')
                            log.error(_)
                            self.notification = (_)
                            self.safety_shutdown = True
                        elif self.pm['data'][0]['sCode'] == '50011':
                            log.error(f'Requests too frequent: req_timer max: {self.req_timer.max} max batches: {self.req_timer.max_batches}')
                            self.notification = f'Requests too frequent! {self.req_timer.max}'
                        elif self.pm['data'][0]['sCode'] == '51502':
                            log.error('Insufficient margin to modify trade')
                            self.notification = 'insufficient margin'
                            self.safety_shutdown = True  # means stop adding new trades until further notice
                        elif self.pm['data'][0]['sCode'] == '51004':
                            _ = ('Order amount exceeds limit')
                            log.error(_)
                            self.notification = _
                            self.safety_shutdown = True
                        elif self.pm['data'][0]['sCode'] == '51509':
                            _ = ('Order cancelled by exch as order failed')
                            log.error(_)
                            self.notification = _
                        elif self.pm['data'][0]['sCode'] == '57008':
                            log.error('Insufficient balance')
                            self.notification = 'Insufficient balance'
                            self.safety_shutdown = True
                        else:
                            self.notification = self.pm['data'][0]['sMsg']

                    except Exception as e:
                        log.error(e, self.pm)
                    return

                elif self.pm['code'] == '0':
                    log.debug(f"process_private> exchange ack request --------------------\n{self.pm}")

                elif self.pm['code'] == '2':
                    log.debug(f"process_private> Code 2\n{self.pm}")
                    if self.pm['data'][0]['sCode'] == '50011':
                        _note = f'Requests too frequent counts={self.req_timer.max}'
                        log.error(_note)
                        self.notification = _note

                    if any([True for item in self.pm['data'] if item['sCode'] == '51004']):  # checks in case there is a list of return values form server
                        _note = 'Order amount exceeds'
                        log.error(_note)
                        self.notification = _note
                    return

            if 'event' in self.pm:
                # structure is: event: subscribe args: {channel;: positions, etc...}
                if self.pm['event'] == 'subscribe':
                    log.info(f'subscription confirmed by exchange: {self.pm}')
                    return

                # login confirmation
                elif 'event' in self.pm:
                    # event type received
                    if self.pm == {'event': 'login', 'msg': '', 'code': '0'}:
                        log.info('private connection confirmed')
                        return
                else:
                    log.debug(f'other type of event: {self.pm}')

            if 'arg' in self.pm:
                if self.pm['arg']['channel'] == 'positions':
                    self.positions = self.pm
                    log.debug("pm positions info recvd")
                    self.update_risk()

                elif self.pm['arg']['channel'] == 'account':
                    self.account = self.pm
                    log.debug('pm account info recvd')
                    self.update_risk()

                elif self.pm['arg']['channel'] == 'orders':
                    _ = self.pm['data'][0]
                    # log.debug(f">>> recvd Order {_}")

                    try:
                        self.orders_hist.append(_)  # this will accumulate into too much data
                        self.orders_hist = self.orders_hist[-10:]  # get rid of extra data
                        state = _['state']
                        orders_clOrdId = _['clOrdId']

                        sz = int(_['sz'])

                        if _['fillNotionalUsd'] == '':
                            fillNotionalUsd = 0
                        else:
                            fillNotionalUsd = float(_['fillNotionalUsd'])

                        # Partial fills updated differently:
                        fillSz = int(_['fillSz'])
                        remSz = sz - fillSz

                        if fillSz != 0:
                            # this is a new fill
                            conf_px = float(_['fillPx'])
                        else:
                            conf_px = float(_['px'])

                        if orders_clOrdId[:2] == 'mm':
                            if state == 'live' or state == 'partially_filled':  # updated orders can come through as partial with a different notional and must be processed.

                                orders_ordId = int(_['ordId'])
                                log.debug(f"process_private> change in orders> rcvd New LIVE {orders_clOrdId} {orders_ordId} {_['instId']}@{conf_px} fillNotionalUsd: {fillNotionalUsd} fillSz: {fillSz} remSz: {remSz}")

                                if state == 'partially_filled':
                                    sz = remSz  # TODO: debug the size issuie for partial fills
                                    log.debug(f'changed sz to remSz of {remSz}')

                                for i in self.orion_orders:
                                    # Identify if request exists, move to confirm list and remove from pnd_confirm
                                    if any(orders_clOrdId in d for d in self.pnd_conf):  # Check if order in pnd_q
                                        rem_items = [x for x in self.pnd_conf if orders_clOrdId not in x]

                                        self.conf.append({orders_clOrdId: {'last': conf_px, 'req': None, 'sz': sz}})  # update last px and/or updated dz

                                        self.pnd_conf = rem_items
                                        i['uTime'] = int(time.time() * 1000)

                                    elif any(orders_clOrdId in d for d in self.conf):  # Check if order in conf
                                        self.conf[0][orders_clOrdId] = {'last': conf_px, 'req': None, 'sz': sz}
                                        i['uTime'] = int(time.time() * 1000)
                                    else:
                                        log.error(f"could not find {orders_clOrdId} in pnd_conf. FYG pnd_conf= {self.pnd_conf}  orion_orders={self.orion_orders}")

                            if state == 'filled' or state == 'partially_filled':
                                if state == 'filled':
                                    self.reset_live_dists()  # TODO: this is a temp check to see if top line continues to flicker or not

                                # log.info(f'process_private> filled / partial > {orders_clOrdId} {state} fillSz={fillSz} total sz (rem)= {sz} @ {conf_px}')
                                #log.debug(f'process_private> original message> {self.pm}')

                                for i in self.orion_orders:
                                    BE_px = 0  # (breakeven fee for swap trades)

                                    t = int(time.time() * 1000)
                                    ''' Cycle through confirmed and pending_confirmation lists to locate executed trade
                                    Once we find it, we update the risk buckets, average px, etc.. and finally move the transaction
                                    to filled status'''

                                    log.debug('running for loop in self.orion_orders')
                                    for status in ['conf', 'pnd_conf']:  # cycle through confirmed and pnd_conf buckets
                                        log.debug(f'running for loop in {status}')
                                        # log.debug(f'for reference i = {i}')

                                        if status == 'conf':
                                            found = [tx for tx in self.conf if orders_clOrdId in tx]  # find transactgion if in confirmed
                                        else:
                                            found = [tx for tx in self.pnd_conf if orders_clOrdId in tx]  # find transactgion if in confirmed

                                        if found:  # Check if order in conf_q
                                            if status == 'conf':
                                                rem_items = [x for x in self.conf if orders_clOrdId not in x]
                                            else:
                                                rem_items = [x for x in self.pnd_conf if orders_clOrdId not in x]

                                            log.debug(f"Process_private> found {orders_clOrdId} in {status}")
                                            # log.debug(f"Process_private> rem_items = {rem_items}")

                                            if fillSz != 0:  # below only applies if we had a fill and not just an update in price

                                                self.fill_count += 1  # track number of fills
                                                # update to time stamp and last filled
                                                i['uTime'] = t
                                                i['last_fld'] = {orders_clOrdId: {'conf_px': conf_px, 'time': t, 'sz': fillSz, 'fill_count': self.fill_count}}
                                                log.debug(f"process_private> FILLED > {i['last_fld']}")

                                                # log.debug('last_fld also updated')
                                                # px confirmed trade
                                                _ = {orders_clOrdId: {'px': conf_px, 'sz': fillSz}}

                                                # append filled order to correct bucket
                                                if orders_clOrdId[2] == 'F':  # fwd
                                                    fwd_num = orders_clOrdId[3]
                                                    _side = orders_clOrdId[4]

                                                    bucket = i['fwd' + fwd_num + '_delta'][_side]
                                                    bucket['fills'].append(_)
                                                    bucket['num'] += 1
                                                    bucket['sz'] += fillSz
                                                    log.debug(f"process_private> {bucket} num increased to {bucket['num']}")

                                                    # determine the fair price for a forward, the reference px for the swap and then the P&L of new trade
                                                    log.info(f'DEBUG fwd_num = {fwd_num}')
                                                    if fwd_num == '1':
                                                        ref_fwd_px = self.vwap_fwd1['mid']
                                                    elif fwd_num == '2':
                                                        ref_fwd_px = self.vwap_fwd2['mid']
                                                    elif fwd_num == '3':
                                                        ref_fwd_px = self.vwap_fwd3['mid']
                                                    else:
                                                        ref_fwd_px = self.vwap_swap['mid']  # TODO: remove this
                                                        log.error('got a strange fwd number.... ')

                                                    ref_swap_px = self.vwap_swap['mid']
                                                    mid_sprd = round(10000 * (ref_fwd_px - ref_swap_px) / ref_swap_px, 2)  # mark-to-market of spread at time of capture

                                                    # update sz, this will be sign dependent in certain cases
                                                    if _side == 'O':  # sold, so size is negative
                                                        fillSz_wSign = -1 * fillSz
                                                        self.fwds_PNL += ((1 / conf_px) - (1 / ref_fwd_px)) * fillSz * 10  # capture the PNL from offer to mid
                                                        log.info(f'fwds_PNL offer side = {self.fwds_PNL} gerated from conf_px={conf_px} ref_fwd_px = {ref_fwd_px} ref_swap_px={ref_swap_px}')

                                                    elif _side == 'B':  # sold, so size is negative
                                                        fillSz_wSign = fillSz
                                                        self.fwds_PNL += ((1 / conf_px) - (1 / ref_fwd_px)) * fillSz * 10  # capture the PNL from offer to mid
                                                        log.info(f'fwds_PNL bid side = {self.fwds_PNL} gerated from conf_px={conf_px} ref_fwd_px = {ref_fwd_px} ref_swap_px={ref_swap_px}')
                                                    else:
                                                        log.error('process_private> strange side {_side} encountered')
                                                        mid_sprd = 0
                                                        # trgt_sprd = 0

                                                    #  Need to keep track of a reference px that tells us how much we are short/long at
                                                    self.prev_allNOP = self.all_NOP
                                                    self.all_NOP += fillSz_wSign

                                                    self.update_NOPs(fillSz_wSign, ref_swap_px)  # update NOP positions and average prices

                                                    if abs(self.all_NOP) > abs(self.prev_allNOP):  # identify if risk has increased
                                                        if fillSz > (i['spawn_size'] / 3):
                                                            self.regen_timer.start_regen()  # start regen counter on any new trade filled
                                                            log.debug(f'Regen started as overall risk has increased {self.prev_allNOP + self.MR_NOP} -> {self.all_NOP + self.MR_NOP}')
                                                        else:
                                                            log.debug('process_private> fill was tiny.  Ignoring')
                                                            self.notifications = 'tiny fill. ignoring'

                                                    log.debug(f'process_private> new all_NOP= {self.all_NOP} after fillSz_wSign={fillSz_wSign}; ref_swap_px = {ref_swap_px} using mid_srpd={mid_sprd}')

                                                    if self.all_NOP != 0:
                                                        self.trade_timer.start()
                                                        log.debug(f'process_private> all_NOP not square= {self.all_NOP}')

                                                    elif self.all_NOP == 0 and (self.all_shortVal != 0 or self.all_longVal != 0):
                                                        _ = ('NOPS reset as we are square')
                                                        self.notification = _
                                                        log.debug(_)
                                                        self.trade_timer.stop()
                                                        self.reset_NOPs()  # use reset after we sqr up
                                                        self.regen_timer.cancel_regen()  # cancels regen cycle
                                                    else:
                                                        log.error('process_private> THIS TEMP other scenario was recorded')

                                                    log.debug(f'Fwd traded: fillSz_wSign = {fillSz_wSign} NOPS= short: {self.all_shortNOP} long: {self.all_longNOP}; ref_swap_px = {ref_swap_px} avglong/short px {self.all_avgShortPx}/{self.all_avgLongPx} and all_avgVal = {self.all_shortVal}/{self.all_longVal}')

                                                    i['fwd' + fwd_num + '_delta']['net']['sz'] += fillSz_wSign

                                                elif orders_clOrdId[2:4] == 'Sw':  # swap
                                                    _side = orders_clOrdId[4]

                                                    bucket = i['swap' + '_delta'][_side]
                                                    bucket['fills'].append(_)
                                                    bucket['num'] += 1
                                                    bucket['sz'] += fillSz
                                                    log.debug(f"process_private> {bucket} num increased to {bucket['num']}")

                                                    if _side == 'O':  # sold, so size is negative
                                                        fillSz_wSign = -1 * fillSz
                                                        ref_swap_px = adj_bps(conf_px, -BE_px)  # add two bps for cost of execution  # TODO: this spread of 2 needs to be adjustable

                                                    elif _side == 'B':  # sold, so size is negative
                                                        fillSz_wSign = fillSz
                                                        ref_swap_px = adj_bps(conf_px, BE_px)  # add two bps

                                                    self.prev_allNOP = self.all_NOP
                                                    self.all_NOP += fillSz_wSign  # update system wide NOP too
                                                    if abs(self.all_NOP) > abs(self.prev_allNOP):

                                                        if fillSz > (i['spawn_size'] / 3):
                                                            self.regen_timer.start_regen()  # start regen counter on any new trade filled
                                                            log.debug(f'Regen started as overall risk has increased {self.prev_allNOP + self.MR_NOP} -> {self.all_NOP + self.MR_NOP}')
                                                        else:
                                                            log.debug('process_private> fill was tiny.  Ignoring')
                                                            self.notifications = 'tiny fill. ignoring'

                                                    self.update_NOPs(fillSz_wSign, ref_swap_px)  # update NOP positions and average prices

                                                    if self.all_NOP != 0:
                                                        self.trade_timer.start()

                                                    elif self.all_NOP == 0 and self.all_shortVal != 0 or self.all_longVal != 0:
                                                        _ = ('NOPS square; regen cycle cncld')
                                                        self.notification = _
                                                        log.debug(_)
                                                        self.trade_timer.stop()
                                                        self.reset_NOPs()
                                                        self.regen_timer.cancel_regen()  # cancels regen cycle

                                                    log.debug(f'Swap traded: fillSz_wSign = {fillSz_wSign} NOPS= short: {self.all_shortNOP} long: {self.all_longNOP}; ref_swap_px={ref_swap_px} with BE={BE_px} and all_shortVal={self.all_shortVal}/longVal={self.all_longVal}')

                                                    i['swap' + '_delta']['net']['sz'] += fillSz_wSign

                                                else:
                                                    log.error(f"Process_private> order not found> what kind of order is {orders_clOrdId}")

                                            # updates to self.conf and self.pnd_conf go below

                                            if state == 'filled':  # if filled, then remove trade from confirmed list
                                                if status == 'conf':
                                                    self.conf = rem_items
                                                else:
                                                    self.pnd_conf = rem_items

                                                log.debug(f'{orders_clOrdId} moved out of {status} to fld')
                                                # log.debug(f'filled: {i}')
                                                log.debug(f"conf: {self.conf}")
                                                log.debug(f"pnd_conf: {self.pnd_conf}")

                                            elif state == 'partially_filled':  # adjust existing size by filled amount, but keep ticket where it is
                                                # found[0][orders_clOrdId]['sz'] -= fillSz
                                                found[0][orders_clOrdId]['last'] = conf_px  # last updated price on exchange has been updated to this

                                                log.info(f'changed existing size to {sz} by reducing {fillSz}; price is {conf_px}')
                                                log.debug(f'{orders_clOrdId} kept in conf as only partiall fill')

                                                # log.debug(f'This is how it looks after update: {i}')

                                                # log.debug(f"conf: {self.conf}")
                                                # log.debug(f"pnd_conf: {self.pnd_conf}")

                                            log.debug('Process_private> about to break for loop as found and updated trade')
                                            break

                                        else:
                                            log.debug(f'Not found... {orders_clOrdId} in {status}')

                                await self.overwatch()  # force ov erwatch to run so we immeadiately issue side 1
                                return


                            elif state == 'canceled':
                                # conf > cnld
                                log.info(f"order CANCELLED {_['clOrdId']}  {_['instId']} oda_px={_['px']} ")
                                # TODO: build this later

                                #_thread.start_new_thread(self.nonperiodic_updates, ())  # launch a thread to update fills

                        else:
                            log.error(f"New order unknown websocket stream: {_}")

                    except Exception as e:
                        log.error(f'append_issue> {e}; self.pm={self.pm}', exc_info=True)

                elif self.pm['arg']['channel'] == 'balance_and_position':
                    #log.debug('channel_and_balance data recvd')
                    self.balance_and_position = self.pm
                    self.update_risk()

                elif self.pm['arg']['channel'] == 'liquidation-warning':
                    log.error('got liquidation warning')
                    log.debug(self.pm)

                else:
                    log.error(f'process_private> unknown arg type: {self.pm}')
            else:
                log.debug(f'process_private> another data type: {self.pm}')

        except KeyError as e:
            log.error(f'ws_message key error from pm={self.pm}\nerror: {e}', exc_info=True)
        except Exception as e:
            template = "An exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'pm Exception: {error_message} and e={e}', exc_info=True)



    def update_risk(self):
        self.update_risk_timer.start()
        ''' Update data in self.risk (this is where we store the risks that are later displayed on main screen (how much notional, swaps and futures, nop, etc.._
        ## we do this by cycling through existing risk data and summarising only what we need

        # self.balance consists of two parts if sourced from balance_and_position websocket
        #1 baldata contains OVERALL cashBal, ccy
        #2 posData contains ccy, avgPx, pos, posSideand instType'''

        try:
            if not self.positions or not self.account:
                return

            raw_positions = self.positions['data']
            raw_account = self.account['data'][0]['details']

            if not self.risk:  # populate empty fields once.
                # go through balance data first
                for i in range(len(raw_account)):
                    # run through raw data, if ccy doesnt exist, then create it, if it does, then update it
                    ccy = raw_account[i]['ccy']

                    SWAPS = {'net': 0, 'long': {}, 'short': {}}
                    FUTS = {'net': 0, 'long': {}, 'short': {}}

                    # populate based on self.account data
                    self.risk[ccy] = {'eqUsd': round(float(raw_account[i]['eqUsd']), 1), 'cashBal': round(float(raw_account[i]['cashBal']), 1),
                                      'coinUsdPrice': utils.round_it(float(raw_account[i]['coinUsdPrice']), 6),
                                      'availEq': round(float(raw_account[i]['availEq']), 1), 'disEq': round(float(raw_account[i]['disEq']), 1),
                                      'frozenBal': round(float(raw_account[i]['frozenBal']), 1),
                                      'eq': round(float(raw_account[i]['eq']), 1), 'upl': round(float(raw_account[i]['upl']), 1), 'FUTS': FUTS, 'SWAPS': SWAPS}

            elif self.risk:  # populate empty fields once.
                # go through balance data first
                for i in range(len(raw_account)):
                    # run through raw data, if ccy doesnt exist, then create it, if it does, then update it
                    ccy = raw_account[i]['ccy']

                    # if exists, using existing risk to avoid flashing 0's at any point
                    if ccy in self.risk:  # TODO; remove this
                        FUTS = self.risk[ccy]['FUTS']  # update all futures contract sizes and maturity
                        SWAPS = self.risk[ccy]['SWAPS']  # update all futures contract sizes and maturity

                    # populate based on self.account data
                    self.risk[ccy] = {'eqUsd': round(float(raw_account[i]['eqUsd']), 1), 'cashBal': round(float(raw_account[i]['cashBal']), 1),
                                      'coinUsdPrice': utils.round_it(float(raw_account[i]['coinUsdPrice']), 6),
                                      'availEq': round(float(raw_account[i]['availEq']), 1), 'disEq': round(float(raw_account[i]['disEq']), 1),
                                      'frozenBal': round(float(raw_account[i]['frozenBal']), 1),
                                      'eq': round(float(raw_account[i]['eq']), 1), 'upl': round(float(raw_account[i]['upl']), 1), 'FUTS': FUTS, 'SWAPS': SWAPS}


            # then we go through position data second
            for i in range(len(raw_positions)):
                ccy = raw_positions[i]['ccy']
                instType = raw_positions[i]['instType']

                # here we are going through all exisitng positions and adding sz to existing dictionary
                if instType == 'FUTURES':
                    # if futures, we need the expiry date to determine the PV01 risk
                    instId = raw_positions[i]['instId']
                    side = raw_positions[i]['posSide']
                    sz = raw_positions[i]['notionalUsd']
                    imr = round(float(raw_positions[i]['imr']), 1)
                    mmr = round(float(raw_positions[i]['mmr']), 1)
                    availPos = raw_positions[i]['availPos']
                    upl = round(float(raw_positions[i]['upl']), 1)

                    if sz == '':
                        sz = 0
                    else:
                        if side == 'short':
                            sz = round(float(sz) * -1, 2)
                        elif side == 'long':
                            sz = round(float(sz), 2)
                        else:
                            raise TypeError('wrong value for side')

                    line = {'sz': sz, 'imr': imr, 'mmr': mmr, 'availPos': availPos, 'upl': upl}
                    self.risk[ccy]['FUTS'][side][instId] = line  # update all futures contract sizes and maturity

                if instType == 'SWAP':
                    #log.debug('update_risk> running through swaps loop')
                    instId = raw_positions[i]['instId']
                    side = raw_positions[i]['posSide']
                    sz = round(float(raw_positions[i]['notionalUsd']), 1)
                    imr = round(float(raw_positions[i]['imr']), 1)
                    mmr = round(float(raw_positions[i]['mmr']), 1)
                    availPos = raw_positions[i]['availPos']
                    upl = round(float(raw_positions[i]['upl']), 1)

                    if sz == '':
                        sz = 0
                    else:
                        if side == 'short':
                            sz = float(sz) * -1
                        elif side == 'long':
                            sz = float(sz)
                        else:
                            raise TypeError('wrong value for side')

                    line = {instId: {'sz': sz, 'imr': imr, 'mmr': mmr, 'availPos': availPos, 'upl': upl}}
                    self.risk[ccy]['SWAPS'][side] = line  # update all futures contract sizes and maturity

            # get net NOPs
            for ccy in self.risk:
                for prod in ['SWAPS', 'FUTS']:
                    net = 0
                    for side in ['long', 'short']:
                        for inst, v in self.risk[ccy][prod][side].items():
                            net += v['sz']
                    self.risk[ccy][prod]['net'] = round(net, 2)

        except Exception as e:
            log.error(f'update risk: {e} ', exc_info=True)
            log.debug(f'self.positions = {self.positions}')

        self.update_risk_timer.stop()

    ## okex functions

    def _funding(self, instId='BTC-USD-SWAP'):
        params = {"instId": instId}
        res = self._request_with_params(GET, FUNDING, params)
        bps = round(float(res['data'][0]['fundingRate']) * 10000, 2)
        time = int(res['data'][0]['fundingTime'])
        time = utils.human_time(time).strftime('%D %H:%M')

        next_bps = round(float(res['data'][0]['nextFundingRate']) * 10000,2)
        next_time = int(res['data'][0]['nextFundingTime'])

        next_time = utils.human_time(next_time).strftime('%D %H:%M')

        return (bps, time, next_bps, next_time)

    ## Orion functions

    def show_funding(self):
        #prints funding info for perpetual futures
        bps, time, next_bps, next_time = self._funding(self.swap)
        print(f'Funding Rate: {bps}bps at {time}')
        print(f'Next funding rate: {next_bps} at {next_time}')


    def itrade(self):
        log.info('launched itrade')
        # pretty prints for you
        def p(label='', a='', b='', c=''):
            mgn = 22
            print(label.rjust(mgn), end='\t')

            if not isinstance(a, str):
                a = str(utils.round_it(a, 6))
            if not isinstance(b, str):
                b = str(utils.round_it(b, 6))
            if not isinstance(c, str):
                c = str(utils.round_it(c, 6))
            # print all to screen
            print(a.rjust(mgn), end='\t')
            print(b.rjust(mgn), end='\t')
            print(c.rjust(mgn), end='\n')

        def det_side():
            # determine side
            prompt_side = pyip.inputStr('Buy or Sell?\n', allowRegexes=['Buy', 'Sell', 'buy', 'sell', 'b', 's', 'B', 'S'])
            print(f'you chose {prompt_side}')

            _b = ['Buy', 'buy', 'b', 'B', 'BUY']
            _s = ['Sell', 'sell', 'S', 's', 'SELL']

            if prompt_side in _b:
                side2 = 'buy'
                side1 = 'sell'
                posSide1 = 'short'
                posSide2 = 'long'
            elif prompt_side in _s:
                side2 = 'sell'
                side1 = 'buy'
                posSide1 = 'short'
                posSide2 = 'long'
            else:
                print('try that again pls...')
                side1, posSide1, side2, posSide2 = det_side()

            return side1, posSide1, side2, posSide2


        # append data to orion_orders
        def append_to_orion_orders():
            log.debug('append to orion orders ....')
            print('~~~append_to_orion_orders~~~')

            order = {'ttype': ttype,
                    'imp_bid': None, 'imp_offer': None, 'inst1_skew': 0, 'inst2_skew': 0,
                    'trgt_swap': {'buy': -10, 'sell': 10}, 'trgt_fwd1': {'buy': -50, 'sell': 50}, 'trgt_fwd2': {'buy': -100, 'sell': 100}, 'trgt_fwd3': {'buy': -100, 'sell': 100},
                    'conf_px': None, 'mm_method': 'leader', 'NOP_limit': 300,
                    'swap_delta': {'B': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'O': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'net': {'num': 0, 'sz': 0}},
                    'fwd1_delta': {'B': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'O': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'net': {'num': 0, 'sz': 0}},
                    'fwd2_delta': {'B': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'O': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'net': {'num': 0, 'sz': 0}},
                    'fwd3_delta': {'B': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'O': {'fills': [], 'num': 0, 'sz': 0, 'avg': None}, 'net': {'num': 0, 'sz': 0}},

                    'long@': None, 'short@': None, 'swap_skew': {'bid': 0, 'offer': 0}, 'fwd1_skew': {'bid': 0, 'offer': 0}, 'fwd2_skew': {'bid': 0, 'offer': 0}, 'fwd3_skew': {'bid': 0, 'offer': 0},
                    'swapT_bid': None, 'swapT_offer': None, 'fwd1T_bid': None, 'fwd1T_offer': None, 'fwd2T_bid': None, 'fwd2T_offer': None, 'fwd3T_bid': None, 'fwd3T_offer': None,
                    'call_type': call_type,
                    'fillPx1': None, 'fillPx2': None, 'ordId': None, 'status': 'pending', 'uTime': int(time.time() * 1000),
                    'lev1': 50, 'lev2': 50, 'spawns': 0, 'spawn_size': 100,
                    'num_tx': 0, 'issue_q': [],

                    'last_fld': None, 'compl': 0, 'i1cncld': [], 'i2cncld': [], 'achieved': []}

            log.info(f'orion_orders size: {len(self.orion_orders)} before appending')
            self.orion_orders.append(order)  # add to existing call levels
            log.info('order appended to orion_orders')
            log.info(f'orion_orders size: {len(self.orion_orders)} after appending')
            log.info(f'order = {order}')
            utils.save_obj(self.orion_orders, 'orion_orders') # and save it just in case something lost along the way

        #################################################
        # Start menu
        #################################################
        '''Itrade will build trades that will go into Order Watch.

        Steps:
        1. call_type = Call only or Trade
        2. Ttype = Spread, index spread, Outright
        3. buy/sell ref inst2
        4. get inst1, levels, size/leverage
        5. append to order watch'''

        # pre-start check
        #self.get_orders()
        #if 'data' in self.orders:
        #    if self.orders['data']:
        #        print('warning, you have outstanding orders...')
        #        print(self.orders['data'])
        #    else:
        #        print('no preexisting trades on exchange... ready to proceed')

        ## Step 1 = Call or Execute
        print('~~~Step 1~~~ Call level or Execute?\n')
        call_type = pyip.inputMenu(['call (email)', 'trade and email'], lettered=True)
        if call_type == 'trade and email':
            call_type = 'xqt'
        elif call_type == 'call (email)':
            call_type = 'email_only'

        # Step 2 - Determining if spread, or outright trade is required
        #######################################################
        print('~~~Step 2~~~ Two legs, spread or outright?\n')
        ttype_choice = pyip.inputMenu(['Market-maker', 'Manual'],
                '\nhow do you want to trade this?\n', lettered= True)
        ttype_dict = {'Manual': 'manual', 'Market-maker': 'marketMaker'}
        ttype = ttype_dict[ttype_choice]
        print(f'ttype = {ttype}')


        # need to accomodate for buying/selling and doing both
        if ttype == 'marketMaker':
            append_to_orion_orders()
            return




    """End of OKEX specific section****************************************** """

    def menu(self):
        funcs = ['itrade', 'executed_orders', 'cancel_all', 'status', 'edit_call_levels', 'clear_call_levels', 'clean', 'reset_curves']

        for f in enumerate(funcs):
            print(f'{f[0]}....{f[1]}')

        _ = int(input('what do you want to do? '))
        func = getattr(self, funcs[_])  # gets function from current class
        func()

    def manual_trade(self):
        args = [{"side": 'buy',
                "instId": self.swap,
                "posSide": 'long',
                "tdMode": "cross",
                "px": 1.03,
                "reduceOnly": True,
                "ordType": "post_only",
                "sz": 100,
                "clOrdId": 'dbg'
                }]

        for k, v in args[0].items():
            _ = input(str(k) + ' ' + str(v) + '....update: ')
            if _ == '':
                pass
            else:
                args[0][k] = _

        ok = input(f'OK with:\n{args}')
        _ = {"id": "mnlUpdt", "op": "batch-orders", "args": args}

        sub_str = json.dumps(_)
        #if ok=='y':
        #    self.loop.create_task(self._trade(sub_str),)
        self.loop.create_task(self._trade(sub_str))
        log.info('sent request')

    async def _trade(self, sub_str):
        res =await self.ws_private.send(sub_str)
        print(f'sent request: res is {res}')



    def cancel_batch_orders(self, active_orders):
        params = active_orders
        return self._request_with_params(POST, CANCEL_BATCH_ORDERS, params)

    def ws_cancel_order(self, instId, clOrdId):
        args = [{
                "instId": instId,
                "clOrdId": clOrdId}]


        _ = {"id": "reqCncl", "op": "cancel-order", "args": args}

        sub_str = json.dumps(_)
        self.private_ws.send(sub_str)
        log.info('sent ws cancel order')

    def clear_call_levels(self):
        # clears call level file
        self.orion_orders = []
        utils.save_obj(self.orion_orders, 'orion_orders')

    def cancel_all(self):

        # cancel all outstanding orders
        #self.get_orders() # not needed since migrating to websocket
        active_orders = []  # store ids here

        for order in self.okex_orders['data']:
            instId = order["instId"]
            clOrdId = order["clOrdId"]
            print(f'{instId} clOrId={clOrdId} {order["side"]} {order["posSide"]} {order["sz"]} @ {order["px"]}')
            active_orders.append({'instId': instId, 'clOrdId': clOrdId})

        if not active_orders == []:

            print('\nAttempting to cancel them all')
            print(f'you have: {active_orders}')
            # cancel orders in list
            res_cancel = self.cancel_batch_orders(active_orders)
            print(f'send cancellation order..\n')
            time.sleep(1)
            print(f'answer back was: {res_cancel}')

            # check if anything still outstanding
            time.sleep(1)
            res = self.okex_orders
            if res['data'] == []:
                # all cleared
                print('all done')
            else:
                print(f'after attempted cancellation some trades may still be there: {res}')

        else:
            print(f'no active OKEX orders.  current orders list={self.okex_orders}')


    def clean(self):
        # shortcut for wiping evverything clean during testing
        log.info('someone ordered a cleanup?')
        self.clear_call_levels()
        self.cancel_all()
        self.get_orders()
        self.conf = []
        self.pnd_conf = []
        self.reset_live_dists()  # reset distances to live prices
        log.debug('done with clean up')

    def get_orders(self):
        try:
            self.okex_orders = self._request_without_params(c.GET, c.ORDERS)
            log.info('request to get_orders')

        except exceptions.OkexAPIException as e:
            if e.response_text['code'] == '50110':
                # invalid IP, usually needs to be updated to allow access to private data
                self.notification = 'wrong_source... Check IP address'  # TODO: check ip errors should not be from here
            else:
                log.error(f'get_orders okexAPIException: {e}')
        except Exception as e:
            log.error(e, exc_info=True)

    def get_fills(self, instType=""):
        # gets history form alst 3 days
        params = {}
        if instType:
            params['instType'] = instType
        res = self._request_with_params(c.GET, c.FILLS, params)  # returns a list item
        return res

    def update_fills(self):
        self.fills = self.get_fills()['data']
        self.notification = 'Fills updated                 '

    def update_dist(self):
        # updates how far away we are form market
        try:
            # get dist of our actual prices from min best in market
            for tkt in (self.pnd_conf + self.conf):
                _name = next(iter(tkt))
                _last = next(iter(tkt.values()))['last']
                #self.reset_dist()

                if _last:
                    ls = round(10000 * (_last - self.vwap_swap['mid']) / self.vwap_swap['mid'], 1)  # live spread

                    if _name[2:5] == "F1B":  # buying
                        self.live_fwd1_dist_bbid = round(10000 * (self.min_fwd1['bid'] - _last) / self.min_fwd1['bid'], 1)
                        self.live_fwd1_bspread = [_last, ls]
                    elif _name[2:5] == "F1O":  # selling
                        self.live_fwd1_dist_boffer = round(10000 * (_last - self.min_fwd1['offer']) / self.min_fwd1['offer'], 1)
                        self.live_fwd1_ospread = [_last, ls]
                    elif _name[2:5] == "F2B":  # buying
                        self.live_fwd2_dist_bbid = round(10000 * (self.min_fwd2['bid'] - _last) / self.min_fwd2['bid'], 1)
                        self.live_fwd2_bspread = [_last, ls]
                    elif _name[2:5] == "F2O":  # selling
                        self.live_fwd2_dist_boffer = round(10000 * (_last - self.min_fwd2['offer']) / self.min_fwd2['offer'], 1)
                        self.live_fwd2_ospread = [_last, ls]
                    elif _name[2:5] == "F3B":  # buying
                        self.live_fwd3_dist_bbid = round(10000 * (self.min_fwd3['bid'] - _last) / self.min_fwd3['bid'], 1)
                        self.live_fwd3_bspread = [_last, ls]
                    elif _name[2:5] == "F3O":  # selling
                        self.live_fwd3_dist_boffer = round(10000 * (_last - self.min_fwd3['offer']) / self.min_fwd3['offer'], 1)
                        self.live_fwd3_ospread = [_last, ls]
                    elif _name[2:5] == "SwB":  # buying inst1
                        self.live_swap_dist_bbid = round(10000 * (self.min_swap['bid'] - _last) / self.min_swap['bid'], 1)
                        self.live_swap_bspread = [_last, ls]
                    elif _name[2:5] == "SwO":  # selling inst1
                        self.live_swap_dist_boffer = round(10000 * (_last - self.min_swap['offer']) / self.min_swap['offer'], 1)
                        self.live_swap_ospread = [_last, ls]
                    else:
                        log.error("live dist to best prices error")

        except UnboundLocalError as e:
            log.error(e, exc_info = True)
        except Exception as e:
            log.error(e, exc_info= True)



    '''Debug testing Websockets and stuff.  To be deleted later'''
    # trade
    async def trade(self):
        api_key = self.api_key
        passphrase = self.passphrase
        secret_key = self.secret_key
        url = private_url

        def get_sub_str(p):
            args_list = [{"instId": self.fwd1, "clOrdId": 'dbg', "newPx": p}]  # Note if ordId and clOrdId given, only OrdId is used by exchange
            sub_param = {"id": "reqUpdate", "op": "amend-order", "args": args_list}  # TODO: figure out id naming methodology that works for you
            sub_str = json.dumps(sub_param)
            return sub_str

        try:
            async with websockets.connect(url) as ws:
                # login
                timestamp = str(get_local_timestamp())
                login_str = login_params(timestamp, api_key, passphrase, secret_key)
                await ws.send(login_str)
                # print(f"send: {login_str}")
                res = await ws.recv()
                print(res)

                # trade
                #sub_str = json.dumps(trade_param)
                p = 1.00000
                for i in range (100):
                    p += 0.0001
                    sub_str = get_sub_str(p)
                    await ws.send(sub_str)
                    asyncio.sleep(0.1)

                try:
                    #res = await asyncio.wait_for(ws.recv(), timeout=25)
                    print('done sending')
                except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed) as e:
                    try:
                        await ws.send('ping')
                        res = await ws.recv()
                        print(res)
                    except Exception as e:
                        log.error(e, exc_info=True)

                print(get_timestamp() + res)

        except Exception as e:
            log.error(e, exc_info=True)


    ''' for testing and debugging '''
    def trgts(self):
        for trgt_inst in ['trgt_swap', 'trgt_fwd1', 'trgt_fwd2', 'trgt_fwd3']:
            for side in ['buy', 'sell']:
                trgt = pyip.inputInt(f"{side} {trgt_inst} @ {self.orion_orders[0][trgt_inst][side]}\n", blank = True)
                if trgt == '':
                    pass
                else:
                    print('updating to {trgt}\n')
                    self.orion_orders[0][trgt_inst][side] = trgt



    ## starring LittleBot
    # start it off, it will check where perp is and then issue a 5 bps wide fwd1 trade
    # we show = -10/-5 and see what happens in small tickets

    async def test_issue(self):
        args = [{"side": 'sell',
                "instId": self.fwd1,
                "posSide": 'short',
                "tdMode": "cross",
                "px": target_bid,
                "reduceOnly": False,
                "ordType": "post_only",
                "sz": 20,
                "clOrdId": 'dbg'},

                {"side": 'buy',
                "instId": self.fwd1,
                "posSide": 'long',
                "tdMode": "cross",
                "px": target_offer,
                "reduceOnly": False,
                "ordType": "post_only",
                "sz": 20,
                "clOrdId": 'dbg'
                }]

        _ = {"id": "issueMM", "op": "batch-orders", "args": args}

        sub_str = json.dumps(_)
        await self.ws_private.send(sub_str)



    def start_test(self):
        log.info('starting test')
        self.ws_test1()
        time.sleep(1)
        self.ws_test2()
        log.info('done with test')


    def ws_test1(self):
        self.loop.create_task(self.ws_debug1())

    def ws_test2(self):
        self.loop.create_task(self.ws_debug2())

    async def ws_debug1(self):
        self.loop.create_task(self.test_issue())
        log.info('issued a test ticket')

    async def ws_debug2(self):
        # first part
        p = 1.69999
        start = 1000 * time.time()
        for i in range(1, 61):
            _=(f'----------------------round {i}')
            log.info(_)

            t1 = 1000 * time.time()
            p -= 0.00003
            p = utils.round_it(p, 5)
            await self.test_update(p, rnd=i)
            _ = (f'end of round {i}: changed price to {p}.  total round(system clock): {(1000*(time.time())-t1):,.3f}')
            log.info(_)
        _1= (f' Total time took: {(1000*time.time()) - start:,.0f}')
        _2= (f'c= {self.req_timer.counts} elap={self.req_timer.elapsed} total_elapsed: {self.req_timer.total_elapsed} mean={self.req_timer.mean}')
        log.info(_1)
        log.info(_2)

        # break
        time.sleep(2)
        log.info('starting part 2')

        # second part
        p = 1.90000
        start = 1000 * time.time()
        for i in range(1, 61):
            _= (f'----------------------round {i}')
            log.info(_)

            t1 = 1000 * time.time()
            p -= 0.00002
            p = utils.round_it(p, 5)
            await self.test_update(p, rnd=i)
            #await asyncio.sleep(0.05)
            #self.get_orders()
            #print(self.okex_orders['data'][0]['px'])
            _= (f'end of round {i}: changed price to {p}.  total round(system clock): {(1000*(time.time())-t1):,.3f}')
            log.info(_)
        _1 = (f' Total time took: {(1000*time.time()) - start:,.0f}')
        _2 = (f'c= {self.req_timer.counts} elap={self.req_timer.elapsed} total_elapsed: {self.req_timer.total_elapsed} mean={self.req_timer.mean}')
        log.info(_1)
        log.info(_2)

    async def test_update(self, p, rnd):
        id_label = 'dbg' + str(rnd)
        rate_limit = 0

        args_list = [{"instId": self.fwd1, "clOrdId": 'dbg', "newPx": p}]  # Note if ordId and clOrdId given, only OrdId is used by exchange
        sub_param = {"id": id_label, "op": "amend-order", "args": args_list}  # TODO: figure out id naming methodology that works for you
        sub_str = json.dumps(sub_param)

        log.info(f'preapring to send test_update> p={p} req timer: c={self.req_timer.counts} elapsed={self.req_timer.elapsed}ms')

        lap_time = self.req_timer.lap()
        sleep_req = rate_limit - lap_time

        log.info(f'laptime={lap_time} sleep req is {sleep_req:,.1f}')

        if sleep_req > 0:
            log.info(f'sleeping for {sleep_req}')
            await asyncio.sleep(sleep_req / 1000)

        log.info('sending update req')
        await self.ws_private.send(sub_str)
        self.req_timer.update()

        _ = (f'slept for:{sleep_req} total_elapsed={self.req_timer.total_elapsed}ms mean={self.req_timer.mean}ms per trade')
        log.info(_)


    '''End of ws debug stuff'''


    async def overwatch(self):
        '''
        Structure of overwatch:

        - This is the market making version.
        - There is a spread buy level and a spread sell level.  e.g -12/-2
        - Inst2 two-way price is flashed all the time.  When it's in the zone, the update speed is increased.
        - Lets measure and monitor how that goes.  Will probably need to adjust the spread lower if we get hit a lot, and higher if get lifted.
        - Later, we will add inst1 market making.  This will be more tricky as no real refernce in place yet.
        - Ideally both inst1 and inst2 should trade against a single reference.


        functions
        issue_side1
        issue_side2
        update_side1
        update_side2
        cancel
        calc_targets

        Then there's the main loop that checks instrucitons and market and makes decisions

       '''
        self.overwatch_timer.start()  # measure code efficiecy

        def id_order(t, order):
            # returns transaction details

            # determine bid or offer, side, target_px
            if t[2:5] == 'SwB':  # Buy leg
                side = 'buy'
                inst_label = self.swap
                target_px = order['swapT_bid']
                best_px = self.min_swap['bid']

            elif t[2:5] == 'SwO':  # Sell leg
                side = 'sell'
                inst_label = self.swap
                target_px = order['swapT_offer']
                best_px = self.min_swap['offer']

            elif t[2:5] == 'F1B':  # Buy leg
                side = 'buy'
                inst_label = self.fwd1
                target_px = order['fwd1T_bid']
                best_px = self.min_fwd1['bid']
            elif t[2:5] == 'F1O':  # Sell leg
                side = 'sell'
                inst_label = self.fwd1
                target_px = order['fwd1T_offer']
                best_px = self.min_fwd1['offer']
            elif t[2:5] == 'F2B':  # Buy leg
                side = 'buy'
                inst_label = self.fwd2
                target_px = order['fwd2T_bid']
                best_px = self.min_fwd2['bid']
            elif t[2:5] == 'F2O':  # Sell leg
                side = 'sell'
                inst_label = self.fwd2
                target_px = order['fwd2T_offer']
                best_px = self.min_fwd2['offer']
            elif t[2:5] == 'F3B':  # Buy leg
                side = 'buy'
                inst_label = self.fwd3
                target_px = order['fwd3T_bid']
                best_px = self.min_fwd3['bid']
            elif t[2:5] == 'F3O':  # Sell leg
                side = 'sell'
                inst_label = self.fwd3
                target_px = order['fwd3T_offer']
                best_px = self.min_fwd3['offer']
            else:
                log.error(f"what kind of of name is: {t}?")
            return side, inst_label, target_px, best_px

        def t_details(t):
            # get full breakdown of details based on ticket in bucket

            clOrdId, v = next(iter(t.items()))
            side, inst_label, target_px, best_px = id_order(clOrdId, order)  # get trade details

            curr_px = v['last']  # last confirmed price
            req_px = v['req']  # last instruction to update price
            sz = v['sz']

            return clOrdId, curr_px, req_px, sz, side, inst_label, target_px, best_px

        async def issue_tickets():
            log.debug(f"Overwatch> issue_tickets; issue_q: [{order['issue_q']}]")
            # TODO: calculate Initial Margin Requirement as we go through the issue_q; make sure we are OK with it and display on Screen somewhere.
            BE_px = 10 # min cushion in case of slow connection adne xtreme volatility

            args = []  # blank to be populated by below process

            for t in order['issue_q']:
                side, inst_label, target_px, best_px = id_order(t, order)  # get trade details
                self.pnd_conf.append({t: {'last': None, 'req': target_px, 'sz': order['spawn_size']}})

                # manage risk/colalteral
                # determine type of intrsument (futures or swap)
                log.debug(f'Issue tickets> checking collateral for {side} {inst_label} ')
                if inst_label != self.swap:  # this is a futures contract
                    if side == 'sell':
                        try:
                            availPos = int(self.risk[inst_label[:3]]['FUTS']['long'][inst_label]['availPos'])
                            target_px = adj_bps(target_px, BE_px)
                            if availPos > order['spawn_size']:
                                reduceOnly = True
                                posSide = 'long'
                            else:
                                reduceOnly = False
                                posSide = 'short'
                        except Exception as e:
                            log.info(f'issue_tickets> could not find {inst_label}, {e}')
                            availPos = 0
                            reduceOnly = False
                            posSide = 'short'
                    if side == 'buy':
                        try:
                            availPos = int(self.risk[inst_label[:3]]['FUTS']['short'][inst_label]['availPos'])
                            target_px = adj_bps(target_px, -BE_px)
                            if availPos > order['spawn_size']:
                                reduceOnly = True
                                posSide = 'short'
                            else:
                                reduceOnly = False
                                posSide = 'long'
                        except Exception as e:
                            log.info(f'issue_tickets> could not find {inst_label}, {e}')
                            availPos = 0
                            reduceOnly = False
                            posSide = 'long'

                elif inst_label == self.swap:  # this is a perp swap contract
                    if side == 'sell':
                        try:
                            availPos = int(self.risk[inst_label[:3]]['SWAPS']['long'][inst_label]['availPos'])
                            target_px = adj_bps(target_px, BE_px)
                            if availPos > order['spawn_size']:
                                reduceOnly = True
                                posSide = 'long'
                            else:
                                reduceOnly = False
                                posSide = 'short'
                        except Exception:
                            log.info(f'issue_tickets> could not find {inst_label}')
                            availPos = 0
                            reduceOnly = False
                            posSide = 'short'
                    if side == 'buy':
                        try:
                            availPos = int(self.risk[inst_label[:3]]['SWAPS']['short'][inst_label]['availPos'])
                            target_px = adj_bps(target_px, -BE_px)
                            if availPos > order['spawn_size']:
                                reduceOnly = True
                                posSide = 'short'
                            else:
                                reduceOnly = False
                                posSide = 'long'
                        except Exception:
                            log.info(f'issue_tickets> could not find {inst_label}')
                            availPos = 0
                            reduceOnly = False
                            posSide = 'long'

                # generate args

                _args = {"side": side,
                         "instId": inst_label,
                         "posSide": posSide,
                         "tdMode": "cross",
                         "px": target_px,
                         "reduceOnly": reduceOnly,
                         "ordType": "post_only",
                         "sz": order['spawn_size'],
                         "clOrdId": t}

                args.append(_args)

            _ = {"id": "ReqAll", "op": "batch-orders", "args": args}

            log.debug(f'Overwatch> issue new tickets> _ = {_}')
            sub_str = json.dumps(_)

            await self.ws_private.send(sub_str)

            # remove from issue_q and place in pnd_conf
            order['issue_q'] = []  # clean our issue q
            log.debug("Overwatch> end issue_tickets> ")
            self.req_timer.update()

        async def update_tickets():
            self.update_tickets_timer.start()

            req_timer_lap = self.req_timer.lap()
            ''' Note: rate limit is 300 requests per 2 seconds, or approx once every 6.7ms according to docs
            but in reality for (ADA futures for examples its 60 per 2 seconds).

            Process:
                -Cycle through pnd_conf and then conf trades and decide whether or not an updated is required.
                -If update is required, piece together the arrgs and send out.
            '''
            def check_if_update_req(side, sys_px, target_px, sz_orig):
                log.debug(f'check_if_update_req> side={side} sys_px={sys_px} target_px={target_px} sz_orig={sz_orig}')

                self.check_if_update_req_timer.start()
                sz_new = None  # updated sz

                req_timer_lap = self.req_timer.lap()
                count = self.req_timer.counts

                req_soft_cap = 265    # actual cap is 300, but leave some room
                max_cap = 290  # reduced by max batch size of 6
                req_interval1 = 7  # Priority 1: min time between requests in ms
                req_interval2 = 10  # Priority 2: min time between requests in ms
                req_interval3 = 200  # Priority 3: min time between requests in ms

                # returns whether or not we need to update prices, along with size of ticket

                update_req = False
                # if hedge_priority then sz should be adapted to net_NOP imbalance
                if count > max_cap and self.regen_timer.pre_hedged:
                    log.debug('check_if_update_req> count > max_cap, skipping')
                    return sz_orig, update_req

                if req_timer_lap < req_interval1 and self.regen_timer.pre_hedged:  # If min amount of time not passed then skip everything
                    log.debug('check_if_update_req auto False as req_timer_lap < req_interval1')
                    return sz_orig, update_req

                # log.debug(f'check if update_req> sys_px={sys_px} and target_px={target_px} < compare to see if same decimal places ')
                if self.regen_timer.hedge_priority:  # update swap fast to get out of risk
                    log.debug('check_if_update_req> hedge priority is TRUE.')
                    # adjust exit side to reflect NOP imbalance`
                    if self.all_NOP > 0:

                        if side == 'sell':  # sell side reflects how long we are
                            sz_new = self.all_NOP  # if we are long, then our sell amnt should equal outstanding size of all NOP.
                            update_req = True

                        elif side == 'buy':
                            if sys_px > target_px:  # last price in system is higher than it should be
                                update_req = True
                            elif req_timer_lap > req_interval3:
                                update_req = True

                    elif self.all_NOP < 0:
                        if side == 'buy':  # sell side reflectgs how long we are
                            sz_new = abs(self.all_NOP)
                            update_req = True

                        elif side == 'sell':
                            if sys_px < target_px:  # last price at risk
                                update_req = True
                            elif req_timer_lap > req_interval3:
                                update_req = True

                elif not self.regen_timer.hedge_priority and count < req_soft_cap:   # normal updates in this scenario
                    log.debug(f'check_if_update_req> hedge_priority is FALSE.  NOP = {self.all_NOP}')
                    if self.all_NOP == 0:
                        sz_new = order['spawn_size']  # reset sizes to normal once we are square

                    if side == 'sell':
                        if sys_px:
                            if sys_px < target_px and req_timer_lap > req_interval2:  # at risk
                                update_req = True

                        if req_timer_lap > req_interval3:
                            update_req = True

                    if side == 'buy':
                        if sys_px:
                            if sys_px > target_px and req_timer_lap > req_interval2:  # at risk
                                update_req = True

                        if req_timer_lap > req_interval3:
                            update_req = True

                # if no changes, then no update needed

                if not sz_new:
                    sz_new = sz_orig

                if sys_px == target_px:  # no need to check anything if current price on exchange matches our target px
                    update_req = False
                    #log.debug(f'sys price {sys_px} matches target price {target_px} and {sz_new} unch, so no update req')

                if not self.regen_timer.pre_hedged:
                    self.regen_timer.pre_hedged = True  # After initial order to update given following a new trade, we can switch this to True
                    log.debug('check_if_update_req> pre_hedged switched to True')

                #if sz_new != order['spawn_size']:
                #    log.debug(f'check_if_update_req> sees sz_new={sz_new} and sz_orig={sz_orig}')

                self.check_if_update_req_timer.stop()

                return sz_new, update_req

            args = []
            pnd_conf = []
            _conf = []
            items_updated = 0

            log.debug(f'>>>Overwatch> NOP: {self.all_NOP} updating ticket prices; req_timer: c={self.req_timer.counts} elapsed={self.req_timer.elapsed} req_timer lap:{req_timer_lap} ')
            log.debug(f"MKT> Swap: {self.bbid_swap}/{self.boffer_swap} Fwd1: {self.bbid_fwd1}/{self.boffer_fwd1} Fwd2: {self.bbid_fwd2}/{self.boffer_fwd2}")

            for t in self.pnd_conf:
                # identify the instrument and update its price if needed
                clOrdId, curr_px, req_px, sz, side, inst_label, target_px, best_px = t_details(t)
                sz, update_req = check_if_update_req(side, req_px, target_px, sz)

                log.debug(f"update_tickets> pnd_conf> {clOrdId} {side} update_req={update_req} curr_px={curr_px} req_px={req_px} trgt={target_px} sz={sz} hedge_priority:{self.regen_timer.hedge_priority} ")

                # match inst to its target px
                if update_req:
                    # if update_req, then we append trades to be updated
                    log.info(f"update_tickets> pnd_conf> update_req TRUE: {side} {clOrdId} curr_px:{curr_px} req_px: {req_px}  target_px: {target_px} best_px: {best_px} req_timer counts/batch: {self.req_timer.counts}/{self.req_timer.batches}")

                    _args = {"instId": inst_label, "clOrdId": clOrdId, "newPx": target_px, "newSz": sz}
                    log.debug(f"updating swap to: {_args}")

                    args.append(_args)
                    _ = {clOrdId: {'last': curr_px, 'req': target_px, 'sz': sz}}
                    pnd_conf.append(_)  # track pending requists as a dict list
                    items_updated += 1  # keep track of how many items as this affects reqests limit
                else:
                    # log.debug(f'update_ticket> no update_req for {clOrdId}')
                    pnd_conf.append({clOrdId: {'last': curr_px, 'req': req_px, 'sz': sz}})  # track pending requists as a dict list

            for t in self.conf:
                clOrdId, curr_px, req_px, sz, side, inst_label, target_px, best_px = t_details(t)

                drift = round(10000 * (target_px - curr_px) / target_px, 1)  # market vs my price
                curr_sprd = round(10000 * (self.vwap_swap['mid'] - curr_px) / self.vwap_swap['mid'], 1)  # spread of curent price around mid swap

                sz, update_req = check_if_update_req(side, curr_px, target_px, sz)

                log.debug(f"update_tickets> conf> {clOrdId} {side} update_req={update_req} curr_px={curr_px} req_px={req_px} curr_sprd={curr_sprd} trgt={target_px} sz={sz} hedge_priority:{self.regen_timer.hedge_priority} req_timer lap:{req_timer_lap}")

                # Only update price if trgt to best price is negative.  i.e, our target price is better than the current best price, or if our price is at risk
                # at risk
                if update_req:
                    _args = {"instId": inst_label, "clOrdId": clOrdId, "newPx": target_px, "newSz": sz}
                    log.info(f"update_tickets> self.conf> UPDATING: {clOrdId} {inst_label} side={side} curr_px= {curr_px} curr_sprd={curr_sprd} target_px = {target_px} sz={sz} drift: {drift} hedge_priority:{self.regen_timer.hedge_priority}")

                    args.append(_args)
                    _ = {clOrdId: {'last': curr_px, 'req': target_px, 'sz': sz}}
                    log.debug(f"updating conf trade args to: {_args}")
                    pnd_conf.append(_)  # track pending requists as a dict list
                    items_updated += 1  # keep track of how many items as this affects reqests limit
                else:
                    #  we need to look up and see if clOrdId exist in prev_conf and then update the price.
                    _conf.append({clOrdId: {'last': curr_px, 'req': req_px, 'sz': sz}})  # if no need to update, then conf_list remains intact.
                    # log.debug(f"update_tickets> conf> NO updt: {clOrdId} {inst_label} side={side} curr_px:{curr_px} curr_sprd:{curr_sprd} target_px:{target_px} sz={sz} drft:{drift} priority:{self.regen_timer.hedge_priority}")

            # send requests to exchange and update internal records
            if args:
                sub_param = {"id": "reqAll", "op": "batch-amend-orders", "args": args}
                sub_str = json.dumps(sub_param)

                await self.ws_private.send(sub_str)
                log.debug(f"sent orders to exchange: {sub_param}")
                self.req_timer.update(n=items_updated)
                self.pnd_conf = pnd_conf  # replace with the new pnd_conf list
                self.conf = _conf  # replace with whatever is left unchanged in the confirmed list

            self.update_tickets_timer.stop()

            if items_updated != 0:
                log.info(f'update_tickets> done> items_updated: {items_updated} req_timer_counts: c:{self.req_timer.counts} req_max = {self.req_timer.max} elapsed:{self.req_timer.elapsed} ')
            else:
                log.debug('update_tickets> Nothing updated')

        async def cancel_side2():
            args = [{"instId": inst2_label,
                    "clOrdId": clOrdId2}]

            _ = {"id": "reqCncl", "op": "cancel-order", "args": args}

            sub_str = json.dumps(_)
            log.info('sent ws cancel order')

            await self.ws_private.send(sub_str)
            self.req_timer.update()

        # manage skews
        def manage_skews():
            # manages skews
            ss = order['spawn_size']
            self.total_NOP = self.all_NOP + self.MR_NOP
            hr = round(-2 * ((self.total_NOP) / ss), 1)  # Hedge Ratio

            # Manage skews looks at overall delta, as well as individual product imbalances.
            # So for example, if you get lifted all the time in fwd3, and dont get given, then the skew should change to reflect this.
            # swap_imb = round(2 * (order['swap_delta']['O']['sz'] - order['swap_delta']['B']['sz']) / ss, 1)  # swap_ imbalance
            swap_imb = 0  # no swap skewing for now
            fwd1_imb = round(2 * (order['fwd1_delta']['O']['sz'] - order['fwd1_delta']['B']['sz']) / ss, 1)  # swap_ imbalance
            fwd2_imb = round(2 * (order['fwd2_delta']['O']['sz'] - order['fwd2_delta']['B']['sz']) / ss, 1)  # swap_ imbalance
            fwd3_imb = round(2 * (order['fwd3_delta']['O']['sz'] - order['fwd3_delta']['B']['sz']) / ss, 1)  # swap_ imbalance

            if self.total_NOP > 0:  # we are long

                order['swap_skew']['bid'] = swap_imb + hr
                order['fwd1_skew']['bid'] = fwd1_imb + hr
                order['fwd2_skew']['bid'] = fwd2_imb + hr
                order['fwd3_skew']['bid'] = fwd3_imb + hr

                if self.MR_bid_BE_dist:
                    if self.MR_bid_BE_dist > 0:  # if in the money on Mean Reversion trades, then boost offers
                        order['swap_skew']['offer'] = swap_imb + hr
                        order['fwd1_skew']['offer'] = fwd1_imb + hr
                        order['fwd2_skew']['offer'] = fwd2_imb + hr
                        order['fwd3_skew']['offer'] = fwd3_imb + hr
                else:
                    order['swap_skew']['offer'] = swap_imb
                    order['fwd1_skew']['offer'] = fwd1_imb
                    order['fwd2_skew']['offer'] = fwd2_imb
                    order['fwd3_skew']['offer'] = fwd3_imb

            elif self.total_NOP < 0:  # we are short
                order['swap_skew']['offer'] = swap_imb + hr
                order['fwd1_skew']['offer'] = fwd1_imb + hr
                order['fwd2_skew']['offer'] = fwd2_imb + hr
                order['fwd3_skew']['offer'] = fwd3_imb + hr

                if self.MR_off_BE_dist:  # if in the money on Mean Reversion trades, then boost bids
                    if self.MR_off_BE_dist > 0:
                        order['swap_skew']['bid'] = swap_imb + hr
                        order['fwd1_skew']['bid'] = fwd1_imb + hr
                        order['fwd2_skew']['bid'] = fwd2_imb + hr
                        order['fwd3_skew']['bid'] = fwd3_imb + hr
                else:
                    order['swap_skew']['bid'] = swap_imb
                    order['fwd1_skew']['bid'] = fwd1_imb
                    order['fwd2_skew']['bid'] = fwd2_imb
                    order['fwd3_skew']['bid'] = fwd3_imb

            # reset if net delta is square or within min size
            else:
                order['swap_skew']['offer'] = swap_imb
                order['fwd1_skew']['offer'] = fwd1_imb
                order['fwd2_skew']['offer'] = fwd2_imb
                order['fwd3_skew']['offer'] = fwd3_imb

                order['swap_skew']['bid'] = swap_imb
                order['fwd1_skew']['bid'] = fwd1_imb
                order['fwd2_skew']['bid'] = fwd2_imb
                order['fwd3_skew']['bid'] = fwd3_imb

        def update_NOP_PNL():
            # update running PNL from unhedged positions
            mid = self.vwap_swap['mid']
            if self.all_longNOP:
                self.all_unbPNL_longs = round(self.all_longNOP * 10 * ((1 / self.all_avgLongPx) - (1 / mid)), 5)
            else:
                self.all_unbPNL_longs = 0

            if self.all_shortNOP:

                self.all_unbPNL_shorts = round(-self.all_shortNOP * 10 * ((1/mid) - (1 / self.all_avgShortPx)), 5)
            else:
                self.all_unbPNL_shorts = 0

            self.all_unbPNL = round(self.all_unbPNL_longs + self.all_unbPNL_shorts, 5)


            # MR PNL
            self.MR_unbPNL = round((self.MR_longNOP * mid) + self.MR_longVal - (self.MR_shortNOP * mid) + self.MR_shortVal, 5)

            if self.MR_avgShortPx:
                self.MR_off_BE_dist = round(10000 * (self.MR_avgShortPx - mid) / mid, 1)  # bid breakeven distance
            if self.MR_avgLongPx:
                self.MR_bid_BE_dist = round(10000 * (mid - self.MR_avgLongPx) / mid, 1)  # offer breakeven distance


        def NOP_to_MR(side):
            # transfer outstanding NOP to mean_reversion for holding
            log.debug(f'NOP_to_MR> before: mr_longNOP={self.MR_longNOP} MR_longVal={self.MR_longVal} MR_shortNOP={self.MR_shortNOP} MR_shortVal={self.MR_shortVal}')

            if side == 'long':
                self.MR_longNOP += self.all_longNOP
                self.MR_longVal += self.all_longVal
                self.MR_avgLongPx = utils.round_it(-self.MR_longVal / self.MR_longNOP, 6)  # longVal is minus becuase you spend cash to get it

                self.all_longNOP = 0
                self.all_longVal = 0
                self.all_avgLongPx = 0

            elif side == 'short':
                self.MR_shortNOP += self.all_shortNOP
                self.MR_shortVal += self.all_shortVal
                self.MR_avgShortPx = utils.round_it(self.MR_shortVal / self.MR_shortNOP, 6)
                self.all_shortNOP = 0
                self.all_shortVal = 0
                self.all_avgShortPx = 0

            self.MR_NOP = self.MR_longNOP + self.MR_shortNOP
            self.all_NOP = self.all_longNOP + self.all_shortNOP

            # reset all_NOP amnd related

            log.debug(f'NOP_to_MR> after: mr_longNOP={self.MR_longNOP} MR_longVal={self.MR_longVal} MR_shortNOP={self.MR_shortNOP} MR_shortVal={self.MR_shortVal}')
            log.debug(f'MR_longNOP = {self.MR_longNOP} MR_shortNOP= {self.MR_shortNOP} all_longNOP = {self.all_longNOP} all_shortNOP={self.all_shortNOP}.  All_NOP = {self.all_NOP} MR_NOP = {self.MR_NOP}')

        def calc_targets():
            self.calc_targets_timer.start()

            if self.all_NOP != self.prev_allNOP:
                log.debug(f'calc_targets> self.all_NOP {self.all_NOP} different to prev_allNOP {self.prev_allNOP}, so updating skews.')
                manage_skews()

            WF = self.regen_timer.widen_factor()
            regen_lap = self.regen_timer.lap()

            # for hybrid pricing
            imprv = 1.5  # bps of improvement over market

            log.debug(f"calc_targets> hedge_priority: {self.regen_timer.hedge_priority} all_NOP: {self.all_NOP} short@ {self.all_avgShortPx} or long@{self.all_avgLongPx} widen factor = {WF} ")

            # ref_px = self.all_avgPx   # ref price is based on where we are net long/short
            SM = self.vwap_swap['mid']

            # Manage swap pricing
            if order['mm_method'] == 'hybrid':
                order['swapT_bid'] = min(adj_bps(SM, (order['trgt_swap']['buy'] - WF + order['swap_skew']['bid'])), self.min_swap['bid'])
                order['swapT_offer'] = max(adj_bps(SM, (order['trgt_swap']['sell'] + WF + order['swap_skew']['offer'])), self.min_swap['offer'])

                order['fwd1T_bid'] = min(adj_bps(SM, (order['trgt_fwd1']['buy'] - WF + order['fwd1_skew']['bid'])), adj_bps(self.min_fwd1['bid'], imprv))
                order['fwd2T_bid'] = min(adj_bps(SM, (order['trgt_fwd2']['buy'] - WF + order['fwd2_skew']['bid'])), adj_bps(self.min_fwd2['bid'], imprv))
                order['fwd3T_bid'] = min(adj_bps(SM, (order['trgt_fwd3']['buy'] - WF + order['fwd3_skew']['bid'])), adj_bps(self.min_fwd3['bid'], imprv))

                order['fwd1T_offer'] = max(adj_bps(SM, (order['trgt_fwd1']['sell'] + WF + order['fwd1_skew']['offer'])), adj_bps(self.min_fwd1['offer'], -imprv))
                order['fwd2T_offer'] = max(adj_bps(SM, (order['trgt_fwd2']['sell'] + WF + order['fwd2_skew']['offer'])), adj_bps(self.min_fwd2['offer'], -imprv))
                order['fwd3T_offer'] = max(adj_bps(SM, (order['trgt_fwd3']['sell'] + WF + order['fwd3_skew']['offer'])), adj_bps(self.min_fwd3['offer'], - imprv))

            elif order['mm_method'] == 'leader':
                # leader shows our price irrespective of market, but not worse than crossing bid/offer

                order['swapT_bid'] = min(adj_bps(SM, (order['trgt_swap']['buy'] - WF + order['swap_skew']['bid'])), self.min_swap['offer'])
                order['swapT_offer'] = max(adj_bps(SM, (order['trgt_swap']['sell'] + WF + order['swap_skew']['offer'])), self.min_swap['bid'])

                order['fwd1T_bid'] = min(adj_bps(SM, (order['trgt_fwd1']['buy'] - WF + order['fwd1_skew']['bid'])), self.min_fwd1['offer'])
                order['fwd2T_bid'] = min(adj_bps(SM, (order['trgt_fwd2']['buy'] - WF + order['fwd2_skew']['bid'])), self.min_fwd2['offer'])
                order['fwd3T_bid'] = min(adj_bps(SM, (order['trgt_fwd3']['buy'] - WF + order['fwd3_skew']['bid'])), self.min_fwd3['offer'])

                order['fwd1T_offer'] = max(adj_bps(SM, (order['trgt_fwd1']['sell'] + WF + order['fwd1_skew']['offer'])), self.min_fwd1['bid'])
                order['fwd2T_offer'] = max(adj_bps(SM, (order['trgt_fwd2']['sell'] + WF + order['fwd2_skew']['offer'])), self.min_fwd2['bid'])
                order['fwd3T_offer'] = max(adj_bps(SM, (order['trgt_fwd3']['sell'] + WF + order['fwd3_skew']['offer'])), self.min_fwd3['bid'])

                log.debug('Before rewrite of prices')
                log.debug(f"fwd1_bid = {order['fwd1T_bid']} swap={self.min_swap['bid']} trgt_fwd1 buy= {order['trgt_fwd1']['buy']} WF={WF} skew= {order['fwd1_skew']} min_fwd1 bid= {self.min_fwd1['bid']}")
                log.debug(f"fwd1_offer = {order['fwd1T_offer']} swap= {self.min_swap['offer']} trgt_fwd1 buy= {order['trgt_fwd1']['sell']} WF={WF} skew= {order['fwd1_skew']} min_fwd1 offer= {self.min_fwd1['offer']}")

            if self.regen_timer.hedge_priority:
                mm_sprd = 5
                sprd_fwd1 = 0
                sprd_fwd2 = 0
                sprd_fwd3 = 0

                if self.all_NOP > 0:
                    ref_px = self.all_avgLongPx   # ref price is based on where we are net long/short
                    #  if we get long, then we offer everything based on reference swap px plus mm spread, but not better than market
                    if self.hedge['mmSwO']:
                        order['swapT_offer'] = max(adj_bps(ref_px, mm_sprd), adj_bps(self.min_swap['offer'], -imprv))
                    if self.hedge['mmF1O']:
                        order['fwd1T_offer'] = max(adj_bps(ref_px, (order['trgt_fwd1']['sell'] + sprd_fwd1)), adj_bps(self.min_fwd1['offer'], -imprv))
                    if self.hedge['mmF2O']:
                        order['fwd2T_offer'] = max(adj_bps(ref_px, (order['trgt_fwd2']['sell'] + sprd_fwd2)), adj_bps(self.min_fwd1['offer'], -imprv))
                    if self.hedge['mmF3O']:
                        order['fwd3T_offer'] = max(adj_bps(ref_px, (order['trgt_fwd3']['sell'] + sprd_fwd3)), adj_bps(self.min_fwd1['offer'], -imprv))

                elif self.all_NOP < 0:
                    ref_px = self.all_avgShortPx   # ref price is based on where we are net long/short
                    if self.hedge['mmSwB']:
                        order['swapT_bid'] = min(adj_bps(ref_px, -mm_sprd), adj_bps(self.min_swap['bid'], imprv))
                    if self.hedge['mmF1B']:
                        order['fwd1T_bid'] = min(adj_bps(ref_px, (order['trgt_fwd1']['buy'] - sprd_fwd1)), adj_bps(self.min_fwd1['bid'], imprv))
                    if self.hedge['mmF2B']:
                        order['fwd2T_bid'] = min(adj_bps(ref_px, (order['trgt_fwd2']['buy'] - sprd_fwd2)), adj_bps(self.min_fwd1['bid'], imprv))
                    if self.hedge['mmF3B']:
                        order['fwd3T_bid'] = min(adj_bps(ref_px, (order['trgt_fwd3']['buy'] - sprd_fwd3)), adj_bps(self.min_fwd1['bid'], imprv))

                elif self.all_NOP == 0:
                    self.regen_timer.hedge_priority = False
                    log.debug('calc_targets> hedge priority switched to False as NOP is flat')

                log.debug(f"calc_targets> regen_lap={regen_lap} mm_sprd={mm_sprd} all_NOP ={self.all_NOP} hedge_priority={self.regen_timer.hedge_priority}")
                log.debug(f"calc_targets> fwd1_bid = {order['fwd1T_bid']}  = swap mid={SM} trgt_fwd1 buy= {order['trgt_fwd1']['buy']} WF={WF} skew= {order['fwd1_skew']} min_fwd1 bid= {self.min_fwd1['bid']}")
                log.debug(f"calc_targets> fwd1_offer = {order['fwd1T_offer']}  = swap mid={SM} trgt_fwd1 sell= {order['trgt_fwd1']['sell']} WF={WF} skew= {order['fwd1_skew']} min_fwd1 offer= {self.min_fwd1['offer']}")



            # TODO: dist to best bids/offers should be in the same place as wehere we do it for live trades to best
            # calc dist away from best

            self.fwd1_dist_bbid = round(10000 * (self.min_fwd1['bid'] - order['fwd1T_bid']) / self.min_fwd1['bid'], 1)
            self.fwd1_dist_boffer = round(10000 * (order['fwd1T_offer'] - self.min_fwd1['offer']) / self.min_fwd1['offer'], 1)
            self.fwd2_dist_bbid = round(10000 * (self.min_fwd2['bid'] - order['fwd2T_bid']) / self.min_fwd2['bid'], 1)
            self.fwd2_dist_boffer = round(10000 * (order['fwd2T_offer'] - self.min_fwd2['offer']) / self.min_fwd2['offer'], 1)
            self.fwd3_dist_bbid = round(10000 * (self.min_fwd3['bid'] - order['fwd3T_bid']) / self.min_fwd3['bid'], 1)
            self.fwd3_dist_boffer = round(10000 * (order['fwd3T_offer'] - self.min_fwd3['offer']) / self.min_fwd3['offer'], 1)


            # measure dist to best bid/offer
            self.swap_dist_bbid = round(10000 * (self.min_swap['bid'] - order['swapT_bid']) / self.min_swap['bid'], 1)   # this is redundent
            self.swap_dist_boffer = round(10000 * (order['swapT_offer'] - self.min_swap['offer']) / self.min_swap['offer'], 1)  # this is redundent

            self.calc_targets_timer.stop()
        # threaded function for monitoring market spreads and reacting by notifying or executing trades
        template = []  # for sending out emails

        try:

            # Structure is like this:
            # run through order.watch and identify what inst2 and inst1 are as well as their prices

            num_orders = len(self.orion_orders)
            for i in range(num_orders):

                log.debug(f"Overwatch> START overwatch counts={self.overwatch_timer.counts} >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                # Read orion_odas ##########################
                ############################################
                order = self.orion_orders[i]
                # log.debug(f'order: {order}')
                # track total outstanding tickets
                num_conf = len(self.conf)
                num_pnd_conf = len(self.pnd_conf)
                order['num_tx'] = num_conf + num_pnd_conf

                calc_targets()
                update_NOP_PNL()  # get update to self.unbPNL for unhedged PNL

                if self.all_unbPNL < self.SL_amnt:
                    _ = (f'STOP LOSS triggered: {self.all_unbPNL} less than {self.SL_amnt}')
                    log.info(_)
                    self.notification = _

                log.debug(f"Overwatch> start> overwatch counts= {self.overwatch_timer.counts} num_tx = {order['num_tx']}")
                regen_percentage = self.regen_timer.percentage()


                # scenario for moving risk to Mean Reversion Port
                # if dist from execution reaches a certain level (50bps) and sufficient time has passed,
                # then we move risk out to allow main portoflio to continue funcitoning

                # TODO: this is temp off
                if regen_percentage == 100 and self.regen_timer.hedge_priority:  # regen process complete; hedge_priority is off

                    if (self.all_NOP > 0 and self.live_swap_ospread[1] > 20):
                        self.regen_timer.hedge_priority = False
                        NOP_to_MR('long')  # move NOP's to MR portfolio
                        self.notification = 'Long NOP sent to MR'
                        log.info(f"Overwatch> Long NOP sent to MR; hedge priority switched off. Num_tx = {order['num_tx']}")

                    elif (self.all_NOP < 0 and self.live_swap_bspread[1] < -20):
                        self.regen_timer.hedge_priority = False
                        NOP_to_MR('short')  # move NOP's to MR portfolio
                        self.notification = 'Short NOP sent to MR'
                        log.info(f"Overwatch> Short NOP sent to MR; hedge priority switched off. Num_tx = {order['num_tx']}")

                # Track FILLS and calc new deltas
                if self.regen_timer.hedge_priority:
                    # log.debug('hedge prioritised> about to launch update_tickets')
                    await update_tickets()

                elif not self.regen_timer.hedge_priority and (self.conf or self.pnd_conf):
                    # ticket exists or about to be confirmed
                    # log.debug('Overwatch> starting regular update_tickets')
                    await update_tickets()
                    # log.debug('Overwatch> done with regular update_tickets')

                if order['num_tx'] < len(self.included) and order['num_tx'] != 0:
                    regen_percentage = self.regen_timer.percentage()
                    log.debug(f'Overwatch> a trade is missing regen; regen percentage: {100*regen_percentage:,.1f}')

                    if not self.safety_shutdown:  # if safety shutdown, then no more new trades
                        if abs(self.all_NOP + self.MR_NOP) <= order['NOP_limit']:  # max size to unhedged open positions
                            log.info("Overwatch> all_NOP less than NOP limit.  Issuing more.")

                            # issuing the missing legs
                            current = set([k[:5] for d in (self.conf + self.pnd_conf) for k in d.keys()])  # get a set of outstanding trades

                            missing = self.included - current  # missing transaction(s)

                            # get client order id's for missing legs
                            for tx in missing:
                                log.debug(f"this ticket is missing: {tx}")

                                if tx == 'mmSwB':
                                    clOrdId = tx + str(order['swap_delta']['B']['num'])
                                elif tx == 'mmSwO':
                                    clOrdId = tx + str(order['swap_delta']['O']['num'])
                                elif tx == 'mmF1B':
                                    clOrdId = tx + str(order['fwd1_delta']['B']['num'])
                                elif tx == 'mmF1O':
                                    clOrdId = tx + str(order['fwd1_delta']['O']['num'])
                                elif tx == 'mmF2B':
                                    clOrdId = tx + str(order['fwd2_delta']['B']['num'])
                                elif tx == 'mmF2O':
                                    clOrdId = tx + str(order['fwd2_delta']['O']['num'])
                                elif tx == 'mmF3B':
                                    clOrdId = tx + str(order['fwd3_delta']['B']['num'])
                                elif tx == 'mmF3O':
                                    clOrdId = tx + str(order['fwd3_delta']['O']['num'])

                                order['issue_q'].append(clOrdId)  # append new trades to issue_q

                            log.debug(f"Overwatch> new issueq= {order['issue_q']} and sending to issue_tickets")

                            # update notification and orions_odas that trade is imminent
                            order['status'] = 'issuing more'
                            order['uTime'] = int(time.time() * 1000)

                            await issue_tickets()  # issues by joining best bid/offer
                            log.info('Overwatch> Done with issue_ticket')

                    else:
                        log.debug(f"Regen time = {regen_percentage}.  Didn't issue new ticket because regen time less than required; req_timer.counts={self.req_timer.counts}")

                if order['compl'] < 2000 and not self.conf and not self.pnd_conf:
                    # Initial bunch of tickets that will be issued
                    log.debug(f'Overwatch> tickets should be issued imminently;  c={self.req_timer.counts}')
                    # size management
                    # update notification and orions_odas that trade is imminent
                    order['status'] = 'triggered'
                    order['uTime'] = int(time.time() * 1000)

                    # populate required trades for initial issuance
                    for inst in self.included:
                        order['issue_q'].append(inst + 'N0')

                    # Need to issue bid@fwd1T_bid and offer at fwd1T_offer

                    await issue_tickets()  # issues by joining best bid/offer
                    log.info('Overwatch> done with issue_tickets')


        except IndexError as e:
            template = "exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'overwatch typeError: {error_message}  ', exc_info=True)
        except TypeError as e:
            template = "exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'overwatch typeError: {error_message}  ', exc_info=True)
        except Exception as e:
            template = "exception of type {0} occurred. Arguments:\n{1!r}"
            error_message = template.format(type(e).__name__, e.args)
            log.error(f'overwatch: {error_message}  ', exc_info=True)
        finally:
            # update and track actual live prices away from top of book.
            if self.orion_orders:
                oda = self.orion_orders[0]

                if self.conf != self.prev_conf or self.pnd_conf != self.prev_pnd_conf:
                    log.debug('Overwatch Summary at end *****')
                    if oda['last_fld']:
                        log.info(f"Overwatch> end> last_fld: {oda['last_fld']} ")
                    log.info(f"Overwatch> end> uTime:{oda['uTime']} num_outstanding_orders= {oda['num_tx']} req_timer c:{self.req_timer.counts} elapsed:{self.req_timer.elapsed}")
                    log.info(f"Overwatch> end> conf: {self.conf} ")
                    log.info(f"Overwatch> end> pnd_conf:{self.pnd_conf}")

                    self.prev_conf = self.conf
                    self.prev_pnd_conf = self.prev_pnd_conf

            self.update_dist()  # updates distance to actual live bid/offers on exchange

            try:
                self.overwatch_timer.stop()
                #log.debug(f'Overwatch overall took {self.overwatch_timer.elapsed}ms count={self.overwatch_timer.counts} ')   #
            except Exception as e:
                log.error(f'timer error {e}')



  #######################################################################################################################################
  #######################################################################################################################################
  #######################################################################################################################################





    def pre_start(self):
        # gets backgreound exzsiting trades
        # TODO: need to check if IP is OK first and API details in place
        #self.launch_screen()

        try:
            self.get_orders()  # make sure any pending orders are caught before starting
            self.update_fills() # update already existing fills

            # get latest funding details
            bps, time, next_bps, next_time = self._funding(self.swap)
            self.notification = f'fndg:{bps:,.1f}bps at {time}'
        except Exception as e:
            log.error(e)


    def start_public (self):
        try:
            log.info('start it started')

            #Public thread
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.result1 = self.loop.create_task(self.connect_public())  # this then start subscribe_public

            self.loop.run_forever()
            #self.loop.close()

        except Exception as e:
            log.error("main error : ", e)

    def start_private(self):
        try:
            log.info('start_private running')
            self.result2 = self.loop.create_task(self.connect_private())  # this then start subscribe_public
            self.clean()
            self.connected_private = True  # connection has been established
            log.info('start_private done its thing')
        except Exception as e:
            log.error(e)


