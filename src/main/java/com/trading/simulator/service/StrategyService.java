package com.trading.simulator.service;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.strategy.TradingStrategy;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

@Service
public class StrategyService {

    private final Map<String, TradingStrategy> strategies;
    private final TradingService tradingService;
    private final MarketDataService marketDataService;

    public StrategyService(List<TradingStrategy> strategyList, TradingService tradingService, MarketDataService marketDataService) {
        this.strategies = strategyList.stream()
                .collect(Collectors.toMap(TradingStrategy::getAlgorithmName, s -> s));
        this.tradingService = tradingService;
        this.marketDataService = marketDataService;
    }

    public List<String> getAvailableAlgorithms() {
        return List.copyOf(strategies.keySet());
    }

    public void executeAlgorithm(SimulationSession session) {
        if (session.getSelectedAlgorithm() == null) return;
        
        TradingStrategy strategy = strategies.get(session.getSelectedAlgorithm());
        if (strategy == null) return;

        // Fetch strict history based on virtual time
        List<MarketData> history = marketDataService.getSimulationData("SPY", session.getCurrentVirtualTime());
        if (history.isEmpty()) return;

        TradingStrategy.TradeSignal signal = strategy.evaluate(history, session);
        
        if (signal.type() != TradingStrategy.SignalType.HOLD) {
            // Execute trade via TradingService
            tradingService.executeTrade(
                    session,
                    signal.symbol(),
                    signal.type() == TradingStrategy.SignalType.BUY ? com.trading.simulator.model.Trade.TradeType.BUY : com.trading.simulator.model.Trade.TradeType.SELL,
                    signal.quantity(),
                    history.get(0)
            );
        }
    }
}
