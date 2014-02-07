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
import re
import os
from datetime import datetime

from pyalgotrade import broker

class OrderFailed(Exception):
    pass

class PortfolioNotFound(Exception):
    pass

class VtraderClient():
    home = os.path.join(os.path.expanduser("~"), "pyalgotrader")
    cache_timeout = 30

    class Action:
        BUY_STOCK		        = 0
        SELL_STOCK              = 1
        SELL_STOCK_SHORT		= 2
        BUY_OPTION              = 3
        BUY_OPTION_TO_CLOSE     = 4
        SELL_OPTION             = 5
        SELL_OPTION_TO_CLOSE    = 6

    def __init__(self, portfolio, username, password, url):
        self.base_url = url
        self.username = username
        self.password = password
        self.cookie_file = self._get_cookie_file()

        # Create the working directory if not already present
        if not os.path.exists(self.home):
            os.makedirs(self.home)

        # And fire up the cookie jar
        self.cj = cookielib.MozillaCookieJar(self.cookie_file)
        try:
            self.cj.load(ignore_discard=True)
        except IOError:
            pass

        self.portfolio_name = portfolio
        self.portfolio_id = self._get_portfolio_id()

    def _get_cookie_file(self):
        """Returns the filename used to store the cookies which is unique for every username/url pair."""
        # Hash the URL instead of storing the path
        m = hashlib.md5()
        m.update(self.base_url)
        return os.path.join(self.home, "vtrader-%s-%s-cookies.txt" % (self.username, m.hexdigest()))

    def _get_portfolio_id(self):
        url = "%s/VirtualTrader/Portfolio/PortfolioStrategyPositions_AjaxGrid" % self.base_url
        response = self.__get_response_data(url, is_json=True)

        for data in response['data']:
            for details in data['Details']:
                portfolio_name = details['PortfolioName']
                portfolio_id = details['PortfolioId']
                if portfolio_name.lower() == self.portfolio_name.lower():
                    return portfolio_id

        raise PortfolioNotFound()

    def get_cash_value(self):
        account_balance = self._get_account_balance()
        return float(account_balance['MoneyMarketCashValue']['RawData'])

    def place_order(self, order):
        url = "%s/VirtualTrader/Order/Create" % self.base_url
        data = {
            'Duration': 'Day',
            'Limit': '',
            'PortfolioId': self.portfolio_id,
            'OrderType': 'Market',
            'Status': '',
            'Stop': '',
            'KeySymbol': self.__get_key(order.getInstrument()),
            'IsFutureTrade': False,
            'IsIndexOrCurrencyOptionTrade': False,
            'X-Requested-With': 'XMLHttpRequest',
        }

        # We should repeat this for every leg in the spread, but we're only dealing with simple orders
        leg_index = 0
        action = self.__get_action(order)
        instrument_type = self.__get_instrument_type(order.getInstrument())
        if instrument_type == self.InstrumentType.STOCK:
            data.update(self.__get_stock_leg(leg_index, action, order))
        else:
            raise Exception("Option orders are not yet supported.")
            #data.update(self.__get_option_leg(leg_index, order))

        data = urllib.urlencode(data)
        response = self.__get_response_data(url, data, use_cache=False)
        if not 'Your order has been submitted' in response:
            raise OrderFailed("Received invalid response: %s" % response)

    def __get_action(self, order):
        """ Maps the order action to the proper Vtrader action code. """
        action = None
        instrument_type = self.__get_instrument_type(order.getInstrument())
        if instrument_type == self.InstrumentType.STOCK:
            if order.getAction() == broker.Order.Action.BUY:
                action = self.Action.BUY_STOCK
            elif order.getAction() == broker.Order.Action.SELL:
                action = self.Action.SELL_STOCK
            elif order.getAction() == broker.Order.Action.SELL_SHORT:
                action = self.Action.SELL_STOCK_SHORT
        elif instrument_type == self.InstrumentType.CALL_OPTION or instrument_type == self.InstrumentType.PUT_OPTION:
            if order.getAction() == broker.Order.Action.BUY:
                action = self.Action.BUY_OPTION
            if order.getAction() == broker.Order.Action.BUY_TO_COVER:
                action = self.Action.BUY_OPTION_TO_CLOSE
            elif order.getAction() == broker.Order.Action.SELL:
                action = self.Action.SELL_OPTION_TO_CLOSE
            elif order.getAction() == broker.Order.Action.SELL_SHORT:
                action = self.Action.SELL_OPTION

        if action is None:
            raise Exception("Invalid instrument and action combination.")

        return action

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

    def get_account_value(self):
        return self.get_cash_value() + self.get_position_value()

    def get_position_value(self):
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

    # def get_open_spreads(self):
    #     spreads = []
    #     transaction_rows = self._get_portfolio_transaction_history()['data']
    #     position_rows = self._get_portfolio_positions()['data']
    #     for position_row in position_rows:
    #         symbol = position_row['Symbol']
    #         is_option = bool(position_row['IsOption'])
    #         quantity = int(position_row['Quantity']['RawData'])
    #
    #         time_of_transaction = None
    #         for transaction_row in transaction_rows:
    #             if 'Filled' != transaction_row['OrderStatus']:
    #                 continue
    #
    #             if symbol != transaction_row['Symbol']:
    #                 continue
    #
    #             transaction_time = transaction_row['TransactionTime']
    #             transaction_timestamp = re.match('.*?\(([0-9]+)', transaction_time).group(1)
    #             time_of_transaction = datetime.fromtimestamp(float(transaction_timestamp)/1000)
    #             break
    #
    #         if time_of_transaction is None:
    #             continue
    #
    #         if not is_option:
    #             continue
    #
    #         option = StockOption.objects.get(symbol=symbol)
    #         if quantity > 0:
    #             spread = LongOption(option, time_of_transaction.date())
    #             spread.scale(abs(quantity))
    #             spreads.append(spread)
    #         elif quantity < 0:
    #             spread = ShortOption(option, time_of_transaction.date())
    #             spread.scale(abs(quantity))
    #             spreads.append(spread)
    #     return spreads

    # def open_spread(self, spread):
    #     self._create_spread_order(spread, 1)
    #
    # def close_spread(self, spread):
    #     self._create_spread_order(spread, 0)
    #
    # def close_all_spreads(self):
    #     open_spreads = self.get_open_spreads()
    #     for spread in open_spreads:
    #         self.close_spread(spread)

    def get_num_open_orders(self):
        open_orders = self._get_open_orders()
        return int(open_orders['total'])

    def _authenticate(self):
        url = "%s/Authentication" % self.base_url
        data = urllib.urlencode({
            'Login.UserName': self.username,
            'Login.Password': self.password,
            'Login.RememberMe': False,
            })
        self.__get_response_data(url, data, use_cache=False)
        self.cj.save(ignore_discard=True)

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

    def _get_available_stocks(self):
        stocks = {}

        terms = [c for c in string.lowercase]
        terms.extend(['%d' % i for i in range(0, 10)])

        for term in terms:
            url = "%s/VirtualTrader/Search/Stock?term=%s" % (self.base_url, term)
            list_of_stocks = self.__get_response_data(url, is_json=True)
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

    # def _create_spread_order(self, spread, open_flag):
    #     stock = Stock.objects.get(symbol=spread.underlying_symbol)
    #     url = "%s/VirtualTrader/Order/Create" % self.base_url
    #     data = {
    #         'Duration': 'Day',
    #         'Limit': '',
    #         'PortfolioId': self.portfolio_id,
    #         'OrderType': 'Market',
    #         'Status': '',
    #         'Stop': '',
    #         'KeySymbol': self.__get_key(stock),
    #         'IsFutureTrade': False,
    #         'IsIndexOrCurrencyOptionTrade': False,
    #         'X-Requested-With': 'XMLHttpRequest',
    #     }
    #     i = -1
    #     for leg in spread.legs:
    #         i += 1
    #         action = self.__get_action(spread, leg, open_flag)
    #         if isinstance(leg.instrument, Stock):
    #             data.update(self.__get_stock_leg(i, leg.instrument, action, leg.quantity))
    #         else:
    #             data.update(self.__get_option_leg(i, leg.instrument, action, leg.quantity))
    #     data = urllib.urlencode(data)
    #
    #     response = self.__get_response_data(url, data, use_cache=False)
    #     if not 'Your order has been submitted' in response:
    #         raise OrderFailed("Received invalid response: %s" % response)

    # def __get_action(self, spread, leg, open_flag):
    #     if open_flag:
    #         # We're opening a new position
    #         if isinstance(leg.instrument, Stock):
    #             # We're opening a position in the stock
    #             if leg.position == Position.Long:
    #                 return self.Action.BUY_STOCK
    #             else:
    #                 return self.Action.SELL_STOCK_SHORT
    #         else:
    #             # We're opening a position in the option
    #             if leg.position == Position.Long:
    #                 return self.Action.BUY_OPTION
    #             else:
    #                 return self.Action.SELL_OPTION
    #     else:
    #         # We're closing an existing position
    #         if isinstance(leg.instrument, Stock):
    #             # We're closing a position in the stock
    #             if leg.position == Position.Long:
    #                 return self.Action.SELL_STOCK
    #             else:
    #                 return self.Action.BUY_STOCK
    #         else:
    #             # We're closing a position in the option
    #             if leg.position == Position.Long:
    #                 return self.Action.SELL_OPTION_TO_CLOSE
    #             else:
    #                 return self.Action.BUY_OPTION_TO_CLOSE

    # def __get_stock_leg(self, id, stock, action, qty):
    #     leg_options = {
    #         'Action': action,
    #         'Quantity': int(qty),
    #         'DisplaySymbol': stock.symbol,
    #         'KeySymbol': self.__get_key(stock),
    #         'Exchange': 'TSX',
    #         'UnderlyingSymbol': stock.symbol,
    #         'UnderlyingKeySymbol': self.__get_key(stock),
    #         'UnderlyingExchange': 'TSX',
    #         'AssetType': 'Stock',
    #         'CFICode': 'ESXXXX',
    #         'Expiration': '',
    #         'Strike': '',
    #         'CallPutIndicator': '',
    #     }
    #
    #     leg = {}
    #     for option in leg_options.keys():
    #         leg['OrderLegs[%d].%s' % (id, option)] = leg_options[option]
    #     return leg

    # def __get_option_leg(self, id, option, action, qty):
    #     leg_options = {
    #         'Action': action,
    #         'Quantity': int(qty),
    #         'DisplaySymbol': option.stock.symbol,
    #         'KeySymbol': self.__get_key(option),
    #         'Exchange': 'MX',
    #         'UnderlyingSymbol': option.stock.symbol,
    #         'UnderlyingKeySymbol': self.__get_key(option.stock),
    #         'UnderlyingExchange': 'TSX',
    #         'AssetType': 'Option',
    #         'CFICode': 'OXXXXX',
    #         'Expiration': option.expiry.strftime('%y|%m|%d'),
    #         'Strike': option.strike,
    #         'CallPutIndicator': 1 if option.type == StockOption.CALL else 2,
    #     }
    #
    #     leg = {}
    #     for option in leg_options.keys():
    #         leg['OrderLegs[%d].%s' % (id, option)] = leg_options[option]
    #     return leg


    class InstrumentType(object):
        STOCK = 1
        CALL_OPTION = 2
        PUT_OPTION = 3

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

    def __get_response_data(self, url, data=None, is_json=False, use_cache=True, verbose=False):
        response = None
        key = None
        # if use_cache:
        #     # Hash the URL and data
        #     m = hashlib.sha256()
        #     m.update(url)
        #     m.update(str(data))
        #
        #     # Cache lookup
        #     key = "vtrader-%s" % m.hexdigest()
        #     response = cache.get(key)

        if not response:
            if verbose:
                print "URL: %s" % url
                print "Data: %s" % data

            retries = 0
            while retries >= 0:
                retries -= 1

                try:
                    opener = self.__get_opener(is_ajax=is_json)
                    result = opener.open(url, data=data)
                    response = result.read()
                    result.close()
                    opener.close()
                except urllib2.HTTPError, e:
                    # If we're forbidden, authenticate, and retry
                    if e.code == 403:
                        self._authenticate()
                        retries += 1
                    else:
                        raise

            if verbose:
                try:
                    print "URL: %s, Response: %s" % (url, response)
                except UnicodeDecodeError:
                    print "URL: %s (Failed to decode response)" % url

            # if use_cache:
            #     cache.set(key, response, timeout=self.cache_timeout)

        if is_json:
            return json.loads(response)
        return response
