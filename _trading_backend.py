# list all trading functions here to be imported by backend_orionv2 if needed
#from utils import round_it
#import pyinputplus as pyip
#import logging

import const as c

import exceptions
#log = logging.getLogger(__name__)
#log.info("Hello logging!: trading_backend is up")

''' Trading section '''
def _request(self, method, request_path, params, cursor=False):
    #log.info(f'_request used (should be for backup purposes only): {params}')
    # used for nonwebsocket requests

    #log.debug(f'attemping to use _request on : {method} ~~~ {request_path} ~~~ {params}')
    if method == c.GET:
        request_path = request_path + utils.parse_params_to_str(params)
    # url
    url = c.API_URL + request_path

    timestamp = utils.get_timestamp()
    # sign & header
    if self.use_server_time:
        timestamp = self._get_timestamp()
    body = json.dumps(params).replace(' ', '') if method == c.POST else ""

    sign = utils.sign(utils.pre_hash(timestamp, method, request_path, str(body)), self.api_secret_key)
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


def get_leverage(self, instId, mgnMode = "isolated"):
    params = {"instId": instId, "mgnMode": mgnMode}

    return self._request_with_params(GET, GET_LEVERAGE, params)


def set_leverage(self, instId = "", ccy= "", lever = "2", mgnMode = "isolated", posSide = ""):
    params= {"instId": instId, "ccy": ccy, "lever": lever, "mgnMode": mgnMode, "posSide": posSide}
    return self._request_with_params(POST, LEVERAGE, params)

def place_order(self, instId="BTC-USD-SWAP", tdMode="cross", clOrdId="test", side="buy", ccy="", posSide="", ordType="limit", px="", sz="", reduceOnly=False):
    params = {"instId": instId, "tdMode": tdMode, "clOrdId": clOrdId, "ordType": ordType, "side": side, "px": px, "sz": sz}

    if posSide:
        params['posSide'] = posSide
    if reduceOnly:
        params['reduceOnly'] = reduceOnly
    if ccy:
        params['ccy'] = ccy

    return self._request_with_params(POST, PLACE_ORDER, params)

def ws_place_order(self, id="orion", instId="BTC-USD-SWAP", tdMode="cross", clOrdId="test", side="buy", ccy="", posSide="", ordType="post_only", px="", sz="", reduceOnly=False):
    params = {"instId": instId, "tdMode": tdMode, "clOrdId": clOrdId, "ordType": ordType, "side": side, "px": px, "sz": sz}

    if posSide:
        params['posSide'] = posSide
    if reduceOnly:
        params['reduceOnly'] = reduceOnly
    if ccy:
        params['ccy'] = ccy

    _ = {"id": id, "op": "order", "args": [params]}  # TODO: figure out id naming methodology that works for you


    sub_str = json.dumps(_)
    self.private_ws.send(sub_str)
    log.debug(f'ws_place_order> sent : {sub_str}')
    log.debug('done sending websocket place_order')

def test_buy(self):
    #debug only, remove later
    bids2 = self.stack2['bids']
    bbid2 = float(next(iter(bids2)))
    px = bbid2 + 0.00001
    self.ws_place_order(instId='ADA-USD-211224', side='buy', posSide='long', px=px, sz=69)
    log.debug('sent order')

#see outstanding trades

def get_orders(self):
    try:
        params = {}
        self.orders = self._request_with_params(c.GET, c.ORDERS, params)
        #log.debug(f'get_orders OG: {self.orders}')

    except exceptions.OkexAPIException as e:
        if e.response_text['code'] == '50110':
            # invalid IP, usually needs to be updated to allow access to private data
            self.debug = 'wrong_source... Check IP address'  # TODO: check ip errors should not be from here
        else:
            log.error('get_orders okexAPIException: {e}')
        #log.error(f'get_orders: response_text: {e._text}, response code: {e.code}')

def cancel_order(self, instId="BTC-USD-SWAP", ordId='', clOrdId='test'):
    params = {"instId": instId}

    if ordId:
        params["ordId"] = ordId
    if clOrdId:
        params["clOrdId"] = clOrdId
    return self._request_with_params(c.POST, c.CANCEL_ORDER, params)



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




def cancel_all(self):
    # cancel all outstanding orders
    #self.get_orders() # not needed since migrating to websocket
    active_orders = []  # store ids here

    for oda in self.orders['data']:
        instId = oda["instId"]
        clOrdId = oda["clOrdId"]
        print(f'{instId} clOrId={clOrdId} {oda["side"]} {oda["posSide"]} {oda["sz"]} @ {oda["px"]}')
        active_orders.append({'instId': instId, 'clOrdId':clOrdId})

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
        res = self.orders
        if res['data'] == []:
            # all cleared
            print('all done')
        else:
            print(f'after attempted cancellation some trades may still be there: {res}')
    else:
        print (f'no active orders.  current orders list={self.orders}')

def amend_order(self, instId, cxlOnFail=False, clOrdId="", ordId="", newSz="", newPx=""):
    params = {}
    params['instId'] = instId
    if clOrdId:
        params['clOrdId'] = clOrdId
    if ordId:
        params['ordId'] = ordId
    if newSz:
        params['newSz'] = newSz
    if newPx:
        params['newPx'] = newPx

    return self._request_with_params(POST, AMEND_ORDER, params)

def executed_orders(self):
    # print a list from a file that stores exxecuted orders
    orders = utils.load_obj('.executed_orders')
    for i in range(len(orders)):
        print(orders[i])


'''smarter execution functions '''

def list_tradables(self, ccy):
    # list all tradeables under particular idx name
    # used as a helper funciton in choosing products to trade
    idx_name = 'OKE-' + ccy + '-USD-SWAP'
    curve_name = 'OKE-' + ccy + '-USD-CURVE'

    data = self.curves_price_list[curve_name]

    index_price = float(self.subscription_list[idx_name]['indexPrice'])

    print('~' * 100)
    print('Spot/Swaps:')
    for i in self.subscription_list:
        if i[4:7] == ccy and not i[-7] == '-':
            print(f"{self.subscription_list[i]['instType']} {i} price: {self.subscription_list[i]['last']} ")

    #print(f'\nSPOT: {idx_name}  SWAP Price: {index_price:,}*  ')
    #print(f'\nSWAP: {idx_name}  SWAP Price: {index_price:,}*  ')
    print('Futures: ')
    for date, price in sorted(data.items()):
        tenor = utils.calc_days_rem_direct(date)

        price_diff = price - index_price
        bps_diff = 10000 * (price_diff / index_price)  # NOTE: The denominator means everything is relative to the index (not tradeable)
        ann_bps = bps_diff * (365/tenor)

        print(f'{date.strftime("%y%m%d")} days_rem: {tenor:,.1f} ~~~ price:{price:,} ~~~ spread_USD: {(price-index_price):,.5g} ~~~ sprd_bps:{bps_diff:>,.0f} ~~~ sprd_ann: {ann_bps:,.0f}')

    print('~' * 100)





def itrade(self):

    def p(label='', a='', b='', c=''):
        # pretty prints for you
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


    def append_to_orion_orders():
        print('~~~append_to_orion_orders~~~')

        p('insts: ', inst1_label, inst2_label)
        p('ttype: ', '', ttype)
        p('call_type: ', '', call_type)
        p('posSize: ', posSize1, posSize2)
        p('posSide: ', posSide1, posSide2)
        p('side: ', side1, side2)
        p('reduceOnly: ', reduceOnly1, reduceOnly2)
        p('lev: ', lev1, lev2)
        p('target: ', '', str(sign) + '' +str(target))

        _ = pyip.inputYesNo('To confirm, you OK with the above?\n ')

        if _  == 'yes':
            #if yes, then we add this to trades monitor, which would then deal with it appropriately
            ## note, some variables are redundant and needed to double check initial booking.  They will be dropped off before appending to orderwatch (e.g side1 = opposite of side2)
            ## other variables will be None or N/A such as those needed for single sided or outright orders

            print('appending to orderwatch')
            log.info('appending to orion_orders')
            order = {'inst1': inst1_label, 'inst2': inst2_label, 'sign': sign, 'side1': side1, 'side2': side2, 'ttype': ttype, 'clOrdId': None,
                    'impl_last': None, 'imp_bid': None, 'imp_offer': None, 'target': target, 'conf_px': None, 'posSide1': posSide1, 'posSide2': posSide2,
                    'size1': posSize1, 'size2': posSize2, 'call_type': call_type, 'i1order_px': 'pending', 'i2order_px': 'pending', 'fillPx1': None, 'fillPx2': None, 'ordId': None, 'status': 'pending', 'uTime': int(time.time() * 1000),
                    'reduceOnly1': reduceOnly1, 'reduceOnly2': reduceOnly2, 'lev1': lev1, 'lev2': lev2, 'i1pnd_conf': [], 'i1conf': [], 'i2pnd_conf': [], 'i2conf': [], 'spawns': 0, 'spawn_size1': 0, 'spawn_size2': 0,
                    'i1fld': [], 'i2fld': [], 'compl': 0, 'i1cncld': [], 'i2cncld': []}

            log.info(f'orion_orders size: {len(self.orion_orders)} before appending')
            self.orion_orders.append(order)  # add to existing call levels

            log.info(f'order appended to orion_orders')
            log.info(f'orion_orders size: {len(self.orion_orders)} after appending')
            log.info(f'order = {order}')
            utils.save_obj(self.orion_orders, 'orion_orders') # and save it just in case something lost along the way
        else:
            print('exited, no orders sent')

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
    self.get_orders()

    if self.orders['data']:
        print('warning, you have outstanding orders...')
        print(self.orders['data'])
    else:
        print('no preexisting trades on exchange... ready to proceed')

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
    ttype_choice = pyip.inputMenu(['spread against another instrument', 'spread against an index', 'outright cash trade', 'F.A.S.T', 'test - buy sprd', 'test - sell sprd', 'debug - monitor BUY', 'debug - monitor SELL'],
            '\nhow do you want to trade this?\n', lettered= True)
    ttype_dict = {'spread against another instrument': '1st_of2', 'spread against an index': 'single_sided', 'outright cash trade': 'outright',
            'F.A.S.T': 'FAST', 'test - buy sprd': 'testBuy', 'test - sell sprd': 'testSell', 'debug - monitor BUY': 'debugMonitorB', 'debug - monitor SELL': 'debugMonitorS'}
    ttype = ttype_dict[ttype_choice]
    print(f'ttype = {ttype}')


    # need to accomodate for buying/selling and doing both
    if ttype == 'debugMonitorS':
        target = int(input('enter target'))
        ttype = 'laser'
        posSize1 = posSize2 = 500
        posSide1 = 'short'
        reduceOnly1 = True
        posSide2 = 'long'
        reduceOnly2 = True
        side1 = 'buy'
        side2 = 'sell'
        inst1_label = 'OKE-ADA-USD-SWAP'
        inst2_label = 'OKE-ADA-USD-211231'
        sign = '>'
        #target = -5
        lev1 = 50
        lev2 = 50

        append_to_orion_orders()
        return

    if ttype == 'debugMonitorB':
        target = int(input('enter target'))
        ttype = 'laser'
        posSize1 = posSize2 = 500
        posSide1 = 'short'
        reduceOnly1 = False
        posSide2 = 'long'
        reduceOnly2 = False
        side1 = 'sell'
        side2 = 'buy'
        inst1_label = 'OKE-ADA-USD-SWAP'
        inst2_label = 'OKE-ADA-USD-211231'
        sign = '<'
        #target = -14
        lev1 = 50
        lev2 = 50

        append_to_orion_orders()
        return

    #### Step 3 - Buy or sell main trading instrument (inst2)
    ################################################
    print('~~~step 3~~~ Get inst2')
    side2, inst2_label = get_instrument()
    print(f'determined side2={side2} and inst2_label = {inst2_label}')

    ####  step 4: get rest of details
    ########################
    print('~~~step 4~~~ Get rest of details')

    posSize1, posSize2, posSide1, posSide2, side1, inst1_label, sign, target, reduceOnly1, reduceOnly2, lev1, lev2 = get_rem_dets()

    print(f'about to append to order watch, but jsut before let me tell you that {reduceOnly1} and {reduceOnly2} are weird')

    ## step 5
    append_to_orion_orders()  ## add info to order watch



