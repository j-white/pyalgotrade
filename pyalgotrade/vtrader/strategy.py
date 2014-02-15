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

from pyalgotrade.strategy import BaseStrategy
from broker import VtraderBroker

class VtraderStrategy(BaseStrategy):
    def __init__(self, barFeed, *args, **kwargs):
        self.__broker = VtraderBroker(*args, **kwargs)
        self.__useAdjustedValues = False
        super(VtraderStrategy, self).__init__(barFeed, self.__broker)

    def getUseAdjustedValues(self):
        return self.__useAdjustedValues

    def setUseAdjustedValues(self, useAdjusted):
        if not self.getFeed().barsHaveAdjClose():
            raise Exception("The barfeed doesn't support adjusted close values")
        self.getBroker().setUseAdjustedValues(useAdjusted, True)
        self.__useAdjustedValues = useAdjusted

    def onBars(self, bars):
        self.__broker.updateActiveOrders()
