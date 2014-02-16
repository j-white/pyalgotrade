from pyalgotrade.technical import ma
from pyalgotrade.technical import cross

import pyalgotrade.logger
import logging
logger = pyalgotrade.logger.getLogger("mystrategy")
logger.setLevel(logging.DEBUG)

class MyStrategy():
    def __init__(self, feed, instruments, smaPeriod):
        self.__instruments = instruments
        self.__positions = {}
        self.__close = {}
        self.__sma = {}

        for instrument in instruments:
            self.__close[instrument] = feed[instrument].getCloseDataSeries()
            self.__sma[instrument] = ma.SMA(self.__close[instrument], smaPeriod)

    def setPositions(self, positions):
        for instrument in positions.keys():
            self.__positions[instrument] = positions[instrument]

    def getSMA(self, instrument):
        return self.__sma[instrument]

    def onEnterOk(self, position):
        logger.debug("onEnterOk(): Position for %s with %d shares" %
                     (position.getInstrument(), position.getShares()))

    def onEnterCanceled(self, position):
        logger.debug("onEnterCanceled(): Position for %s " % position.getInstrument())
        del self.__positions[position.getInstrument()]

    def onExitOk(self, position):
        logger.debug("onExitOk(): Position for %s with %d shares" %
                     (position.getInstrument(), position.getShares()))
        del self.__positions[position.getInstrument()]

    def onExitCanceled(self, position):
        logger.debug("onExitCanceled(): Position for %s " % position.getInstrument())
        # If the exit was canceled, re-submit it.
        self.__positions[position.getInstrument()].exit()

    def onBars(self, bars):
        for instrument in self.__instruments:
            bar = bars[instrument]
            close = self.__close[instrument]
            sma = self.__sma[instrument]

            # If a position was not opened, check if we should enter a long position.
            if not self.__positions.has_key(instrument):
                if cross.cross_above(close, sma) > 0:
                    # Enter a buy market order for 1000 shares. The order is good till canceled
                    logger.info("Going long on %s" % instrument)
                    self.__positions[instrument] = self.enterLong(instrument, 1000, True)

            # Check if we have to exit the position.
            elif cross.cross_below(close, sma) > 0:
                logger.info("Closing position on %s" % instrument)
                self.__positions[instrument].exit()
