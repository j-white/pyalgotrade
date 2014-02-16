from pyalgotrade.broker import backtesting
from pyalgotrade.strategy import BacktestingStrategy
from pyalgotrade.stratanalyzer import returns
from pyalgotrade import plotter

from pyalgotrade.vtrader import VtraderBroker, utils
from sample_strategy import MyStrategy

class BacktestMyStrategy(MyStrategy, BacktestingStrategy):
    def __init__(self, feed, instruments, smaPeriod):
        MyStrategy.__init__(self, feed, instruments, smaPeriod)
        BacktestingStrategy.__init__(self, feed)

        # Use the same commission model as the Vtrader broker when backtesting
        self.getBroker().setCommission(backtesting.FixedPerTrade(VtraderBroker.COMMISSION_PER_TRADE))

# Build the strategy
instruments = ['BB', 'T']
feed = utils.getFeed(instruments, suffix='.TO')
strategy = BacktestMyStrategy(feed, instruments, smaPeriod=30)

# Attach a returns analyzers to the strategy.
returnsAnalyzer = returns.Returns()
strategy.attachAnalyzer(returnsAnalyzer)

# Attach the plotter to the strategy.
plt = plotter.StrategyPlotter(strategy)

for instrument in instruments:
    # Include the SMA in the instrument's subplot to get it displayed along with the closing prices.
    plt.getInstrumentSubplot(instrument).addDataSeries("%s - SMA" % instrument, strategy.getSMA(instrument))

# Plot the strategy returns at each bar.
plt.getOrCreateSubplot("returns").addDataSeries("Net return", returnsAnalyzer.getReturns())
plt.getOrCreateSubplot("returns").addDataSeries("Cum. return", returnsAnalyzer.getCumulativeReturns())

# Run the strategy.
strategy.run()
print "Final portfolio value: $%.2f" % strategy.getResult()

# Plot the strategy.
plt.plot()
