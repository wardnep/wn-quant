import ccxt

exchange = ccxt.binance({
    'apiKey': 'uHM7aOZMgcnG0VJ28qUHD4dsDXQ5nBWJMMbUC5Kulqr2V1lnVHKsDz1l7UMIArXa',
    'secret': '8qPb3w9cbQP2iin6pzyWt54NTPtNfBM2oUc5V52uhHa7wvQZ5PPUqLeYMqOBd86',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

exchange.set_sandbox_mode(True)
