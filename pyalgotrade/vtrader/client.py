# PyAlgoTrade
#
# Copyright 2011-2013 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Jesse White <jwhite08@gmail.com>
"""

import cookielib
import urllib
import urllib2
import hashlib
import json
import string
import os
import re
import time
from datetime import datetime

from pyalgotrade.strategy.position import LongPosition, ShortPosition
from pyalgotrade import broker
import pyalgotrade.logger
import utils

logger = pyalgotrade.logger.getLogger("vtrader.client")

class Memoize(object):
    """ Used to cache HTTP responses. """
    def __init__(self, expiry=None):
        self.expiry = expiry
        self.nodes = {}

    class Node(object):
        def __init__(self, key, value):
            self.key = key
            self.value = value
            self.timestamp = time.time()

        def is_expired(self, expiry):
            return expiry and self.timestamp + expiry < time.time()

        def __str__(self):
            return str(self.key)

        def __hash__(self):
            return hash(str(self))

        def __cmp__(self, other):
            return cmp(str(self), str(other))

    def __call__(self, f):
        def wrapped_f(*args, **kwargs):
            # Convert the arguments to a string and skip the 1st arg 'self'
            key = '%s - %s' % (args[1:], kwargs)

            # Pull the node from the cache
            node = self.nodes.get(key, None)

            # Evaluate the function if the node is missing or expired
            if node is None or node.is_expired(self.expiry):
                value = f(*args, **kwargs)

                # Save the value to the cache
                node = Memoize.Node(key, value)
                self.nodes[key] = node

            return node.value
        return wrapped_f

class Instrument(object):
    def __init__(self, symbol):
        self.__symbol = symbol

    @staticmethod
    def fromSymbol(symbol):
        try:
            return Option(symbol)
        except ValueError:
            # If it's not an option, assume it's a stock
            return Stock(symbol)

    def getSymbol(self):
        return self.__symbol

    def getKeySymbol(self):
        raise NotImplementedError()

    def getExchange(self):
        raise NotImplementedError()

    def __str__(self):
        return str(self.__symbol)

    def __hash__(self):
        return hash(str(self))

    def __cmp__(self, other):
        return cmp(str(self), str(other))

class Stock(Instrument):
    EXCHANGE = 'TSX'

    def __init__(self, symbol):
        super(Stock, self).__init__(symbol)
        self.__class_symbol = symbol

    def getKeySymbol(self):
        return 'ca;%s' % self.getSymbol()

    def getClassSymbol(self):
        return self.__class_symbol

    def getExchange(self):
        return Stock.EXCHANGE

class Option(Instrument):
    REGEX = '^([A-Z\.]+)([0-9]{2})([0-9]{2})([0-9]{2})([CP])([0-9\.]+)$'
    EXCHANGE = 'MX'

    def __init__(self, symbol):
        super(Option, self).__init__(symbol)

        m = re.match(Option.REGEX, symbol, re.I)
        if m is None:
            raise ValueError('Invalid option symbol ' + symbol)

        self.__underlying = Stock(m.group(1))
        self.__expiry = datetime.strptime('%s %s %s' % (m.group(2), m.group(3), m.group(4)), '%y %m %d').date()
        self.__is_call = m.group(5).upper() == 'C'
        self.__strike = float(m.group(6))

    def getKeySymbol(self):
        yy = self.__expiry.strftime('%y')
        offset = 64 if self.__is_call else 76
        mm = chr(offset + self.__expiry.month)
        dd = self.__expiry.strftime('%d')

        return 'ca;O:%s\\%s%s%s\\%.1f' % (self.__underlying.getClassSymbol(),
                                          yy, mm, dd,
                                          self.__strike)

    def getExchange(self):
        return Option.EXCHANGE

    def getUnderlying(self):
        return self.__underlying

    def getExpiry(self):
        return self.__expiry

    def isCall(self):
        return self.__is_call

    def isPut(self):
        return not self.__is_call

    def getStrike(self):
        return self.__strike

class OrderFailed(Exception):
    """ Thrown when an error occurs placing an order. """
    pass

class PortfolioNotFound(Exception):
    """ Thrown when the id cannot be determined for the given portfolio name. """
    pass

class VtraderClient(object):
    """An HTTP-based client that interfaces with the Vtrader platform"""

    HOME = os.path.join(os.path.expanduser("~"), ".pyalgotrade")
    CACHE_EXPIRY_IN_SECONDS = 30

     # Maps the pyalgotrader order types to the Vtrader order types
    ALGO_TO_VTRADER_ORDER_TYPE =  {
        broker.Order.Type.MARKET : 'Market',
        broker.Order.Type.LIMIT : 'Limit',
        broker.Order.Type.STOP_LIMIT : 'StopLimit',
        broker.Order.Type.STOP : 'Stop'
    }

    # Maps the Vtrader order types to the pyalgotrader order types
    VTRADER_TO_ALGO_ORDER_TYPE = {v:k for k, v in ALGO_TO_VTRADER_ORDER_TYPE.items()}

    class Action(object):
        """Vtrader action codes - these differ by instrument type"""
        BUY_STOCK		        = 0
        SELL_STOCK              = 1
        SELL_STOCK_SHORT		= 2
        BUY_OPTION              = 3
        BUY_OPTION_TO_CLOSE     = 4
        SELL_OPTION             = 5
        SELL_OPTION_TO_CLOSE    = 6

    STOCK_ALGO_TO_VTRADER_ACTION_TYPE = {
        broker.Order.Action.BUY : Action.BUY_STOCK,
        broker.Order.Action.BUY_TO_COVER : Action.BUY_STOCK,
        broker.Order.Action.SELL : Action.SELL_STOCK,
        broker.Order.Action.SELL_SHORT : Action.SELL_STOCK_SHORT,
    }

    OPTION_ALGO_TO_VTRADER_ACTION_TYPE = {
        broker.Order.Action.BUY : Action.BUY_OPTION,
        broker.Order.Action.BUY_TO_COVER : Action.BUY_OPTION_TO_CLOSE,
        broker.Order.Action.SELL : Action.SELL_OPTION_TO_CLOSE,
        broker.Order.Action.SELL_SHORT : Action.SELL_OPTION,
    }

    ALGO_TO_VTRADER_ACTION_TYPE = {
        Stock : STOCK_ALGO_TO_VTRADER_ACTION_TYPE,
        Option : OPTION_ALGO_TO_VTRADER_ACTION_TYPE,
    }

    STOCK_VTRADER_TO_ALGO_ACTION_TYPE = {
        Action.BUY_STOCK : broker.Order.Action.BUY,
        Action.SELL_STOCK : broker.Order.Action.SELL,
        Action.SELL_STOCK_SHORT : broker.Order.Action.SELL_SHORT
    }

    OPTION_VTRADER_TO_ALGO_ACTION_TYPE = {v:k for k, v in OPTION_ALGO_TO_VTRADER_ACTION_TYPE.items()}

    VTRADER_TO_ALGO_ACTION_TYPE = {
        Stock : STOCK_VTRADER_TO_ALGO_ACTION_TYPE,
        Option : OPTION_VTRADER_TO_ALGO_ACTION_TYPE,
    }

    def __init__(self, portfolio, username, password, url, save_cookies_to_disk=True):
        self.base_url = url.strip("/")
        self.username = username
        self.password = password
        self.save_cookies_to_disk = save_cookies_to_disk
        self.cookie_file = self._getCookieFile()

        # Use by getStrategyPositions()
        self.__playback_mode = False

        # Fire up the cookie jar
        self.cj = cookielib.MozillaCookieJar(self.cookie_file)
        try:
            self.cj.load(ignore_discard=True)
        except IOError:
            if save_cookies_to_disk:
                logger.warning("Could not load the cookies from %s. Ignoring." % self.cookie_file)

        self.portfolio_name = portfolio
        logger.info("Retrieving the portfolio id for '%s'..." % self.portfolio_name)
        self.portfolio_id = self._getPortfolioId()
        logger.info("Using portfolio id %s for '%s'" % (self.portfolio_id, self.portfolio_name))

    def getPortfolios(self):
        """Retrieves the available portfolio names and corresponding ids from the server.

        :rtype: A dictionary mapping the portfolio names to their ids
        """
        portfolios = {}

        # Make a request to /VirtualTrader/Portfolio/Dashboard
        url = "%s/VirtualTrader/Portfolio/Dashboard" % self.base_url
        response = self._getCachedResponse(url)

        # The current (default) portofolio name and id will be given by a link of this form
        # 'pid="381da009-6dc2-4f2f-b302-8582d821decc"><a class="t-link" href="#PortfoliosTabStrip-1">Default</a>'
        match = re.search('pid="([0-9a-f-]+?)"><a class="t-link" href="#PortfoliosTabStrip-1">(.*?)</a>', response)
        if match:
            portfolios[match.group(2)] = match.group(1)

        # Any others will be given by links of this form
        # 'href="/VirtualTrader/Portfolio/PortfolioDashboard/381da009-6dc2-4f2a-b212-8591d821decb">Additional</a>'
        matches = re.findall('href="/VirtualTrader/Portfolio/PortfolioDashboard/([0-9a-f-]+?)">(.*?)</a>', response)
        for match in matches:
            portfolios[match[1]] = match[0]

        return portfolios

    def getCashValue(self):
        """Returns the amount of available buying power in dollars."""
        account_balance = self._getAccountBalance()
        return float(account_balance['MoneyMarketCashValue']['RawData'])

    def getShareValue(self):
        """Returns the value of the current shares if they were to be closed at the current market prices."""
        position_value = 0

        position_rows = self._getPortfolioPositions()['data']
        quote_rows = self._getPortfolioQuotes()['data']
        for position_row in position_rows:

            symbol = position_row['Symbol']
            is_option = bool(position_row['IsOption'])
            quantity = int(position_row['Quantity']['RawData'])

            multiplier = 1
            if is_option:
                multiplier = 100

            found_quote_for_symbol = False
            for quote_row in quote_rows:
                if symbol == quote_row['Symbol']:
                    found_quote_for_symbol = True

                    bid =  float(quote_row['Bid']['RawData'])
                    ask =  float(quote_row['Ask']['RawData'])

                    # We using the simulator we always buy at the ask
                    # and sell at the bid.
                    if quantity < 0:
                        inc = quantity * ask * multiplier
                    else:
                        inc = quantity * bid * multiplier
                    position_value += inc

            if not found_quote_for_symbol:
                raise Exception("Missing quote for %s" % symbol)

        return position_value

    def getEquity(self):
        """Returns the total value of current positions and cash on hand."""
        return self.getCashValue() + self.getShareValue()

    def getPositions(self):
        positions = {}
        position_rows = self._getPortfolioPositions()['data']
        for position in position_rows:
            positions[position['Symbol']] = int(position['Quantity']['RawData'])
        return positions

    def getStrategyPositions(self, strategy, commission):
        positions = {}
        try:
            self.__playback_mode = True

            position_rows = self._getPortfolioPositions()['data']
            for position in position_rows:
                instrument = position['Symbol']
                quantity = int(position['Quantity']['RawData'])
                average_price = float(position['AvgCostValue']['RawData'])
                if quantity > 0:
                    positions[instrument] = LongPosition(strategy, instrument, 0, 0, abs(quantity), True)
                elif quantity < 0:
                    positions[instrument] = ShortPosition(strategy, instrument, 0, 0, abs(quantity), True)

                order = positions[instrument].getEntryOrder()
                commission_fees = 0
                if commission is not None:
                    commission_fees = commission.calculate(order, average_price, abs(quantity))
                execution_info = broker.OrderExecutionInfo(average_price, abs(quantity), commission_fees, datetime.now())
                order.addExecutionInfo(execution_info)
        finally:
            self.__playback_mode = False
        return positions

    def getEstimatedAccountValue(self):
        account_balance = self._getAccountBalance()
        return float(account_balance['AccountValue']['RawData'])

    def getEstimatedPositionValue(self):
        account_balance = self._getAccountBalance()
        return float(account_balance['CurrentPositionValue']['RawData'])

    def getNumOpenOrders(self):
        open_orders = self._getOpenOrders()
        return int(open_orders['total'])

    def getAvailableStocks(self):
        stocks = set()

        terms = [c for c in string.lowercase]
        terms.extend(['%d' % i for i in range(0, 10)])

        for term in terms:
            url = "%s/VirtualTrader/Search/Stock?term=%s" % (self.base_url, term)
            list_of_stocks = self._getCachedResponse(url, is_json=True)
            for entry in list_of_stocks:
                stocks.add(Stock(entry['Symbol']))

        return stocks

    def updateOrder(self, order, commission):
        """Updates the order to reflect the order state on the server."""
        orders = self._getPortfolioOrdersAndTransactions()['data']

        for remoteOrder in orders:
            if remoteOrder['Id'] == order.getId():
                is_open = bool(remoteOrder['IsOpenOrder'])
                is_aborted = bool(remoteOrder['IsAbortedOrder'])
                is_partial = bool(remoteOrder['IsPartialOrder'])
                cumulative_qty = int(remoteOrder['CumulativeQuantity'])
                cumulative_avg_price = float(remoteOrder['CumulativeQuantityAveragePrice'])
                cumulative_price = cumulative_avg_price * cumulative_qty

                # Determine the price and quantity of the delta (remote state - local state)
                prev_qty = order.getFilled()
                prev_avg_price = 0.0 if order.getAvgFillPrice() is None else order.getAvgFillPrice()
                prev_price = prev_avg_price * prev_qty

                delta_qty = cumulative_qty - prev_qty
                delta_price = cumulative_price - prev_price
                delta_avg_price = delta_price / delta_qty if delta_qty <> 0 else 0

                delta_commission = 0.0
                if commission is not None:
                    delta_commission = commission.calculate(order, delta_avg_price, delta_qty)

                orderExecutionInfo = broker.OrderExecutionInfo(delta_avg_price, delta_qty,
                                                               delta_commission, datetime.now())

                if orderExecutionInfo.getQuantity() > 0:
                    order.addExecutionInfo(orderExecutionInfo)

                if is_aborted:
                    order.switchState(broker.Order.State.CANCELED)

                return orderExecutionInfo

        return None

    def cancelOrder(self, order):
        """Cancels the order on the server."""
        url = self.base_url + "/VirtualTrader/Order/CancelOrder"
        data = urllib.urlencode({
            'orderId': order.getId(),
            'portfolioId': self.portfolio_id,
            })
        return self._getResponse(url, data, is_json=True)

    def placeOrder(self, order):
        """Places the order on the server and updates the order id if successful.

           @throws OrderFailed
        """

        if self.__playback_mode:
            order.switchState(broker.Order.State.SUBMITTED)
            order.switchState(broker.Order.State.ACCEPTED)
            return

        # Determine the limit and stop prices if applicable
        limit_price = ''
        stop_price = ''

        if order.getType() in [broker.Order.Type.LIMIT, broker.Order.Type.STOP_LIMIT]:
            limit_price = order.getLimitPrice()
        if order.getType() in [broker.Order.Type.STOP, broker.Order.Type.STOP_LIMIT]:
            stop_price = order.getStopPrice()

        # Determine the duration
        if order.getType() is not broker.Order.Type.MARKET:
            duration = 1 if order.getGoodTillCanceled() else 0
        else:
            # Market orders only do not support GTC
            duration = 'Day'

        instrument = Instrument.fromSymbol(order.getInstrument())

        # They KeySymbol should always be for the underlying security
        root_key_symbol = instrument.getKeySymbol()
        if isinstance(instrument, Option):
            root_key_symbol = instrument.getUnderlying().getKeySymbol()

        # Build the data to post
        url = "%s/VirtualTrader/Order/Create" % self.base_url
        data = {
            'Duration': duration,
            'Limit': limit_price,
            'Stop': stop_price,
            'PortfolioId': self.portfolio_id,
            'OrderType': self.ALGO_TO_VTRADER_ORDER_TYPE[order.getType()],
            'Status': '',
            'KeySymbol': root_key_symbol,
            'IsFutureTrade': False,
            'IsIndexOrCurrencyOptionTrade': False,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # Add a leg for every instrument and action in the order
        # Since we're not dealing with spreads, we only need to add a single leg
        leg_index = 0
        action = self._getOrderAction(order.getAction(), instrument)
        if isinstance(instrument, Stock):
            data.update(self._getStockLeg(leg_index, action, order, instrument))
        elif isinstance(instrument, Option):
            data.update(self._getOptionLeg(leg_index, action, order, instrument))
        else:
            raise Exception("Unsupported instrument %s" % instrument)

        # Make the request
        data = urllib.urlencode(data)
        response = self._getResponse(url, data)
        if not 'Your order has been submitted' in response:
            raise OrderFailed("Received invalid response: %s" % response)

        # Update the order
        order_id = self._getBestOrderId(order)
        order.setId(order_id)

    def _getBestOrderId(self, order):
        """Attempts to retrieve the id for a recently placed order using all of the known attributes.
           This is required since the Vtrader API does not return the order ID when the order is submitted

        .. note::
            * This has some limitations in a multi-threaded or multi-client environment, but
              its the best we can do given the constraints of the API
        """
        orders = self._getPortfolioOrdersAndTransactions()['data']

        # Parse the transaction time from the orders
        for remoteOrder in orders:
            remoteOrder['_timestamp'] = float(re.search('(\d+\.?\d*)', remoteOrder['TransactionTime']).group(0))

        # Sort them by timestamp in descending order
        orders = sorted(orders, key=lambda order : -order['_timestamp'])

        # Use the id of the first order that matches the given instrument
        for remoteOrder in orders:
            # Match the instrument
            if remoteOrder['Symbol'].lower() != order.getInstrument().lower():
                continue

            # Match the order type
            if self.VTRADER_TO_ALGO_ORDER_TYPE[remoteOrder['OrderType']] != order.getType():
                continue

            # The quantity gets reset to 0 if the order is immediately rejected, so we can't rely on this
            # # Match the quantity
            # if int(remoteOrder['TotalQuantity']) != order.getQuantity():
            #     continue

            # All checks passed, assume this is the order we just place
            return remoteOrder['Id']

        logger.error("Failed to the determine the id for a recently place order. (%d orders returned)" % (len(orders)))
        raise OrderFailed()

    @staticmethod
    def _getOrderAction(action, instrument):
        """ Maps the order action to the proper Vtrader action code. """

        return VtraderClient.ALGO_TO_VTRADER_ACTION_TYPE[instrument.__class__][action]

    @staticmethod
    def _getStockLeg(id, action, order, stock):
        """ Builds an order leg for a stock. """

        leg_options = {
            'Action': action,
            'Quantity': order.getQuantity(), # Qty should always be an integer
            'DisplaySymbol': stock.getSymbol(),
            'KeySymbol': stock.getKeySymbol(),
            'Exchange': stock.getExchange(),
            'UnderlyingSymbol': stock.getSymbol(),
            'UnderlyingKeySymbol': stock.getKeySymbol(),
            'UnderlyingExchange': stock.getExchange(),
            'AssetType': 'Stock',
            'CFICode': 'ESXXXX',
            'Expiration': '',
            'Strike': '',
            'CallPutIndicator': '',
        }

        leg = {}
        for option in leg_options.keys():
            leg['OrderLegs[%d].%s' % (id, option)] = leg_options[option]
        return leg

    @staticmethod
    def _getOptionLeg(id, action, order, option):
        """ Builds an order leg for an option. """

        underlying = option.getUnderlying()
        leg_options = {
            'Action': action,
            'Quantity': int(order.getQuantity()), # Qty should always be an integer
            'DisplaySymbol': underlying.getSymbol(),
            'KeySymbol': option.getKeySymbol(),
            'Exchange': option.getExchange(),
            'UnderlyingSymbol': underlying.getSymbol(),
            'UnderlyingKeySymbol': underlying.getKeySymbol(),
            'UnderlyingExchange': underlying.getExchange(),
            'AssetType': 'Option',
            'CFICode': 'OXXXXX',
            'Expiration': option.getExpiry().strftime('%y|%m|%d'),
            'Strike': option.getStrike(),
            'CallPutIndicator': 1 if option.isCall() else 2,
        }

        leg = {}
        for option in leg_options.keys():
            leg['OrderLegs[%d].%s' % (id, option)] = leg_options[option]
        return leg

    def _getPortfolioId(self):
        portfolios = self.getPortfolios()

        if portfolios.has_key(self.portfolio_name):
            return portfolios[self.portfolio_name]
        else:
            logger.error("No portfolio named '%s' found. Available portfolio names are %s" %
                         (self.portfolio_name, portfolios.keys()))
            raise PortfolioNotFound()

    def _getAccountBalance(self):
        url = "%s/VirtualTrader/AccountBalance/GetDashboardAccountBalance" % (self.base_url)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            })
        return  self._getResponse(url, data, is_json=True)

    def _getPortfolioQuotes(self):
        url = "%s/VirtualTrader/Portfolio/PortfolioQuotes_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'orderBy': 'Change-desc',
            })
        return self._getResponse(url, data, is_json=True)

    def _getPortfolioPositions(self):
        url = "%s/VirtualTrader/Portfolio/PortfolioPositions_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'orderBy': 'PortfolioMarketValuePerc-desc',
            })
        return self._getResponse(url, data, is_json=True)

    def _getPortfolioTransactionHistory(self):
        url = "%s/VirtualTrader/Order/PortfolioTransactionHistory_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            })
        return self._getResponse(url, data, is_json=True)

    def _getPortfolioOrdersAndTransactions(self, number_of_orders_to_show=12):
        url = "%s/VirtualTrader/Order/PortfolioOrdersAndTransactions_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            'nbOrdersShow': number_of_orders_to_show,
            })
        return self._getResponse(url, data, is_json=True)

    def _getOpenOrders(self):
        url = "%s/VirtualTrader/Order/PortfolioOpenOrders_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'size': 100,
            })
        return self._getResponse(url, data, is_json=True)

    def _authenticate(self):
        logger.info("Authenticating the Vtrader client with username '%s'" % self.username)

        url = "%s/Authentication" % self.base_url
        data = urllib.urlencode({
            'Login.UserName': self.username,
            'Login.Password': self.password,
            'Login.RememberMe': False,
            })
        self._getResponse(url, data, auto_auth=False)
        if self.save_cookies_to_disk:
            logger.debug("Saving cookies to %s" % self.cookie_file)
            self.cj.save(ignore_discard=True)

    @Memoize(expiry=CACHE_EXPIRY_IN_SECONDS)
    def _getCachedResponse(self, *args, **kwargs):
        return self._getResponse(*args, **kwargs)

    def _isLoginPage(self, response):
        return re.search("Login_UserName.*Login\.UserName.*Login_Password.*Login\.Password", response, re.DOTALL) is not None

    def _getResponse(self, url, data=None, is_json=False, auto_auth=True):
        if data is None:
            logger.debug("Making HTTP request to %s" % url)
        else:
            logger.debug("Making HTTP request to %s with: %s" % (url, data))

        response = None
        retry = True
        while retry:
            retry = False
            need_to_auth = False

            try:
                opener = self._getUrlOpener(is_ajax=is_json)
                result = opener.open(url, data=data)
                response = result.read()
                result.close()
                opener.close()
            except urllib2.HTTPError, e:
                # If we're forbidden, authenticate, and retry
                if e.code == 403:
                    need_to_auth = True
                else:
                    raise

            if self._isLoginPage(response):
                need_to_auth = True

            if auto_auth and need_to_auth:
                self._authenticate()
                retry = True

        try:
            logger.debug("Got HTTP response from %s: %s" % (url, response))
        except UnicodeDecodeError:
            logger.debug("Got HTTP response from %s: (Failed to decode response)" % url)

        if is_json:
            return json.loads(response)
        return response

    def _getUrlOpener(self, set_referer=True, is_ajax=False):
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cj))

        headers = [
            ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/29.0.1547.65 Safari/537.36')
        ]
        if set_referer:
            headers.append(('Referer', '%s/VirtualTrader/Portfolio/Dashboard' % self.base_url))
        if is_ajax:
            headers.append(('X-Requested-With', 'XMLHttpRequest'))
        opener.addheaders = headers

        return opener

    def _getCookieFile(self):
        """Returns the filename used to store the cookies which is unique for every username/url pair."""

        # Hash the URL instead of storing the path
        m = hashlib.md5()
        m.update(self.base_url)
        return os.path.join(utils.getHome(), ".vtrader-%s-%s-cookies.txt" % (self.username, m.hexdigest()))
