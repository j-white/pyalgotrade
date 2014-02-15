from pyalgotrade.strategy import BacktestingStrategy
from pyalgotrade.vtrader import VtraderBroker, VtraderStrategy
from pyalgotrade.broker import backtesting
from pyalgotrade.vtrader import utils
from pyalgotrade.technical import ma
from pyalgotrade.technical import cross

import pyalgotrade.logger
import logging
logger = pyalgotrade.logger.getLogger("mystrategy")
logger.setLevel(logging.DEBUG)

class MyStrategy(VtraderStrategy):
    def __init__(self, feed, instruments, smaPeriod):
        config = {}
        if issubclass(MyStrategy, VtraderStrategy):
            config = utils.getConfig()
        super(MyStrategy, self).__init__(feed, **config)

        self.__instruments = instruments
        self.__position = {}
        self.__close = {}
        self.__sma = {}

        for instrument in instruments:
            self.__close[instrument] = feed[instrument].getCloseDataSeries()
            self.__sma[instrument] = ma.SMA(self.__close[instrument], smaPeriod)

        # Use the same commission model as the Vtrader broker when backtesting
        if isinstance(self, BacktestingStrategy):
            self.getBroker().setCommission(backtesting.FixedPerTrade(VtraderBroker.COMMISSION_PER_TRADE))

    def getSMA(self, instrument):
        return self.__sma[instrument]

    def onEnterOk(self, position):
        logger.debug("onEnterOk(): Position for %s with %d shares" %
                     (position.getInstrument(), position.getShares()))

    def onEnterCanceled(self, position):
        logger.debug("onEnterCanceled(): Position for %s " % position.getInstrument())
        del self.__position[position.getInstrument()]

    def onExitOk(self, position):
        logger.debug("onExitOk(): Position for %s with %d shares" %
                     (position.getInstrument(), position.getShares()))
        del self.__position[position.getInstrument()]

    def onExitCanceled(self, position):
        logger.debug("onExitCanceled(): Position for %s " % position.getInstrument())
        # If the exit was canceled, re-submit it.
        self.__position[position.getInstrument()].exit()

    def onBars(self, bars):
        for instrument in self.__instruments:
            bar = bars[instrument]
            close = self.__close[instrument]
            sma = self.__sma[instrument]

            # If a position was not opened, check if we should enter a long position.
            if not self.__position.has_key(instrument):
                if cross.cross_above(close, sma) > 0:
                    # Enter a buy market order for 100 shares. The order is good till canceled
                    logger.info("Going long on %s" % instrument)
                    self.__position[instrument] = self.enterLong(instrument, 100, True)

            # Check if we have to exit the position.
            elif cross.cross_below(close, sma) > 0:
                logger.info("Closing position on %s" % instrument)
                self.__position[instrument].exit()

        # broker = self.getBroker()
        # if isinstance(broker, VtraderBroker):
        #     broker.updateActiveOrders()

instruments = ['BB', 'T']
feed = utils.getFeed(instruments, suffix='.TO')
myStrategy = MyStrategy(feed, instruments, smaPeriod=30)

if isinstance(myStrategy, BacktestingStrategy):
    from pyalgotrade.stratanalyzer import returns
    from pyalgotrade import plotter

    # Attach a returns analyzers to the strategy.
    returnsAnalyzer = returns.Returns()
    myStrategy.attachAnalyzer(returnsAnalyzer)

    # Attach the plotter to the strategy.
    plt = plotter.StrategyPlotter(myStrategy)

    for instrument in instruments:
        # Include the SMA in the instrument's subplot to get it displayed along with the closing prices.
        plt.getInstrumentSubplot(instrument).addDataSeries("%s - SMA" % instrument, myStrategy.getSMA(instrument))

    # Plot the strategy returns at each bar.
    plt.getOrCreateSubplot("returns").addDataSeries("Net return", returnsAnalyzer.getReturns())
    plt.getOrCreateSubplot("returns").addDataSeries("Cum. return", returnsAnalyzer.getCumulativeReturns())

    # Run the strategy.
    myStrategy.run()
    print "Final portfolio value: $%.2f" % myStrategy.getResult()

    # Plot the strategy.
    plt.plot()
else:
    # Run the strategy.
    myStrategy.run()
    print "Current portfolio value: $%.2f" % myStrategy.getResult()
