import ccxt

exchange = ccxt.binance({
    'apiKey': 'coqcNImEcujq0iBu6xj2WdNFOW96KtKe9AbjpgQvC6c5ibL66bNkMQo9Jq0EUSTa',
    'secret': '9vUCPrVFjk8PDAVQnCmYvPP0nBIcvtvVvgNztnTM1YK42IMO4PUymWqkSWmpooLZ',
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future',
        'adjustForTimeDifference': True
    }
})

exchange.enable_demo_trading(True)

balance = exchange.fetch_balance()
usdt_balance = balance['USDT']['free']
print(f'Available USDT: {usdt_balance}')

#######################################################################################################################################

symbol = 'BTC/USDT'
amount = 0.001

# entry_order = exchange.create_order(
#     symbol='BTC/USDT',
#     type='market',
#     side='buy',
#     amount=0.001
# )

# print(entry_order)

sl_price = 70000
tp_price = 80000

sl_order = exchange.create_order(
    symbol=symbol,
    type='STOP_MARKET',
    side='sell',
    amount=amount,
    params={
        'stopPrice': sl_price,
        'closePosition': True
    }
)

tp_order = exchange.create_order(
    symbol=symbol,
    type='TAKE_PROFIT_MARKET',
    side='sell',
    amount=amount,
    params={
        'stopPrice': tp_price,
        'closePosition': True
    }
)

print(sl_order)
print(tp_order)
