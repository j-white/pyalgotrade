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
from datetime import datetime

from pyalgotrade import broker
import pyalgotrade.logger

from GenericCache.GenericCache import GenericCache

logger = pyalgotrade.logger.getLogger("vtrader.client")

class OrderFailed(Exception):
    pass

class PortfolioNotFound(Exception):
    pass

class VtraderClient():
    home = os.path.join(os.path.expanduser("~"), "pyalgotrader")
    cache_expiry_in_seconds = 30

    class Action:
        BUY_STOCK		        = 0
        SELL_STOCK              = 1
        SELL_STOCK_SHORT		= 2
        BUY_OPTION              = 3
        BUY_OPTION_TO_CLOSE     = 4
        SELL_OPTION             = 5
        SELL_OPTION_TO_CLOSE    = 6

    class InstrumentType(object):
        STOCK = 1
        CALL_OPTION = 2
        PUT_OPTION = 3

     # Maps the order type to the proper Vtrader order type.
    ALGO_TO_VTRADER_ORDER_TYPE =  {
        broker.Order.Type.MARKET : 'Market',
        broker.Order.Type.LIMIT : 'Limit',
        broker.Order.Type.STOP_LIMIT : 'StopLimit',
        broker.Order.Type.STOP : 'Stop'
    }

    VTRADER_TO_ALGO_ORDER_TYPE = {v:k for k, v in ALGO_TO_VTRADER_ORDER_TYPE.items()}

    def __init__(self, portfolio, username, password, url):
        self.base_url = url
        self.username = username
        self.password = password
        self.cookie_file = self._get_cookie_file()

        # Create the working directory if not already present
        if not os.path.exists(self.home):
            os.makedirs(self.home)

        # Fire up the cookie jar
        self.cj = cookielib.MozillaCookieJar(self.cookie_file)
        try:
            self.cj.load(ignore_discard=True)
        except IOError:
            pass

        # Setup the cache
        self.cache = GenericCache(expiry=self.cache_expiry_in_seconds)

        # Dynamically determine the portfolio id from the portfolio name
        self.portfolio_name = portfolio
        self.portfolio_id = self._get_portfolio_id()

    def _get_cookie_file(self):
        """Returns the filename used to store the cookies which is unique for every username/url pair."""

        # Hash the URL instead of storing the path
        m = hashlib.md5()
        m.update(self.base_url)
        return os.path.join(self.home, "vtrader-%s-%s-cookies.txt" % (self.username, m.hexdigest()))

    def _get_portfolio_id(self):
        portfolios = self.get_portfolios()

        if portfolios.has_key(self.portfolio_name):
            return portfolios[self.portfolio_name]
        else:
            raise PortfolioNotFound()

    def get_portfolios(self):
        portfolios = {}

        # Make a request to /VirtualTrader/Portfolio/Dashboard
        url = "%s/VirtualTrader/Portfolio/Dashboard" % self.base_url
        response = self.__get_response_data(url, cached=True)

        # The current (default) portofolio name and id will be given by a link of this form
        # 'pid="381da009-6dc2-4f2f-b302-8591d821decb"><a class="t-link" href="#PortfoliosTabStrip-1">Quant</a>'
        match = re.search('pid="([0-9a-f-]+?)"><a class="t-link" href="#PortfoliosTabStrip-1">(.*?)</a>', response)
        if match:
            portfolios[match.group(2)] = match.group(1)

        # Any others will be given by links of this form
        # 'href="/VirtualTrader/Portfolio/PortfolioDashboard/381da009-6dc2-4f2f-b302-8591d821decb">Quant</a>'
        matches = re.findall('href="/VirtualTrader/Portfolio/PortfolioDashboard/([0-9a-f-]+?)">(.*?)</a>', response)
        for match in matches:
            portfolios[match[1]] = match[0]

        return portfolios

    def get_cash_value(self):
        account_balance = self._get_account_balance()
        return float(account_balance['MoneyMarketCashValue']['RawData'])

    def get_last_orderid_for_instrument(self, instrument):
        orders = self._get_portfolio_orders_and_transactions()['data']

        # Parse the transaction time from the orders
        for order in orders:
            order['_timestamp'] = float(re.search('(\d+\.\d+)', order['TransactionTime']).group(0))

        # Sort them by timestamp in descending order
        orders = sorted(orders, key=lambda order : -order['_timestamp'])

        # Use the id of the first order that matches the given instrument
        for order in orders:
            if order['Symbol'].lower() == instrument.lower():
                return order['Id']

        return -1

    def update_order(self, order, commission):
        orders = self._get_portfolio_orders_and_transactions()['data']

        for r_order in orders:
            if r_order['Id'] == order.getId():
                is_open = bool(r_order['IsOpenOrder'])
                is_aborted = bool(r_order['IsAbortedOrder'])
                is_partial = bool(r_order['IsPartialOrder'])
                quantity = int(r_order['CumulativeQuantity'])
                average_price = float(r_order['CumulativeQuantityAveragePrice'])
                price = average_price * quantity

                if not is_open and not is_aborted and not is_partial:
                    fees = 0.0
                    if commission is not None:
                        fees = commission.calculate(order, price, quantity)

                    orderExecutionInfo = broker.OrderExecutionInfo(price, quantity, fees, datetime.now())
                    order.setExecuted(orderExecutionInfo)
                elif is_aborted:
                    order.switchState(broker.Order.State.CANCELED)

                break

    def place_order(self, order):
        # Values used for market orders
        limit_price = ''
        stop_price = ''

        if order.getType() in [broker.Order.Type.LIMIT, broker.Order.Type.STOP_LIMIT]:
            limit_price = order.getLimitPrice()
        if order.getType() in [broker.Order.Type.STOP, broker.Order.Type.STOP_LIMIT]:
            stop_price = order.getStopPrice()

        if order.getType() is not broker.Order.Type.MARKET:
            duration = 1 if order.getGoodTillCanceled() else 0
        else:
            duration = 'GoodTillCanceled' if order.getGoodTillCanceled() else 'Day'

        url = "%s/VirtualTrader/Order/Create" % self.base_url
        data = {
            'Duration': duration,
            'Limit': limit_price,
            'Stop': stop_price,
            'PortfolioId': self.portfolio_id,
            'OrderType': self.ALGO_TO_VTRADER_ORDER_TYPE[order.getType()],
            'Status': '',
            'KeySymbol': self.__get_key(order.getInstrument()),
            'IsFutureTrade': False,
            'IsIndexOrCurrencyOptionTrade': False,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # We should repeat this for every leg in the spread, but we're only dealing with simple orders
        leg_index = 0
        action = self._get_order_action(order)
        instrument_type = self.__get_instrument_type(order.getInstrument())
        if instrument_type == self.InstrumentType.STOCK:
            data.update(self.__get_stock_leg(leg_index, action, order))
        else:
            raise Exception("Option orders are not yet supported.")
            #data.update(self.__get_option_leg(leg_index, order))

        data = urllib.urlencode(data)
        response = self.__get_response_data(url, data)
        if not 'Your order has been submitted' in response:
            raise OrderFailed("Received invalid response: %s" % response)

    def _get_order_action(self, order):
        """ Maps the order action to the proper Vtrader action code. """

        stockOrderActionMap = {
            broker.Order.Action.BUY : self.Action.BUY_STOCK,
            broker.Order.Action.BUY_TO_COVER : self.Action.BUY_STOCK,
            broker.Order.Action.SELL : self.Action.SELL_STOCK,
            broker.Order.Action.SELL_SHORT : self.Action.SELL_STOCK_SHORT,
        }

        optionOrderActionMap = {
            broker.Order.Action.BUY : self.Action.BUY_OPTION,
            broker.Order.Action.BUY_TO_COVER : self.Action.BUY_OPTION_TO_CLOSE,
            broker.Order.Action.SELL : self.Action.SELL_OPTION_TO_CLOSE,
            broker.Order.Action.SELL_SHORT : self.Action.SELL_OPTION,
        }

        orderActionMap = {
            self.InstrumentType.STOCK : stockOrderActionMap,
            self.InstrumentType.CALL_OPTION : optionOrderActionMap,
            self.InstrumentType.PUT_OPTION : optionOrderActionMap,
        }

        instrument_type = self.__get_instrument_type(order.getInstrument())
        return orderActionMap[instrument_type][order.getAction()]

    def __get_stock_leg(self, id, action, order):
        leg_options = {
            'Action': action,
            'Quantity': order.getQuantity(),
            'DisplaySymbol': order.getInstrument(),
            'KeySymbol': self.__get_key(order.getInstrument()),
            'Exchange': 'TSX',
            'UnderlyingSymbol': order.getInstrument(),
            'UnderlyingKeySymbol': self.__get_key(order.getInstrument()),
            'UnderlyingExchange': 'TSX',
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

    def get_positions(self):
        positions = {}
        position_rows = self._get_portfolio_positions()['data']
        for position in position_rows:
            positions[position['Symbol'].lower()] = int(position['Quantity']['RawData'])
        return positions

    def get_account_value(self):
        return self.get_cash_value() + self.get_position_value()

    def get_position_value(self):
        """Returns the value of the current positions if they were to be sold at the current market prices."""
        position_value = 0

        position_rows = self._get_portfolio_positions()['data']
        quote_rows = self._get_portfolio_quotes()['data']
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

    def get_estimated_account_value(self):
        account_balance = self._get_account_balance()
        return float(account_balance['AccountValue']['RawData'])

    def get_estimated_position_value(self):
        account_balance = self._get_account_balance()
        return float(account_balance['CurrentPositionValue']['RawData'])

    def get_outstanding_orders_value(self):
        account_balance = self._get_account_balance()
        return float(account_balance['TotalOutstandingOrdersValue']['RawData'])

    def get_num_open_orders(self):
        open_orders = self._get_open_orders()
        return int(open_orders['total'])

    def _get_summary(self):
        url = "%s/VirtualTrader/Portfolio/GetSummary" % self.base_url
        return self.__get_response_data(url, is_json=True)

    def _get_account_balance(self):
        url = "%s/VirtualTrader/AccountBalance/GetDashboardAccountBalance" % (self.base_url)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            })
        return  self.__get_response_data(url, data, is_json=True)

    def _get_portfolio_quotes(self):
        url = "%s/VirtualTrader/Portfolio/PortfolioQuotes_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'orderBy': 'Change-desc',
            })
        return self.__get_response_data(url, data, is_json=True)

    def _get_portfolio_positions(self):
        url = "%s/VirtualTrader/Portfolio/PortfolioPositions_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'orderBy': 'PortfolioMarketValuePerc-desc',
            })
        return self.__get_response_data(url, data, is_json=True)

    def _get_portfolio_transaction_history(self):
        url = "%s/VirtualTrader/Order/PortfolioTransactionHistory_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            })
        return self.__get_response_data(url, data, is_json=True)

    def _get_portfolio_orders_and_transactions(self, nbOrdersShow=5):
        url = "%s/VirtualTrader/Order/PortfolioOrdersAndTransactions_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'portfolioId': self.portfolio_id,
            'nbOrdersShow': nbOrdersShow,
            })
        return self.__get_response_data(url, data, is_json=True)

    def _get_available_stocks(self):
        stocks = {}

        terms = [c for c in string.lowercase]
        terms.extend(['%d' % i for i in range(0, 10)])

        for term in terms:
            url = "%s/VirtualTrader/Search/Stock?term=%s" % (self.base_url, term)
            list_of_stocks = self.__get_response_data(url, is_json=True,  cached=True)
            for entry in list_of_stocks:
                stocks[entry['Symbol']] = entry

        return stocks

    def _get_open_orders(self):
        url = "%s/VirtualTrader/Order/PortfolioOpenOrders_AjaxGrid/%s" % (self.base_url, self.portfolio_id)
        data = urllib.urlencode({
            'page': 1,
            'size': 100,
            })
        return self.__get_response_data(url, data, is_json=True)

    def _cancel_order(self, order_id):
        url = self.base_url + "/VirtualTrader/VirtualTrader/Order/CancelOrder"
        data = urllib.urlencode({
            'orderId': order_id,
            'portfolioId': self.portfolio_id,
            })
        return self.__get_response_data(url, data, is_json=True)

    def __get_instrument_type(self, instrument):
        """Returns the type of instrument. Valid instrument types are:

         * InstrumentType.STOCK
         * InstrumentType.CALL_OPTION
         * InstrumentType.PUT_OPTION
        """
        return VtraderClient.InstrumentType.STOCK

    def __get_key(self, instrument):
        type = self.__get_instrument_type(instrument)

        if type == VtraderClient.InstrumentType.STOCK:
            return 'ca;%s' % instrument
        else:
            # We're dealing with an option
            class_symbol = "TODO"
            expiry_date = datetime.today()
            strike_price = 11

            yy = expiry_date.strftime('%y')
            offset = 64 if type == VtraderClient.InstrumentType.CALL_OPTION else 76
            mm = chr(offset + expiry_date.month)
            dd = expiry_date.strftime('%d')

            return 'ca;O:%s\\%s%s%s\\%.1f' % (class_symbol, yy, mm, dd, strike_price)

    def _authenticate(self):
        url = "%s/Authentication" % self.base_url
        data = urllib.urlencode({
            'Login.UserName': self.username,
            'Login.Password': self.password,
            'Login.RememberMe': False,
            })
        self.__get_response_data(url, data, auto_auth=False)
        self.cj.save(ignore_discard=True)

    def __get_opener(self, set_referer=True, is_ajax=False):
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

    def __get_response_data(self, url, data=None, is_json=False, cached=False, auto_auth=True):
        response = None
        key = None
        if cached:
            # Hash the URL and data
            m = hashlib.sha256()
            m.update(url)
            m.update(str(data))

            # Cache lookup
            key = "vtrader-%s" % m.hexdigest()
            response = self.cache[key]

        if not response:
            logger.debug("HTTP request to %s with: %s" % (url, data))


            retry = True
            while retry:
                retry = False

                try:
                    opener = self.__get_opener(is_ajax=is_json)
                    result = opener.open(url, data=data)
                    response = result.read()
                    result.close()
                    opener.close()
                except urllib2.HTTPError, e:
                    # If we're forbidden, authenticate, and retry
                    if auto_auth and e.code == 403:
                        self._authenticate()
                        retry = True
                    else:
                        raise

            try:
                logger.debug("HTTP response from %s: %s" % (url, response))
            except UnicodeDecodeError:
                logger.debug("HTTP response from %s: (Failed to decode response)" % url)

            if cached:
                self.cache[key] = response

        if is_json:
            return json.loads(response)
        return response
