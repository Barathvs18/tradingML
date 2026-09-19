package com.trading.simulator.service;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.repository.MarketDataRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class MarketDataService {

    private final MarketDataRepository repository;

    /**
     * Gets historical data up to the session's virtual time (Simulation API).
     * Strictly enforces no future data leaks.
     */
    public List<MarketData> getSimulationData(String symbol, LocalDateTime virtualTime) {
        return repository.findHistoricalData(symbol, virtualTime);
    }

    /**
     * Gets the most recent single data point for the virtual time.
     */
    public Optional<MarketData> getLatestDataForSimulation(String symbol, LocalDateTime virtualTime) {
        return repository.findLatestDataAtOrBefore(symbol, virtualTime);
    }

    /**
     * Fetches data for a specific date range (General History API).
     */
    public List<MarketData> getHistoryByDateRange(String symbol, LocalDateTime start, LocalDateTime end) {
        return repository.findDataByDateRange(symbol, start, end);
    }
}
