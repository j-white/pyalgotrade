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
.. moduleauthor:: Gabriel Martin Becedillas Ruiz <gabriel.becedillas@gmail.com>
"""

import unittest
import datetime
import pytz

from pyalgotrade import strategy
from pyalgotrade import barfeed
from pyalgotrade import broker
from pyalgotrade.barfeed import csvfeed
from pyalgotrade.barfeed import yahoofeed
from pyalgotrade.barfeed import ninjatraderfeed
from pyalgotrade.utils import dt
from pyalgotrade import marketsession
import common


def us_equities_datetime(*args, **kwargs):
    ret = datetime.datetime(*args, **kwargs)
    ret = dt.localize(ret, marketsession.USEquities.getTimezone())
    return ret


def get_by_datetime_or_date(dict_, dateTimeOrDate):
    ret = dict_.get(dateTimeOrDate, [])
    if len(ret) == 0 and isinstance(dateTimeOrDate, datetime.datetime):
        ret = dict_.get(dateTimeOrDate.date(), [])
    return ret


class TestStrategy(strategy.BacktestingStrategy):
    def __init__(self, barFeed, cash):
        strategy.BacktestingStrategy.__init__(self, barFeed, cash)

        self.__activePosition = None
        # Maps dates to a tuple of (method, params)
        self.__posEntry = {}
        self.__posExit = {}
        # Maps dates to a tuple of (method, params)
        self.__orderEntry = {}

        self.__result = 0
        self.__netProfit = 0
        self.__orderUpdatedEvents = 0
        self.__enterOkEvents = 0
        self.__enterCanceledEvents = 0
        self.__exitOkEvents = 0
        self.__exitCanceledEvents = 0
        self.__brokerOrdersGTC = False
        self.onStartCalled = False
        self.onIdleCalled = False
        self.onFinishCalled = False

    def addOrder(self, dateTime, method, *args, **kwargs):
        self.__orderEntry.setdefault(dateTime, [])
        self.__orderEntry[dateTime].append((method, args, kwargs))

    def addPosEntry(self, dateTime, enterMethod, *args, **kwargs):
        self.__posEntry.setdefault(dateTime, [])
        self.__posEntry[dateTime].append((enterMethod, args, kwargs))

    def addPosExit(self, dateTime, *args, **kwargs):
        self.__posExit.setdefault(dateTime, [])
        self.__posExit[dateTime].append((args, kwargs))

    def setBrokerOrdersGTC(self, gtc):
        self.__brokerOrdersGTC = gtc

    def getOrderUpdatedEvents(self):
        return self.__orderUpdatedEvents

    def getEnterOkEvents(self):
        return self.__enterOkEvents

    def getExitOkEvents(self):
        return self.__exitOkEvents

    def getEnterCanceledEvents(self):
        return self.__enterCanceledEvents

    def getExitCanceledEvents(self):
        return self.__exitCanceledEvents

    def getResult(self):
        return self.__result

    def getNetProfit(self):
        return self.__netProfit

    def getActivePosition(self):
        return self.__activePosition

    def onStart(self):
        self.onStartCalled = True

    def onIdle(self):
        self.onIdleCalled = True

    def onFinish(self, bars):
        self.onFinishCalled = True

    def onOrderUpdated(self, order):
        self.__orderUpdatedEvents += 1

    def onEnterOk(self, position):
        # print "Enter ok", position.getEntryOrder().getExecutionInfo().getDateTime()
        self.__enterOkEvents += 1
        if self.__activePosition is None:
            self.__activePosition = position
            assert(position.isOpen())
            assert(len(position.getActiveOrders()) != 0)
            assert(position.getShares() != 0)

    def onEnterCanceled(self, position):
        # print "Enter canceled", position.getEntryOrder().getExecutionInfo().getDateTime()
        self.__enterCanceledEvents += 1
        self.__activePosition = None
        assert(not position.isOpen())
        assert(len(position.getActiveOrders()) == 0)
        assert(position.getShares() == 0)

    def onExitOk(self, position):
        # print "Exit ok", position.getExitOrder().getExecutionInfo().getDateTime()
        self.__result += position.getReturn()
        self.__netProfit += position.getNetProfit()
        self.__exitOkEvents += 1
        self.__activePosition = None
        assert(not position.isOpen())
        assert(len(position.getActiveOrders()) == 0)
        assert(position.getShares() == 0)

    def onExitCanceled(self, position):
        # print "Exit canceled", position.getExitOrder().getExecutionInfo().getDateTime()
        self.__exitCanceledEvents += 1
        assert(position.isOpen())
        assert(len(position.getActiveOrders()) == 0)
        assert(position.getShares() != 0)

    def onBars(self, bars):
        dateTime = bars.getDateTime()

        # Check position entry.
        for meth, args, kwargs in get_by_datetime_or_date(self.__posEntry, dateTime):
            if self.__activePosition is not None:
                raise Exception("Only one position allowed at a time")
            self.__activePosition = meth(*args, **kwargs)

        # Check position exit.
        for args, kwargs in get_by_datetime_or_date(self.__posExit, dateTime):
            if self.__activePosition is None:
                raise Exception("A position was not entered")
            self.__activePosition.exit(*args, **kwargs)

        # Check order entry.
        for meth, args, kwargs in get_by_datetime_or_date(self.__orderEntry, dateTime):
            order = meth(*args, **kwargs)
            order.setGoodTillCanceled(self.__brokerOrdersGTC)
            self.getBroker().placeOrder(order)


class StrategyTestCase(unittest.TestCase):
    TestInstrument = "doesntmatter"

    def loadIntradayBarFeed(self):
        fromMonth = 1
        toMonth = 1
        fromDay = 3
        toDay = 3
        barFilter = csvfeed.USEquitiesRTH(us_equities_datetime(2011, fromMonth, fromDay, 00, 00), us_equities_datetime(2011, toMonth, toDay, 23, 59))
        barFeed = ninjatraderfeed.Feed(barfeed.Frequency.MINUTE)
        barFeed.setBarFilter(barFilter)
        barFeed.addBarsFromCSV(StrategyTestCase.TestInstrument, common.get_data_file_path("nt-spy-minute-2011.csv"))
        return barFeed

    def loadDailyBarFeed(self):
        barFeed = yahoofeed.Feed()
        barFeed.addBarsFromCSV(StrategyTestCase.TestInstrument, common.get_data_file_path("orcl-2000-yahoofinance.csv"))
        return barFeed

    def createStrategy(self, useDailyBarFeed=True):
        if useDailyBarFeed:
            barFeed = self.loadDailyBarFeed()
        else:
            barFeed = self.loadIntradayBarFeed()

        strat = TestStrategy(barFeed, 1000)
        return strat


class BrokerOrderTestCase(StrategyTestCase):
    def testMarketOrder(self):
        strat = self.createStrategy()

        o = strat.getBroker().createMarketOrder(broker.Order.Action.BUY, StrategyTestCase.TestInstrument, 1)
        strat.getBroker().placeOrder(o)
        strat.run()
        self.assertTrue(o.isFilled())
        self.assertTrue(strat.getOrderUpdatedEvents() == 2)


class StrategyOrderTestCase(StrategyTestCase):
    def testMarketOrder(self):
        strat = self.createStrategy()

        o = strat.order(StrategyTestCase.TestInstrument, 1)
        strat.run()
        self.assertTrue(o.isFilled())
        self.assertTrue(strat.getOrderUpdatedEvents() == 2)


class LongPosTestCase(StrategyTestCase):
    def testLongPosition(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-08,27.37,27.50,24.50,24.81,63040000,24.26 - Sell
        # 2000-11-07,28.37,28.44,26.50,26.56,58950800,25.97 - Exit long
        # 2000-11-06,30.69,30.69,27.50,27.94,75552300,27.32 - Buy
        # 2000-11-03,31.50,31.75,29.50,30.31,65020900,29.64 - Enter long

        strat.addPosEntry(datetime.datetime(2000, 11, 3), strat.enterLong, StrategyTestCase.TestInstrument, 1, False)
        strat.addPosExit(datetime.datetime(2000, 11, 7))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getOrderUpdatedEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + 27.37 - 30.69, 2))
        self.assertTrue(round(strat.getResult(), 3) == -0.108)
        self.assertTrue(round(strat.getNetProfit(), 2) == round(27.37 - 30.69, 2))

    def testLongPositionAdjClose(self):
        strat = self.createStrategy()
        strat.setUseAdjustedValues(True)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-10-13,31.00,35.75,31.00,35.63,38516200,34.84
        # 2000-10-12,63.81,64.87,61.75,63.00,50892400,30.80
        # 2000-01-19,56.13,58.25,54.00,57.13,49208800,27.93
        # 2000-01-18,107.87,114.50,105.62,111.25,66791200,27.19

        strat.addPosEntry(datetime.datetime(2000, 1, 18), strat.enterLong, StrategyTestCase.TestInstrument, 1, False)
        strat.addPosExit(datetime.datetime(2000, 10, 12))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + 30.31 - 27.44, 2))
        self.assertTrue(round(strat.getResult(), 3) == 0.105)
        self.assertTrue(round(strat.getNetProfit(), 2) == round(30.31 - 27.44, 2))

    def testLongPositionGTC(self):
        strat = self.createStrategy()
        strat.getBroker().setCash(48)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-02-07,59.31,60.00,58.42,59.94,44697200,29.30
        # 2000-02-04,57.63,58.25,56.81,57.81,40925000,28.26 - sell succeeds
        # 2000-02-03,55.38,57.00,54.25,56.69,55540600,27.71 - exit
        # 2000-02-02,54.94,56.00,54.00,54.31,63940400,26.55
        # 2000-02-01,51.25,54.31,50.00,54.00,57108800,26.40
        # 2000-01-31,47.94,50.13,47.06,49.95,68152400,24.42 - buy succeeds
        # 2000-01-28,51.50,51.94,46.63,47.38,86400600,23.16 - buy fails
        # 2000-01-27,55.81,56.69,50.00,51.81,61061800,25.33 - enterLong

        strat.addPosEntry(datetime.datetime(2000, 1, 27), strat.enterLong, StrategyTestCase.TestInstrument, 1, True)
        strat.addPosExit(datetime.datetime(2000, 2, 3))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(48 + 57.63 - 47.94, 2))
        self.assertTrue(round(strat.getNetProfit(), 2) == round(57.63 - 47.94, 2))

    def testEntryCanceled(self):
        strat = self.createStrategy()
        strat.getBroker().setCash(10)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-01-28,51.50,51.94,46.63,47.38,86400600,23.16 - buy fails
        # 2000-01-27,55.81,56.69,50.00,51.81,61061800,25.33 - enterLong

        strat.addPosEntry(datetime.datetime(2000, 1, 27), strat.enterLong, StrategyTestCase.TestInstrument, 1, False)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 0)
        self.assertTrue(strat.getEnterCanceledEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(strat.getBroker().getCash() == 10)
        self.assertTrue(strat.getNetProfit() == 0)

    def testUnrealized(self):
        barFeed = self.loadIntradayBarFeed()
        strat = TestStrategy(barFeed, 1000)

        # 3/Jan/2011 205300 - Enter long
        # 3/Jan/2011 205400 - entry gets filled at 127.21
        # 3/Jan/2011 210000 - last bar

        strat.addPosEntry(dt.localize(datetime.datetime(2011, 1, 3, 20, 53), pytz.utc), strat.enterLong, StrategyTestCase.TestInstrument, 1, True)
        strat.run()
        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 0)

        self.assertEqual(strat.getActivePosition().getUnrealizedReturn(127.21), 0)
        self.assertEqual(strat.getActivePosition().getUnrealizedNetProfit(127.21), 0)

        self.assertEqual(round(strat.getActivePosition().getUnrealizedReturn(127.21*1.5), 4), 0.5)
        self.assertEqual(round(strat.getActivePosition().getUnrealizedNetProfit(127.21*1.5), 4), 127.21/2)

        self.assertEqual(strat.getActivePosition().getUnrealizedReturn(127.21*2), 1)
        self.assertEqual(strat.getActivePosition().getUnrealizedNetProfit(127.21*2), 127.21)

    def testIsOpen_NotClosed(self):
        strat = self.createStrategy()
        strat.addPosEntry(datetime.datetime(2000, 11, 3), strat.enterLong, StrategyTestCase.TestInstrument, 1, False)
        strat.run()
        self.assertTrue(strat.getActivePosition().isOpen())


class ShortPosTestCase(StrategyTestCase):
    def testShortPosition(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-08,27.37,27.50,24.50,24.81,63040000,24.26
        # 2000-11-07,28.37,28.44,26.50,26.56,58950800,25.97
        # 2000-11-06,30.69,30.69,27.50,27.94,75552300,27.32
        # 2000-11-03,31.50,31.75,29.50,30.31,65020900,29.64

        strat.addPosEntry(datetime.datetime(2000, 11, 3), strat.enterShort, StrategyTestCase.TestInstrument, 1, False)
        strat.addPosExit(datetime.datetime(2000, 11, 7))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + 30.69 - 27.37, 2))
        self.assertTrue(round(strat.getResult(), 3) == round(0.10817856, 3))
        self.assertTrue(round(strat.getNetProfit(), 2) == round(30.69 - 27.37, 2))

    def testShortPositionAdjClose(self):
        strat = self.createStrategy()
        strat.setUseAdjustedValues(True)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-10-13,31.00,35.75,31.00,35.63,38516200,34.84
        # 2000-10-12,63.81,64.87,61.75,63.00,50892400,30.80
        # 2000-01-19,56.13,58.25,54.00,57.13,49208800,27.93
        # 2000-01-18,107.87,114.50,105.62,111.25,66791200,27.19

        strat.addPosEntry(datetime.datetime(2000, 1, 18), strat.enterShort, StrategyTestCase.TestInstrument, 1, False)
        strat.addPosExit(datetime.datetime(2000, 10, 12))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + 27.44 - 30.31, 2))
        self.assertTrue(round(strat.getResult(), 3) == round(-0.104591837, 3))
        self.assertTrue(round(strat.getNetProfit(), 2) == round(27.44 - 30.31, 2))

    def testShortPositionExitCanceled(self):
        strat = self.createStrategy()
        strat.getBroker().setCash(0)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-12-08,30.06,30.62,29.25,30.06,40054100,29.39
        # 2000-12-07,29.62,29.94,28.12,28.31,41093000,27.68
        # .
        # 2000-11-29,23.19,23.62,21.81,22.87,75408100,22.36
        # 2000-11-28,23.50,23.81,22.25,22.66,43078300,22.16

        strat.addPosEntry(datetime.datetime(2000, 11, 28), strat.enterShort, StrategyTestCase.TestInstrument, 1, False)
        strat.addPosExit(datetime.datetime(2000, 12, 7))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == 23.19)
        self.assertTrue(strat.getNetProfit() == 0)

    def testShortPositionExitCanceledAndReSubmitted(self):
        strat = self.createStrategy()
        strat.getBroker().setCash(0)

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-24,23.31,24.25,23.12,24.12,22446100,23.58
        # 2000-11-22,23.62,24.06,22.06,22.31,53317000,21.81 - exitShort that gets filled
        # 2000-11-21,24.81,25.62,23.50,23.87,58651900,23.34
        # 2000-11-20,24.31,25.87,24.00,24.75,89783100,24.20
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74 - exitShort that gets canceled
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterShort

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterShort, StrategyTestCase.TestInstrument, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 14))
        strat.addPosExit(datetime.datetime(2000, 11, 22))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(25.12 - 23.31, 2))

    def testUnrealized(self):
        barFeed = self.loadIntradayBarFeed()
        strat = TestStrategy(barFeed, 1000)

        # 3/Jan/2011 205300 - Enter long
        # 3/Jan/2011 205400 - entry gets filled at 127.21
        # 3/Jan/2011 210000 - last bar

        strat.addPosEntry(dt.localize(datetime.datetime(2011, 1, 3, 20, 53), pytz.utc), strat.enterShort, StrategyTestCase.TestInstrument, 1, True)
        strat.run()
        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 0)

        self.assertEqual(strat.getActivePosition().getUnrealizedReturn(127.21), 0)
        self.assertEqual(strat.getActivePosition().getUnrealizedNetProfit(127.21), 0)

        self.assertEqual(round(strat.getActivePosition().getUnrealizedReturn(127.21/2), 4), 0.5)
        self.assertEqual(round(strat.getActivePosition().getUnrealizedNetProfit(127.21/2), 4), 127.21/2)

        self.assertEqual(strat.getActivePosition().getUnrealizedReturn(127.21*2), -1)
        self.assertEqual(strat.getActivePosition().getUnrealizedNetProfit(127.21*2), -127.21)


class LimitPosTestCase(StrategyTestCase):
    def testLong(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - exit filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - exitPosition
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 - entry filled
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongLimit, StrategyTestCase.TestInstrument, 25, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 16), 29)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == 1004)

    def testShort(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-24,23.31,24.25,23.12,24.12,22446100,23.58 - exit filled
        # 2000-11-22,23.62,24.06,22.06,22.31,53317000,21.81 - exitPosition
        # 2000-11-21,24.81,25.62,23.50,23.87,58651900,23.34
        # 2000-11-20,24.31,25.87,24.00,24.75,89783100,24.20
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - entry filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - enterShortLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 16), strat.enterShortLimit, StrategyTestCase.TestInstrument, 29, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 22), 24)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (29 - 23.31), 2))

    def testExitOnEntryNotFilled(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - entry canceled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - exitPosition
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongLimit, StrategyTestCase.TestInstrument, 5, 1, True)
        strat.addPosExit(datetime.datetime(2000, 11, 16), 29)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 0)
        self.assertTrue(strat.getEnterCanceledEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == 1000)

    def testExitTwice(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - exit filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - exitPosition using a market order (cancels the previous one).
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74 - exitPosition
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 - entry filled
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongLimit, StrategyTestCase.TestInstrument, 25, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 14), 100)
        strat.addPosExit(datetime.datetime(2000, 11, 16))
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (26.94 - 25), 2))

    def testExitCancelsEntry(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74 - exitPosition (cancels the entry).
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 -
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongLimit, StrategyTestCase.TestInstrument, 5, 1, True)
        strat.addPosExit(datetime.datetime(2000, 11, 14), 100)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 0)
        self.assertTrue(strat.getEnterCanceledEvents() == 1)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == 1000)

    def testEntryGTCExitNotGTC(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23 - GTC exitPosition (never filled)
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74 -
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 - entry filled
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongLimit, StrategyTestCase.TestInstrument, 25, 1, True)
        strat.addPosExit(datetime.datetime(2000, 11, 15), 100, None, False)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 0)
        self.assertTrue(strat.getExitCanceledEvents() == 1)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 - 25, 2))


class StopPosTestCase(StrategyTestCase):
    def testLong(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - exit filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - exitPosition
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 - entry filled
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongStop

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongStop, StrategyTestCase.TestInstrument, 25, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 16), None, 26)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (26 - 25.12), 2))

    def testShort(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-24,23.31,24.25,23.12,24.12,22446100,23.58 - exit filled
        # 2000-11-22,23.62,24.06,22.06,22.31,53317000,21.81 - exitPosition
        # 2000-11-21,24.81,25.62,23.50,23.87,58651900,23.34
        # 2000-11-20,24.31,25.87,24.00,24.75,89783100,24.20
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - entry filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - enterShortStop

        strat.addPosEntry(datetime.datetime(2000, 11, 16), strat.enterShortStop, StrategyTestCase.TestInstrument, 27, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 22), None, 23)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (26.94 - 23.31), 2))


class StopLimitPosTestCase(StrategyTestCase):
    def testLong(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - exit filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - exitPosition
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20 - entry filled
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87 - enterLongStopLimit

        strat.addPosEntry(datetime.datetime(2000, 11, 10), strat.enterLongStopLimit, StrategyTestCase.TestInstrument, 24, 25.5, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 16), 28, 27)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (28 - 24), 2))

    def testShort(self):
        strat = self.createStrategy()

        # Date,Open,High,Low,Close,Volume,Adj Close
        # 2000-11-24,23.31,24.25,23.12,24.12,22446100,23.58 - exit filled
        # 2000-11-22,23.62,24.06,22.06,22.31,53317000,21.81 - exitPosition
        # 2000-11-21,24.81,25.62,23.50,23.87,58651900,23.34
        # 2000-11-20,24.31,25.87,24.00,24.75,89783100,24.20
        # 2000-11-17,26.94,29.25,25.25,28.81,59639400,28.17 - entry filled
        # 2000-11-16,28.75,29.81,27.25,27.37,37990000,26.76 - enterShortStopLimit
        # 2000-11-15,28.81,29.44,27.70,28.87,50655200,28.23
        # 2000-11-14,27.37,28.50,26.50,28.37,77496700,27.74
        # 2000-11-13,25.12,25.87,23.50,24.75,61651900,24.20
        # 2000-11-10,26.44,26.94,24.87,25.44,54614100,24.87

        strat.addPosEntry(datetime.datetime(2000, 11, 16), strat.enterShortStopLimit, StrategyTestCase.TestInstrument, 29, 27, 1)
        strat.addPosExit(datetime.datetime(2000, 11, 22), 25, 24)
        strat.run()

        self.assertTrue(strat.getEnterOkEvents() == 1)
        self.assertTrue(strat.getEnterCanceledEvents() == 0)
        self.assertTrue(strat.getExitOkEvents() == 1)
        self.assertTrue(strat.getExitCanceledEvents() == 0)
        self.assertTrue(round(strat.getBroker().getCash(), 2) == round(1000 + (29 - 24), 2))

class OptionalOverridesTestCase(StrategyTestCase):
    def testOnStartIdleFinish(self):
        strat = self.createStrategy()
        strat.run()
        self.assertTrue(strat.onStartCalled)
        self.assertTrue(strat.onFinishCalled)
        self.assertFalse(strat.onIdleCalled)
