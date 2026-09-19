package com.trading.simulator.strategy;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.SimulationSession;

import java.util.List;

public interface TradingStrategy {
    
    String getAlgorithmName();

    /**
     * Evaluates the current market data and returns a TradeSignal.
     * 
     * @param historicalData Data strictly up to the current virtual time.
     * @param session The current simulation session (portfolio state).
     * @return Signal indicating whether to BUY, SELL, or HOLD.
     */
    TradeSignal evaluate(List<MarketData> historicalData, SimulationSession session);

    enum SignalType {
        BUY, SELL, HOLD
    }

    record TradeSignal(SignalType type, String symbol, int quantity) {}
}
