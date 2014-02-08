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
from pyalgotrade import broker
from client import VtraderClient

class VtraderOrder:
    def setId(self, orderId):
        self.__id = orderId

class MarketOrder(broker.MarketOrder, VtraderOrder):
    pass

class LimitOrder(broker.LimitOrder, VtraderOrder):
    pass

class StopOrder(broker.StopOrder, VtraderOrder):
    pass

class StopLimitOrder(broker.StopLimitOrder, VtraderOrder):
    pass


class VtraderBroker(broker.Broker):
    """A Vtrader broker."""
    COMMISSION_PER_ORDER = 9.95

    def __init__(self, portfolio, username, password, url):
        broker.Broker.__init__(self)
        self.__activeOrders = {}
        self.client = VtraderClient(portfolio, username, password, url)

    def getCash(self):
        """Returns the amount of available buying power in dollars."""
        return self.client.get_cash_value()

    def getShares(self, instrument):
        """Returns the number of shares for an instrument."""
        positions = self.getPositions()
        return positions[instrument] if positions.has_key(instrument) else 0

    def getPositions(self):
        """Returns a dictionary that maps instruments to shares."""
        return self.client.get_positions()

    def placeOrder(self, order):
        if order.isInitial():
            self.client.place_order(order)

            # The Vtrader API does not return the order ID when the order is placed, it only
            # returns a message confirming that the order was submitted. In order to
            # retrieve the order id we need to make an additional call. We will assume that the
            # id of the last order for the given instrument is the one we just opened
            # IMPORTANT: This has some limitations in a multi-threaded or multi-client environment, but
            # its the best we can do given the constraints of the API
            order_id = self.client.get_last_orderid_for_instrument(order.getInstrument())
            order.setId(order_id)
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
                self.getOrderUpdatedEvent().emit(self, order)

            if order.isAccepted():
                # Update the order.
                orderExecutionInfo = broker.OrderExecutionInfo(10, order.getQuantity(), self.COMMISSION_PER_ORDER, datetime.datetime.now())
                order.setExecuted(orderExecutionInfo)

                if not order.isActive():
                    del self.__activeOrders[order.getId()]
                    self.getOrderUpdatedEvent().emit(self, order)
            else:
                assert(not order.isActive())
                del self.__activeOrders[order.getId()]
                self.getOrderUpdatedEvent().emit(self, order)

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
        activeOrder.switchState(broker.Order.State.CANCELED)
