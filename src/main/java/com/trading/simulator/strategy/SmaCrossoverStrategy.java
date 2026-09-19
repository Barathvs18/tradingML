package com.trading.simulator.strategy;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.SimulationSession;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class SmaCrossoverStrategy implements TradingStrategy {

    private static final int SHORT_WINDOW = 10;
    private static final int LONG_WINDOW = 50;

    @Override
    public String getAlgorithmName() {
        return "SMA_CROSSOVER";
    }

    @Override
    public TradeSignal evaluate(List<MarketData> historicalData, SimulationSession session) {
        if (historicalData.size() < LONG_WINDOW) {
            return new TradeSignal(SignalType.HOLD, "SPY", 0);
        }

        double shortSma = calculateSma(historicalData, SHORT_WINDOW);
        double longSma = calculateSma(historicalData, LONG_WINDOW);
        double prevShortSma = calculateSma(historicalData.subList(1, historicalData.size()), SHORT_WINDOW);
        double prevLongSma = calculateSma(historicalData.subList(1, historicalData.size()), LONG_WINDOW);

        boolean hasPosition = session.getPositions().stream()
                .anyMatch(p -> p.getSymbol().equals("SPY") && p.getQuantity() > 0);

        if (shortSma > longSma && prevShortSma <= prevLongSma && !hasPosition) {
            // Golden cross - Buy
            double currentPrice = historicalData.get(0).getClose();
            int qtyToBuy = (int) (session.getCurrentCash() / currentPrice);
            if (qtyToBuy > 0) {
                return new TradeSignal(SignalType.BUY, "SPY", qtyToBuy);
            }
        } else if (shortSma < longSma && prevShortSma >= prevLongSma && hasPosition) {
            // Death cross - Sell
            int qtyToSell = session.getPositions().stream()
                    .filter(p -> p.getSymbol().equals("SPY"))
                    .findFirst().get().getQuantity();
            return new TradeSignal(SignalType.SELL, "SPY", qtyToSell);
        }

        return new TradeSignal(SignalType.HOLD, "SPY", 0);
    }

    private double calculateSma(List<MarketData> data, int window) {
        return data.stream().limit(window).mapToDouble(MarketData::getClose).average().orElse(0.0);
    }
}
