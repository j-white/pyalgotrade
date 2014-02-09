__author__ = 'jwhite'

import unittest
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

from pyalgotrade.vtrader import VtraderBroker, VtraderClient
from pyalgotrade import broker
from pyalgotrade.broker import backtesting

from twisted.web import server, resource
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from threading import Thread
import uuid
from jinja2 import Environment
import datetime

class JSONResource(resource.Resource):
    isLeaf = True

    def __init__(self, check_auth_cookie=True):
        resource.Resource.__init__(self)
        self.check_auth_cookie = check_auth_cookie
        self.j2env = Environment()
        self.j2env.filters['format_currency'] = self.format_currency

    def format_currency(value):
        return "${:,.2f}".format(value)

    def getChild(self, name, request):
        print 'here'
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)

    def render_GET(self, request):
        self.check_auth(request)
        request.setHeader("content-type", "application/json")

    def render_POST(self, request):
        self.check_auth(request)
        request.setHeader("content-type", "application/json")

    def check_auth(self, request):
        if self.check_auth_cookie:
            pass

class PathResource(resource.Resource):
    isLeaf=False

    def getChild(self, name, request):
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)

class PortfolioPositions(JSONResource):
    JSON = """ {
                    "data": [
                        {%- for instrument, quantity in broker.getPositions().iteritems() %}
                        {%- if not loop.first -%},{%- endif -%}
                            {
                                "PortfolioId": "{{ portfolio_id }}",
                                "Symbol": "{{ instrument }}",
                                "Quantity": {
                                    "RawData": {{ quantity }},
                                    "FormattedData": "{{ quantity }}"
                                }
                            }
                        {% endfor %}
                    ],
                    "total": {{ broker.getPositions()|length }}
                }"""


    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    def render_POST(self, request):
        JSONResource.render_GET(self, request)
        response = self.j2env.from_string(self.JSON).render(portfolio_id=self.site.portfolio_id, broker=self.site.broker)
        return str(response)

class PortfolioStrategyPositions(JSONResource):
    JSON = """ {
                    "data": [
                        {%- for key, value in portfolios.iteritems() %}
                        {%- if not loop.first -%},{%- endif -%}
                            {
                                "StrategyType": 0,
                                "Groups": null,
                                "Details": [
                                    {
                                        "PortfolioId": "{{ value }}",
                                        "PortfolioName": "{{ key }}"
                                    }
                                ]
                            }
                        {% endfor %}
                    ],
                    "total": {{ portfolios.keys()|length }}
                }"""

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    def render_GET(self, request):
        JSONResource.render_GET(self, request)
        portfolios = {self.site.portfolio_name : self.site.portfolio_id}
        response = self.j2env.from_string(self.JSON).render(portfolios=portfolios)
        return str(response)

class DashboardAccountBalance(JSONResource):
    JSON = """ {
                "PortfolioId": "{{ portfolio_id }}",
                "AccountValue": {
                    "RawData": 197378.75,
                    "FormattedData": "$197,378.75"
                },
                "CurrentPositionValue": {
                    "RawData": -11301.36,
                    "FormattedData": "-$11,301.36"
                },
                "MoneyMarketCashValue": {
                    "RawData": {{ '%.2f' | format(broker.getCash()) }},
                    "FormattedData": "{{ broker.getCash() }}"
                },
                "StockBuyingPower": {
                    "RawData": 24510.77,
                    "FormattedData": "$24,510.77"
                },
                "OptionBuyingPower": {
                    "RawData": 24510.77,
                    "FormattedData": "$24,510.77"
                },
                "TotalOutstandingOrdersValue": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
                },
                "OutstandingBuyOrdersValue": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
                },
                "OutstandingSellOrdersValue": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
                }
            }"""

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    def render_POST(self, request):
        portfolio_id = request.args['portfolioId'][0]
        if portfolio_id.lower() != self.site.portfolio_id.lower():
            raise Exception("Invalid portfolio id " + portfolio_id)

        JSONResource.render_GET(self, request)
        response = self.j2env.from_string(self.JSON).render(portfolio_id=portfolio_id, broker=self.site.broker)
        return str(response)

class PortfolioOrdersAndTransactions(JSONResource):
    JSON = """ {
                "data": [
                    {%- for order in orders %}
                    {%- if not loop.first -%},{%- endif -%}
                        {%- set execInfo = order.getExecutionInfo() if order.getExecutionInfo() else execInfo -%}
                        {
                            "Id": "{{ order.getId() }}",
                            "PortfolioId": "{{ portfolio_id }}",
                            "TransactionTime": "/Date(1391832375808)/",
                            "IsOpenOrder": {{ order.isActive()|lower }},
                            "IsPartialOrder": {{ order.isPartiallyFilled()|lower }},
                            "IsAbortedOrder": {{ order.isCanceled()|lower }},
                            "AbortedMessage": null,
                            "IsStrategy": false,
                            "KeySymbol": "ca;{{ order.getInstrument() }}",
                            "Symbol": "{{ order.getInstrument()}}",
                            "Exchange": "TSX",
                            "UnderlyingSymbol": "",
                            "UnderlyingExchange": "",
                            "Description": "{{ order.getInstrument() }}",
                            "Last": "10.86",
                            "Bid": "10.85",
                            "Ask": "10.87",
                            "OrderStatus": "Pending New",
                            "OrderType": "Market",
                            "Side": "Buy",
                            "PositionEffect": "",
                            "TotalQuantity": "{{ order.getQuantity() }}",
                            "CumulativeQuantity": "{{ execInfo.getQuantity() }}",
                            "CumulativeQuantityAveragePrice": "{{ execInfo.getPrice() / execInfo.getQuantity() }}",
                            "RemainingQuantity": "{{ order.getQuantity() - execInfo.getQuantity() }}",
                            "PriceLimit": null,
                            "StopPrice": null,
                            "TimeInForce": "Day"
                        }
                    {% endfor %}
                ],
                "total": {{ orders|length }}
            }"""

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    def render_POST(self, request):
        portfolio_id = request.args['portfolioId'][0]
        if portfolio_id.lower() != self.site.portfolio_id.lower():
            raise Exception("Invalid portfolio id " + portfolio_id)
        number_of_orders_to_show = int(request.args['nbOrdersShow'][0])
        if number_of_orders_to_show <= 0:
            raise Exception("Invalid nbOrdersShow %d" % number_of_orders_to_show)

        last_n_orders = self.site.getOrders()[-number_of_orders_to_show:]
        blankExecutionInfo = broker.OrderExecutionInfo(0, 1, 0, datetime.datetime.now())

        JSONResource.render_GET(self, request)
        response = self.j2env.from_string(self.JSON).render(portfolio_id=portfolio_id, broker=self.site.broker,
                                                            orders=last_n_orders, execInfo = blankExecutionInfo)
        return str(response)

class OrderCreate(resource.Resource):
    isLeaf = True

    def __init__(self, site):
        resource.Resource.__init__(self)
        self.site = site

    def render_POST(self, request):
        instrument = request.args['OrderLegs[0].DisplaySymbol'][0]
        vtrader_action = int(request.args['OrderLegs[0].Action'][0])
        quantity = int(request.args['OrderLegs[0].Quantity'][0])
        type = request.args['OrderType'][0]

        pyalgo_action = broker.Order.Action.BUY
        if vtrader_action == VtraderClient.Action.BUY_STOCK:
            pyalgo_action = broker.Order.Action.BUY
        elif vtrader_action == VtraderClient.Action.SELL_STOCK:
            pyalgo_action = broker.Order.Action.SELL

        if type == 'Market':
            order = self.site.broker.createMarketOrder(pyalgo_action, instrument, quantity)
            self.site.placeOrder(order)

        return "Your order has been submitted"

class VtraderBrokerSite(server.Site):
    def __init__(self, portfolio, broker):
        self.portfolio_name = portfolio
        self.portfolio_id = str(uuid.uuid1())
        self.broker = broker

        # Register callbacks
        self.broker.getOrderUpdatedEvent().subscribe(self.onOrderUpdated)

        # Used to keep track of the orders state
        self.__orders = []

        self.root = self.get_root()
        server.Site.__init__(self, self.root)

    def placeOrder(self, order):
        self.__orders.append(order)
        self.broker.placeOrder(order)

    def getOrders(self):
        return self.__orders

    def get_root(self):
        # /
        root = PathResource()

        # /VirtualTrader
        virtualtrader = PathResource()
        root.putChild('VirtualTrader', virtualtrader)

        # /VirtualTrader/Portfolio
        portfolio = PathResource()
        virtualtrader.putChild('Portfolio', portfolio)

        # /VirtualTrader/Portfolio/PortfolioStrategyPositions_AjaxGrid
        portfolio_positions = PortfolioPositions(self)
        portfolio.putChild('PortfolioPositions_AjaxGrid', portfolio_positions)

        # /VirtualTrader/Portfolio/PortfolioStrategyPositions_AjaxGrid
        portfolio_strategy_positions = PortfolioStrategyPositions(self)
        portfolio.putChild('PortfolioStrategyPositions_AjaxGrid', portfolio_strategy_positions)

        # /VirtualTrader/AccountBalance
        account_balance = PathResource()
        virtualtrader.putChild('AccountBalance', account_balance)

        # /VirtualTrader/AccountBalance/GetDashboardAccountBalance
        get_dashboard_account_balance = DashboardAccountBalance(self)
        account_balance.putChild('GetDashboardAccountBalance', get_dashboard_account_balance)

        # /VirtualTrader/Order
        order = PathResource()
        virtualtrader.putChild('Order', order)

        # /VirtualTrader/Order/Create
        order_create = OrderCreate(self)
        order.putChild('Create', order_create)

        # /VirtualTrader/Order/PortfolioOrdersAndTransactions_AjaxGrid
        portfolio_orders_and_transactions = PortfolioOrdersAndTransactions(self)
        order.putChild('PortfolioOrdersAndTransactions_AjaxGrid', portfolio_orders_and_transactions)

        return root

    def onOrderUpdated(self, broker_, order):
        pass

class MockVtraderServerTestCase(unittest.TestCase):
    TestInstrument = "bb"
    PortfolioName = "test"

    def runReactor(self):
        try:
            reactor.run(False)
        except ReactorAlreadyRunning:
            pass

    @classmethod
    def tearDownClass(cls):
        reactor.callFromThread(reactor.stop)

    def get_brokers(self, cash, barFeed):
        """ Returns both a VirtualTraderBroker and a BacktestingBroker.
            The VirtualTraderBroker interfaces with a mock webservice that is backed
            by the BacktestingBroker.
        """
        # Create a backtesting broker used to back the mock server
        commission = backtesting.FixedPerTrade(VtraderBroker.COMMISSION_PER_ORDER)
        backtest = backtesting.Broker(cash, barFeed, commission=commission)

        # Create a new site instance
        site = VtraderBrokerSite(self.PortfolioName, backtest)

        # Add the new site
        port = reactor.listenTCP(0, site)

        # Fire up the reactor
        Thread(target=self.runReactor).start()

        # Create a new broker pointing to the new site instance
        return VtraderBroker("test", "testuser", "testpass", "http://127.0.0.1:%d" % port.getHost().port), backtest
