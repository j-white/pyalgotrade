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

import datetime

from pyalgotrade import bar
from pyalgotrade import broker
from pyalgotrade import barfeed
from pyalgotrade.vtrader.broker import VtraderBroker

from mock_vtrader_server import MockVtraderServerTestCase

class BarsBuilder(object):
    def __init__(self, instrument, frequency):
        self.__instrument = instrument
        self.__frequency = frequency
        self.__nextDateTime = datetime.datetime(2011, 1, 1)
        if frequency == bar.Frequency.TRADE:
            self.__delta = datetime.timedelta(milliseconds=1)
        elif frequency == bar.Frequency.SECOND:
            self.__delta = datetime.timedelta(seconds=1)
        elif frequency == bar.Frequency.MINUTE:
            self.__delta = datetime.timedelta(minutes=1)
        elif frequency == bar.Frequency.HOUR:
            self.__delta = datetime.timedelta(hours=1)
        elif frequency == bar.Frequency.DAY:
            self.__delta = datetime.timedelta(days=1)
        else:
            raise Exception("Invalid frequency")

    def advance(self, sessionClose):
        if sessionClose:
            self.__nextDateTime = datetime.datetime(self.__nextDateTime.year, self.__nextDateTime.month, self.__nextDateTime.day)
            self.__nextDateTime += datetime.timedelta(days=1)
        else:
            self.__nextDateTime += self.__delta

    def nextBars(self, openPrice, highPrice, lowPrice, closePrice, volume=None, sessionClose=False):
        if volume is None:
            volume = closePrice*10
        bar_ = bar.BasicBar(self.__nextDateTime, openPrice, highPrice, lowPrice, closePrice, volume, closePrice, self.__frequency)
        bar_.setSessionClose(sessionClose)
        ret = {self.__instrument : bar_}
        self.advance(sessionClose)
        return bar.Bars(ret)

    def nextTuple(self, openPrice, highPrice, lowPrice, closePrice, volume=None, sessionClose=False):
        ret = self.nextBars(openPrice, highPrice, lowPrice, closePrice, volume, sessionClose)
        return (ret.getDateTime(), ret)

class Callback:
    def __init__(self):
        self.eventCount = 0

    def onOrderUpdated(self, broker_, order):
        self.eventCount += 1

class MarketOrderTestCase(MockVtraderServerTestCase):
    def testBuyAndSell(self):
        vtrader, backtest = self.get_brokers(100, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
        barsBuilder = BarsBuilder(MockVtraderServerTestCase.TestInstrument, bar.Frequency.MINUTE)

        # Buy
        cb = Callback()
        vtrader.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        self.assertEqual(vtrader.getCash(), 100)
        order = vtrader.createMarketOrder(broker.Order.Action.BUY, MockVtraderServerTestCase.TestInstrument, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        vtrader.placeOrder(order)
        backtest.onBars(*barsBuilder.nextTuple(10, 15, 8, 12))
        vtrader.updateActiveOrders()
        self.assertTrue(order.isFilled())
        self.assertEqual(order.getExecutionInfo().getPrice(), 10)
        self.assertEqual(order.getExecutionInfo().getCommission(), VtraderBroker.COMMISSION_PER_ORDER)
        self.assertEqual(len(vtrader.getActiveOrders()), 0)
        self.assertEqual(vtrader.getCash(), 100 - 10 - VtraderBroker.COMMISSION_PER_ORDER)
        self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 1)
        self.assertEqual(cb.eventCount, 2)
        self.assertEqual(order.getFilled(), 1)
        self.assertEqual(order.getRemaining(), 0)

        # Sell
        cb = Callback()
        vtrader.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        order = vtrader.createMarketOrder(broker.Order.Action.SELL, MockVtraderServerTestCase.TestInstrument, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        vtrader.placeOrder(order)
        backtest.onBars(*barsBuilder.nextTuple(10, 15, 8, 12))
        vtrader.updateActiveOrders()
        self.assertTrue(order.isFilled())
        self.assertEqual(order.getExecutionInfo().getPrice(), 10)
        self.assertEqual(order.getExecutionInfo().getCommission(), VtraderBroker.COMMISSION_PER_ORDER)
        self.assertEqual(len(vtrader.getActiveOrders()), 0)
        self.assertEqual(vtrader.getCash(), 100 - 2 * VtraderBroker.COMMISSION_PER_ORDER)
        self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 0)
        self.assertEqual(cb.eventCount, 2)
        self.assertEqual(order.getFilled(), 1)
        self.assertEqual(order.getRemaining(), 0)

    def testFailToBuy(self):
        vtrader, backtest = self.get_brokers(5, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
        barsBuilder = BarsBuilder(MockVtraderServerTestCase.TestInstrument, bar.Frequency.MINUTE)

        order = vtrader.createMarketOrder(broker.Order.Action.BUY, MockVtraderServerTestCase.TestInstrument, 1)

        # Fail to buy. No money.
        cb = Callback()
        vtrader.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        vtrader.placeOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        backtest.onBars(*barsBuilder.nextTuple(10, 15, 8, 12))
        vtrader.updateActiveOrders()
        self.assertTrue(order.isAccepted())
        self.assertEqual(order.getExecutionInfo(), None)
        self.assertEqual(len(vtrader.getActiveOrders()), 1)
        self.assertEqual(vtrader.getCash(), 5)
        self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 0)
        self.assertEqual(cb.eventCount, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)

        # Fail to buy. No money. Canceled due to session close.
        cb = Callback()
        vtrader.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        backtest.onBars(*barsBuilder.nextTuple(11, 15, 8, 12, sessionClose=True))
        vtrader.updateActiveOrders()
        self.assertTrue(order.isCanceled())
        self.assertEqual(order.getExecutionInfo(), None)
        self.assertEqual(len(vtrader.getActiveOrders()), 0)
        self.assertEqual(vtrader.getCash(), 5)
        self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 0)
        self.assertEqual(cb.eventCount, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)

    # def testSellShort(self):
    #     vtrader, backtest = self.get_brokers(100, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
    #     barsBuilder = BarsBuilder(MockVtraderServerTestCase.TestInstrument, bar.Frequency.MINUTE)
    #
    #     # Buy 1
    #     order = vtrader.createMarketOrder(broker.Order.Action.BUY, MockVtraderServerTestCase.TestInstrument, 1)
    #     self.assertEqual(order.getFilled(), 0)
    #     self.assertEqual(order.getRemaining(), 1)
    #     vtrader.placeOrder(order)
    #     backtest.onBars(*barsBuilder.nextTuple(100, 100, 100, 100))
    #     vtrader.updateActiveOrders()
    #     self.assertEqual(order.getFilled(), 1)
    #     self.assertEqual(order.getRemaining(), 0)
    #     self.assertTrue(order.isFilled())
    #     self.assertEqual(order.getExecutionInfo().getCommission(),  VtraderBroker.COMMISSION_PER_ORDER)
    #     self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 1)
    #     self.assertEqual(vtrader.getCash(), 0)
    #
    #     # Sell 2
    #     order = vtrader.createMarketOrder(broker.Order.Action.SELL_SHORT, MockVtraderServerTestCase.TestInstrument, 2)
    #     self.assertEqual(order.getFilled(), 0)
    #     self.assertEqual(order.getRemaining(), 2)
    #     vtrader.placeOrder(order)
    #     backtest.onBars(*barsBuilder.nextTuple(100, 100, 100, 100))
    #     vtrader.updateActiveOrders()
    #     self.assertEqual(order.getFilled(), 2)
    #     self.assertEqual(order.getRemaining(), 0)
    #     self.assertTrue(order.isFilled())
    #     self.assertEqual(order.getExecutionInfo().getCommission(), 0)
    #     self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), -1)
    #     self.assertEqual(vtrader.getCash(), 200)
    #
    #     # Buy 1
    #     order = vtrader.createMarketOrder(broker.Order.Action.BUY_TO_COVER, MockVtraderServerTestCase.TestInstrument, 1)
    #     vtrader.placeOrder(order)
    #     self.assertEqual(order.getFilled(), 0)
    #     self.assertEqual(order.getRemaining(), 1)
    #     backtest.onBars(*barsBuilder.nextTuple(100, 100, 100, 100))
    #     vtrader.updateActiveOrders()
    #     self.assertTrue(order.isFilled())
    #     self.assertEqual(order.getFilled(), 1)
    #     self.assertEqual(order.getRemaining(), 0)
    #     self.assertEqual(order.getExecutionInfo().getCommission(), 0)
    #     self.assertEqual(vtrader.getShares(MockVtraderServerTestCase.TestInstrument), 0)
    #     self.assertEqual(vtrader.getCash(), 100)

    def testCancel(self):
        vtrader, backtest = self.get_brokers(100, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
        barsBuilder = BarsBuilder(MockVtraderServerTestCase.TestInstrument, bar.Frequency.MINUTE)

        order = vtrader.createMarketOrder(broker.Order.Action.BUY, MockVtraderServerTestCase.TestInstrument, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        vtrader.placeOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        vtrader.cancelOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        backtest.onBars(*barsBuilder.nextTuple(10, 10, 10, 10))
        vtrader.updateActiveOrders()
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        self.assertTrue(order.isCanceled())
