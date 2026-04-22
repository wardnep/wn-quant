def open_long(exchange, symbol, amount):
    return exchange.create_order(
        symbol=symbol,
        type='market',
        side='buy',
        amount=amount
    )

def open_short(exchange, symbol, amount):
    return exchange.create_order(
        symbol=symbol,
        type='market',
        side='sell',
        amount=amount
    )

def place_sl(exchange, symbol, amount, sl_price, side):
    return exchange.create_order(
        symbol=symbol,
        type='STOP_MARKET',
        side='sell',
        amount=amount,
        params={
            'stopPrice': sl_price,
            'closePosition': True
        }
    )

def place_tp(exchange, symbol, amount, tp_price, side):
    return exchange.create_order(
        symbol=symbol,
        type='TAKE_PROFIT_MARKET',
        side='sell',
        amount=amount,
        params={
            'stopPrice': tp_price,
            'closePosition': True
        }
    )
