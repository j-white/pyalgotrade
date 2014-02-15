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

from pyalgotrade import observer
from pyalgotrade import broker
from pyalgotrade.broker import backtesting
from client import VtraderClient

class VtraderOrder(object):
    def setId(self, orderId):
        self.__id = orderId

    def getId(self):
        return self.__id

class MarketOrder(broker.MarketOrder):
    def __init__(self, orderId, *args, **kwargs):
        super(MarketOrder, self).__init__(orderId, *args, **kwargs)
        self.__id = orderId

    def setId(self, orderId):
        self.__id = orderId

    def getId(self):
        return self.__id

class LimitOrder(VtraderOrder, broker.LimitOrder):
    pass

class StopOrder(VtraderOrder, broker.StopOrder):
    pass

class StopLimitOrder(VtraderOrder, broker.StopLimitOrder):
    pass

class VtraderBroker(broker.Broker, observer.Subject):
    """A Vtrader broker."""
    COMMISSION_PER_TRADE = 9.95

    def __init__(self, *args, **kwargs):
        broker.Broker.__init__(self)
        self.__activeOrders = {}
        self.__client = VtraderClient(*args, **kwargs)
        self.__commission = backtesting.FixedPerTrade(self.COMMISSION_PER_TRADE)

    def getClient(self):
        return self.__client

    def getCommission(self):
        return self.__commission

    def setCommission(self, commission):
        self.__commission = commission

    def getCash(self):
        """Returns the amount of available buying power in dollars."""
        return self.__client.getCashValue()

    def getShareValue(self):
        """Returns the value of the current shares if they were to be closed at the current market prices."""
        return self.__client.getShareValue()

    def getEquity(self):
        """Returns the portfolio value (cash + shares)."""
        return self.__client.getEstimatedAccountValue()

    def getShares(self, instrument):
        """Returns the number of shares for an instrument."""
        return self.getPositions().get(instrument, 0)

    def getPositions(self):
        """Returns a dictionary that maps instruments to shares."""
        return self.__client.getPositions()

    def placeOrder(self, order):
        if order.isInitial():
            # Place the order and set the order's id
            self.__client.placeOrder(order)
            self.__activeOrders[order.getId()] = order

            # Switch from INITIAL -> SUBMITTED
            # IMPORTANT: Do not emit an event for this switch because when using the position interface
            # the order is not yet mapped to the position and Position.onOrderUpdated will get called.
            order.switchState(broker.Order.State.SUBMITTED)
        else:
            raise Exception("The order was already processed")

    def getActiveOrders(self):
        return self.__activeOrders.values()

    def updateActiveOrders(self):
        """Updates the state of the active orders by polling the server."""
        for order in self.__activeOrders.values():
            # Switch from SUBMITTED -> ACCEPTED
            if order.isSubmitted():
                order.switchState(broker.Order.State.ACCEPTED)
                self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.ACCEPTED, None))

            # Update the order to reflect the remote state
            orderExecutionInfo = self.__client.updateOrder(order, commission=self.__commission)

            # Notify the order update
            if order.isCanceled():
                del self.__activeOrders[order.getId()]
                if orderExecutionInfo.getQuantity() > 0:
                    self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.PARTIALLY_FILLED, orderExecutionInfo))
                self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.CANCELED, None))
            if order.isFilled():
                del self.__activeOrders[order.getId()]
                self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.FILLED, orderExecutionInfo))
            elif order.isPartiallyFilled():
                self.notifyOrderEvent(broker.OrderEvent(order, broker.OrderEvent.Type.PARTIALLY_FILLED, orderExecutionInfo))

    def createMarketOrder(self, action, instrument, quantity, onClose=False):
        return MarketOrder(-1, action, instrument, quantity, onClose)

    def createLimitOrder(self, action, instrument, limitPrice, quantity):
        return LimitOrder(-1, action, instrument, limitPrice, quantity)

    def createStopOrder(self, action, instrument, stopPrice, quantity):
        return StopOrder(-1, action, instrument, stopPrice, quantity)

    def createStopLimitOrder(self, action, instrument, stopPrice, limitPrice, quantity):
        return StopLimitOrder(-1, action, instrument, limitPrice, stopPrice, quantity)

    def cancelOrder(self, order):
        activeOrder = self.__activeOrders.get(order.getId())
        if activeOrder is None:
            raise Exception("The order is not active anymore")
        if activeOrder.isFilled():
            raise Exception("Can't cancel order that has already been filled")

        self.__client.cancelOrder(order)
        del self.__activeOrders[activeOrder.getId()]
        activeOrder.switchState(broker.Order.State.CANCELED)
        self.notifyOrderEvent(broker.OrderEvent(activeOrder, broker.OrderEvent.Type.CANCELED, "User requested cancellation"))

    # Methods from observer.Subject required when using the broker as part of a Strategy
    def start(self):
        pass

    def stop(self):
        pass

    def join(self):
        pass

    def eof(self):
        return True

    def dispatch(self):
        pass

    def peekDateTime(self):
        return None
