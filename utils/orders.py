def open_position(exchange, symbol, amount, side):
    return exchange.create_order(
        symbol=symbol,
        type='market',
        side=side,
        amount=amount
    )

def place_sl(exchange, symbol, amount, sl_price, side):
    return exchange.create_order(
        symbol=symbol,
        type='STOP_MARKET',
        side=side,
        amount=amount,
        params={
            'stopPrice': sl_price,
            'closePosition': True,
            'reduceOnly': True,
            'workingType': 'MARK_PRICE'
        }
    )

def place_tp(exchange, symbol, amount, tp_price, side):
    return exchange.create_order(
        symbol=symbol,
        type='TAKE_PROFIT_MARKET',
        side=side,
        amount=amount,
        params={
            'stopPrice': tp_price,
            'closePosition': True,
            'reduceOnly': True,
            'workingType': 'MARK_PRICE'
        }
    )
