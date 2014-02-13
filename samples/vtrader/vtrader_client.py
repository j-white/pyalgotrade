import time
import os
import ConfigParser

from pyalgotrade.vtrader import VtraderBroker
from pyalgotrade import broker

# # Uncomment to debug the HTTP requests
# import pyalgotrade.logger
# import logging
# logger = pyalgotrade.logger.getLogger("vtrader.client")
# logger.setLevel(logging.DEBUG)

def main():
    # ~/.pyalgotrade/vtrader.cfg should contain something like:
    sample_config = """
    [vtrader]
    portfolio: <YOUR-PORTFOLIO-NAME-HERE>
    username: <YOUR-USERNAME-HERE>
    password: <YOUR-PASSWORD-HERE>
    url: <VTRADER-URL-HERE>
    """

    home = os.path.join(os.path.expanduser("~"), ".pyalgotrade")
    config = ConfigParser.ConfigParser()
    config.read(os.path.join(home, 'vtrader.cfg'))
    config = dict(config.items('vtrader'))

    brk = VtraderBroker(portfolio=config['portfolio'], username=config['username'],
                        password=config['password'], url=config['url'])

    print "Total equity: %f" % brk.getEquity()
    print "Cash value: %f" % brk.getCash()
    print "Share value: %f" % brk.getShareValue()

    # Create an order to buy stock
    stock_order = brk.createMarketOrder(broker.Order.Action.BUY, 'BB', 1)
    brk.placeOrder(stock_order)
    print "Successfully placed order with id %s" % stock_order.getId()

    # Now cancel it
    brk.cancelOrder(stock_order)
    print "Successfully canceled the previous order."

    # Create an order to sell options
    order = brk.createLimitOrder(broker.Order.Action.SELL_SHORT, 'BB140222C10.00', 15.0, 1)
    brk.placeOrder(order)
    print "Successfully placed order with id %s" % order.getId()

    # If we want to retrieve the order's status one it's been placed, we need to poll
    time.sleep(5)
    brk.updateActiveOrders()
    print "Order is active: %s, filled: %s, cancelled: %s" % (order.isActive(), order.isFilled(), order.isCanceled())

if __name__ == "__main__":
    main()
