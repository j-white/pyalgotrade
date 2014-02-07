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

import unittest
import datetime

from pyalgotrade.vtrader import VtraderBroker
from pyalgotrade import bar
from pyalgotrade import broker
from pyalgotrade import barfeed

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

class BaseTestCase(unittest.TestCase):
    TestInstrument = "bb"

class MarketOrderTestCase(BaseTestCase):
    def testBuyAndSell(self):
        brk = VtraderBroker("test", "http://localhost:9999/...")
        barsBuilder = BarsBuilder(BaseTestCase.TestInstrument, bar.Frequency.MINUTE)

        # Buy
        order = brk.createMarketOrder(broker.Order.Action.BUY, BaseTestCase.TestInstrument, 1)
        brk.placeOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        brk.onBars(*barsBuilder.nextTuple(10, 15, 8, 12))
        self.assertTrue(order.isFilled())
        self.assertTrue(order.getExecutionInfo().getPrice() == 10)
        self.assertTrue(order.getExecutionInfo().getCommission() == 0)
        self.assertTrue(len(brk.getActiveOrders()) == 0)
        self.assertTrue(brk.getCash() == 1)
        self.assertTrue(brk.getShares(BaseTestCase.TestInstrument) == 1)
        self.assertEqual(order.getFilled(), 1)
        self.assertEqual(order.getRemaining(), 0)

        # Sell
        order = brk.createMarketOrder(broker.Order.Action.SELL, BaseTestCase.TestInstrument, 1)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        brk.placeOrder(order)
        brk.onBars(*barsBuilder.nextTuple(10, 15, 8, 12))
        self.assertTrue(order.isFilled())
        self.assertTrue(order.getExecutionInfo().getPrice() == 10)
        self.assertTrue(order.getExecutionInfo().getCommission() == 0)
        self.assertTrue(len(brk.getActiveOrders()) == 0)
        self.assertTrue(brk.getCash() == 11)
        self.assertTrue(brk.getShares(BaseTestCase.TestInstrument) == 0)
        self.assertEqual(order.getFilled(), 1)
        self.assertEqual(order.getRemaining(), 0)