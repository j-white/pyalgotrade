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

from pyalgotrade.vtrader import VtraderClient
from pyalgotrade import broker

from twisted.web import server, resource
import uuid
from jinja2 import Environment

import time
import datetime

def isAuthenticated(request):
    return request.getCookie("_auth") is not None

def authenticated():
    def wrap(f):
        def wrapped_f(self, request):
            if not isAuthenticated(request):
                msg = "Client not authenticated"
                request.setResponseCode(403, msg)
                return msg
            return f(self, request)
        return wrapped_f
    return wrap

class JSONResource(resource.Resource):
    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)
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
        request.setHeader("content-type", "application/json")

    def render_POST(self, request):
        request.setHeader("content-type", "application/json")

class HTMLResource(JSONResource):
    def render_GET(self, request):
        request.setHeader("content-type", "text/html")

    def render_POST(self, request):
        request.setHeader("content-type", "text/html")

class PathResource(resource.Resource):
    isLeaf=False

    def getChild(self, name, request):
        if name == '':
            return self
        return resource.Resource.getChild(self, name, request)

class Authentication(HTMLResource):
    def __init__(self, site):
        HTMLResource.__init__(self)
        self.site = site

    def render_POST(self, request):
        HTMLResource.render_GET(self, request)

        username = request.args['Login.UserName'][0]
        password = request.args['Login.Password'][0]
        remember = bool(request.args['Login.RememberMe'][0])

        if username == self.site.username and password == self.site.password:
            request.addCookie('_auth', '%s:%s:%s' % (username, password, remember))
        else:
             request.setResponseCode(403)

        return ""

class PortfolioPositions(JSONResource):
    JSON = """ {
                    "data": [
                        {%- for instrument, quantity in broker.getPositions().iteritems() %}
                        {%- if not loop.first -%},{%- endif -%}
                            {
                                "PortfolioId": "{{ portfolio_id }}",
                                "Symbol": "{{ instrument }}",
                                "IsOption": false,
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

    @authenticated()
    def render_POST(self, request):
        JSONResource.render_GET(self, request)
        response = self.j2env.from_string(self.JSON).render(portfolio_id=self.site.portfolio_id, broker=self.site.broker)
        return str(response)

class PortfolioQuotes(JSONResource):
    JSON = """ {
                    "data": [
                        {
                            "RowId": "ed35e204-60b4-4414-a52d-0c0424553b46",
                            "PortfolioId": "{{ portfolio_id }}",
                            "IsSymbolValid": true,
                            "IsOption": false,
                            "HasStockGuideProfile": true,
                            "KeySymbol": "ca;VRX",
                            "Quantity": {
                                "RawData": -96,
                                "FormattedData": "-96"
                            },
                            "Symbol": "VRX",
                            "Exchange": "TSX",
                            "Last": {
                                "RawData": 114.91,
                                "FormattedData": "114.91"
                            },
                            "Change": {
                                "RawData": 1.53,
                                "FormattedData": "1.53"
                            },
                            "Volume": {
                                "RawData": 513521,
                                "FormattedData": "513,521"
                            },
                            "DayLowHigh": {
                                "RawData": 113.82,
                                "FormattedData": "113.82"
                            },
                            "YearLowHigh": {
                                "RawData": 50.904315,
                                "FormattedData": "50.904315"
                            },
                            "Bid": {
                                "RawData": 114.82,
                                "FormattedData": "114.82"
                            },
                            "Ask": {
                                "RawData": 115.11,
                                "FormattedData": "115.11"
                            }
                        }
                    ],
                    "total": 1
                }"""

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    @authenticated()
    def render_POST(self, request):
        JSONResource.render_GET(self, request)
        page = int(request.args['page'][0])
        orderBy = request.args['orderBy'][0]
        response = self.j2env.from_string(self.JSON).render(portfolio_id=self.site.portfolio_id, broker=self.site.broker)
        return str(response)

class PortfolioDashboard(HTMLResource):
    UNAUTHENTICATED_HTML = """
    <td>
      <div>
        <input id="Login_UserName" name="Login.UserName" type="text" value="" />
      </div>
      <div>
        <input id="Login_Password" name="Login.Password" type="password" />
      </div>
    </td>
    """

    AUTHENTICATED_HTML = """
    <div>
     <ul>
      {%- for pname, pid in portfolios.iteritems() %}
      {%- if loop.first -%}
      <li class="t-item t-state-default t-state-active" pid="{{ pid }}"><a class="t-link" href="#PortfoliosTabStrip-1">{{ pname }}</a></li>
      {%- else -%}
      <li class="t-item t-state-default" pid="{{ pid }}"><a class="t-link" href="/VirtualTrader/Portfolio/PortfolioDashboard/{{ pid }}">{{ pname }}</a></li>
      {%- endif -%}
      {% endfor %}
     </ul>
    </div>
    """

    def __init__(self, site):
        HTMLResource.__init__(self)
        self.site = site

    def render_GET(self, request):
        HTMLResource.render_GET(self, request)

        template = self.AUTHENTICATED_HTML if isAuthenticated(request) else self.UNAUTHENTICATED_HTML

        portfolios = {self.site.portfolio_name : self.site.portfolio_id}
        response = self.j2env.from_string(template).render(portfolios=portfolios)
        return str(response)

class DashboardAccountBalance(JSONResource):
    JSON = """ {
                "PortfolioId": "{{ portfolio_id }}",
                "AccountValue": {
                    "RawData": {{ '%.2f' | format(broker.getEquity()) }},
                    "FormattedData": "{{ broker.getEquity() }}"
                },
                "CurrentPositionValue": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
                },
                "MoneyMarketCashValue": {
                    "RawData": {{ '%.2f' | format(broker.getCash()) }},
                    "FormattedData": "{{ broker.getCash() }}"
                },
                "StockBuyingPower": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
                },
                "OptionBuyingPower": {
                    "RawData": 0,
                    "FormattedData": "$0.00"
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

    @authenticated()
    def render_POST(self, request):
        portfolio_id = request.args['portfolioId'][0]
        if portfolio_id.lower() != self.site.portfolio_id.lower():
            raise Exception("Invalid portfolio id " + portfolio_id)

        JSONResource.render_POST(self, request)
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
                            "TransactionTime": "/Date({{ order.timestamp }})/",
                            "IsOpenOrder": {{ order.isActive()|lower }},
                            "IsPartialOrder": {{ order.isPartiallyFilled()|lower }},
                            "IsAbortedOrder": {{ order.isCanceled()|lower }},
                            "AbortedMessage": null,
                            "KeySymbol": "ca;{{ order.getInstrument() }}",
                            "Symbol": "{{ order.getInstrument() }}",
                            "Description": "{{ order.getInstrument() }}",
                            "OrderType": "{{ order_to_type[order.getId()] }}",
                            "TotalQuantity": "{{ order.getQuantity() }}",
                            "CumulativeQuantity": "{{ order.getFilled() }}",
                            "CumulativeQuantityAveragePrice": "{{ order.getAvgFillPrice()|default('0.0', true) }}",
                            "RemainingQuantity": "{{ order.getRemaining() }}",
                            "PriceLimit": null,
                            "StopPrice": null
                        }
                    {% endfor %}
                ],
                "total": {{ orders|length }}
            }"""

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    @authenticated()
    def render_POST(self, request):
        portfolio_id = request.args['portfolioId'][0]
        if portfolio_id.lower() != self.site.portfolio_id.lower():
            raise Exception("Invalid portfolio id " + portfolio_id)
        number_of_orders_to_show = int(request.args['nbOrdersShow'][0])
        if number_of_orders_to_show <= 0:
            raise Exception("Invalid nbOrdersShow %d" % number_of_orders_to_show)

        last_n_orders = self.site.getOrders()[-number_of_orders_to_show:]
        blankExecutionInfo = broker.OrderExecutionInfo(0, 1, 0, datetime.datetime.now())

        order_to_type = {}
        for order in last_n_orders:
            order_to_type[order.getId()] = VtraderClient.ALGO_TO_VTRADER_ORDER_TYPE[order.getType()]

        JSONResource.render_POST(self, request)
        response = self.j2env.from_string(self.JSON).render(portfolio_id=portfolio_id, broker=self.site.broker,
                                                            orders=last_n_orders, order_to_type=order_to_type,
                                                            execInfo = blankExecutionInfo)
        return str(response)

class OrderCreate(HTMLResource):
    isLeaf = True

    def __init__(self, site):
        HTMLResource.__init__(self)
        self.site = site

    @authenticated()
    def render_POST(self, request):
        instrument = request.args['OrderLegs[0].DisplaySymbol'][0]
        duration = request.args['Duration'][0]
        vtrader_action = int(request.args['OrderLegs[0].Action'][0])
        quantity = int(request.args['OrderLegs[0].Quantity'][0])
        type = VtraderClient.VTRADER_TO_ALGO_ORDER_TYPE[request.args['OrderType'][0]]

        pyalgo_action = broker.Order.Action.BUY
        if vtrader_action == VtraderClient.Action.BUY_STOCK:
            pyalgo_action = broker.Order.Action.BUY
        elif vtrader_action == VtraderClient.Action.SELL_STOCK:
            pyalgo_action = broker.Order.Action.SELL
        elif vtrader_action == VtraderClient.Action.SELL_STOCK_SHORT:
            pyalgo_action = broker.Order.Action.SELL_SHORT

        # Parse the stop and limit fields, catch the exception since
        # these won't always be set
        try:
            limit = float(request.args['Limit'][0])
        except ValueError:
            limit = None

        try:
            stop = float(request.args['Stop'][0])
        except ValueError:
            stop = None

        good_till_canceled = False
        if duration in ['1', 'GoodTillCanceled']:
            good_till_canceled = True

        if type == broker.Order.Type.MARKET:
            order = self.site.broker.createMarketOrder(pyalgo_action, instrument, quantity)
        elif type == broker.Order.Type.LIMIT:
            order = self.site.broker.createLimitOrder(pyalgo_action, instrument, limit, quantity)
        elif type == broker.Order.Type.STOP:
            order = self.site.broker.createStopOrder(pyalgo_action, instrument, stop, quantity)
        elif type == broker.Order.Type.STOP_LIMIT:
            order = self.site.broker.createStopLimitOrder(pyalgo_action, instrument, stop, limit, quantity)
        else:
            raise Exception("Invalid order type")

        if good_till_canceled:
            order.setGoodTillCanceled(True)

        self.site.placeOrder(order)

        HTMLResource.render_POST(self, request)
        return "Your order has been submitted"

class OrderCancel(JSONResource):
    isLeaf = True

    def __init__(self, site):
        JSONResource.__init__(self)
        self.site = site

    @authenticated()
    def render_POST(self, request):
        order_id = request.args['orderId'][0]
        portfolio_id = request.args['portfolioId'][0]

        order = self.site.getOrder(order_id)
        if order is None:
            raise Exception("Order %s is not active" % order_id)

        self.site.broker.cancelOrder(order)
        JSONResource.render_POST(self, request)
        return "{\"success\":true}"

class VtraderBrokerSite(server.Site):
    def __init__(self, username, password, portfolio, broker):
        self.username = username
        self.password = password
        self.portfolio_name = portfolio
        self.portfolio_id = str(uuid.uuid1())
        self.broker = broker

        # Used to keep track of all orders that have been placed (active or not)
        self.__orders = []

        self.root = self.getRoot()
        server.Site.__init__(self, self.root)

    def placeOrder(self, order):
        order.timestamp = time.time()
        self.__orders.append(order)
        self.broker.placeOrder(order)

    def getOrder(self, order_id):
        for order in self.__orders:
            if str(order.getId()) == str(order_id):
                return order
        return None

    def getOrders(self):
        return self.__orders

    def getRoot(self):
        # /
        root = PathResource()

        # /Authentication
        authentication = Authentication(self)
        root.putChild('Authentication', authentication)

        # /VirtualTrader
        virtualtrader = PathResource()
        root.putChild('VirtualTrader', virtualtrader)

        # /VirtualTrader/Portfolio
        portfolio = PathResource()
        virtualtrader.putChild('Portfolio', portfolio)

        # /VirtualTrader/Portfolio/Dashboard
        portfolio_dashboard = PortfolioDashboard(self)
        portfolio.putChild('Dashboard', portfolio_dashboard)

        # /VirtualTrader/Portfolio/PortfolioPositions_AjaxGrid
        portfolio_positions = PortfolioPositions(self)
        portfolio.putChild('PortfolioPositions_AjaxGrid', portfolio_positions)

        # /VirtualTrader/Portfolio/PortfolioQuotes_AjaxGrid
        portfolio_quotes = PortfolioQuotes(self)
        portfolio.putChild('PortfolioQuotes_AjaxGrid', portfolio_quotes)

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

        # /VirtualTrader/Order/CancelOrder
        order_cancel = OrderCancel(self)
        order.putChild('CancelOrder', order_cancel)

        # /VirtualTrader/Order/PortfolioOrdersAndTransactions_AjaxGrid
        portfolio_orders_and_transactions = PortfolioOrdersAndTransactions(self)
        order.putChild('PortfolioOrdersAndTransactions_AjaxGrid', portfolio_orders_and_transactions)

        return root
