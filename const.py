# http header
API_URL = 'https://www.okex.com'
CONTENT_TYPE = 'Content-Type'
OK_ACCESS_KEY = 'OK-ACCESS-KEY'
OK_ACCESS_SIGN = 'OK-ACCESS-SIGN'
OK_ACCESS_TIMESTAMP = 'OK-ACCESS-TIMESTAMP'
OK_ACCESS_PASSPHRASE = 'OK-ACCESS-PASSPHRASE'


ACEEPT = 'Accept'
COOKIE = 'Cookie'
LOCALE = 'Locale='

APPLICATION_JSON = 'application/json'

GET = "GET"
POST = "POST"
DELETE = "DELETE"

# API
STATUS =  '/api/v5/system/status'
READ_API = '/api/v5/users/subaccount/apikey'
UPDATE_API = '/api/v5/users/subaccount/modify-apikey'
ACCOUNT_CONFIG = '/api/v5/account/config'


# accounts and risk
INSTRUMENTS = '/api/v5/public/instruments'
BALANCE = '/api/v5/account/balance'
CURRENCIES_INFO = '/api/v5/asset/currencies'
POSITIONS = '/api/v5/account/positions'
ACCOUNT_POSITION_RISK = '/api/v5/account/account-position-risk'
BILLS = '/api/v5/account/bills'
MAX_SIZE = '/api/v5/account/max-size'  # spot is in coins, futures/swaps is in contractgs
MAX_AVAIL_SIZE = '/api/v5/account/max-avail-size'
FILLS = '/api/v5/trade/fills'
FILLS_HISTORY = '/api/v5/trade/fills-history'

# public prices
MARKPRICE = '/api/v5/public/mark-price'
CANDLESTICKS = '/api/v5/market/history-candles'
TICKERS = '/api/v5/market/tickers'
TICKER = '/api/v5/market/ticker'


# leverage
GET_LEVERAGE = '/api/v5/account/leverage-info'
LEVERAGE = '/api/v5/account/set-leverage'


# trading
PLACE_ORDER = '/api/v5/trade/order'
FUTURES_FUNDING = '/api/v5/public/funding-rate-history'
ORDERS = '/api/v5/trade/orders-pending'
CANCEL_ORDER = '/api/v5/trade/cancel-order'
CANCEL_BATCH_ORDERS = '/api/v5/trade/cancel-batch-orders'
AMEND_ORDER = '/api/v5/trade/amend-order'


# FUNDING
SWAP_FUNDING = '/api/v5/public/funding-rate-history'
FUNDING = '/api/v5/public/funding-rate'

