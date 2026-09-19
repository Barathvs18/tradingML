package com.trading.simulator.controller;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.model.Trade;
import com.trading.simulator.service.MarketDataService;
import com.trading.simulator.service.SimulationService;
import com.trading.simulator.service.TradingService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/simulation/{sessionId}/trade")
@RequiredArgsConstructor
public class TradingController {

    private final TradingService tradingService;
    private final SimulationService simulationService;
    private final MarketDataService marketDataService;

    @PostMapping
    public ResponseEntity<Trade> executeTrade(
            @PathVariable String sessionId,
            @RequestBody TradeRequest request) {
        
        SimulationSession session = simulationService.getSession(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));

        MarketData latestData = marketDataService.getLatestDataForSimulation(request.getSymbol(), session.getCurrentVirtualTime())
                .orElseThrow(() -> new IllegalStateException("No market data available to trade"));

        Trade trade = tradingService.executeTrade(
                session, 
                request.getSymbol(), 
                Trade.TradeType.valueOf(request.getType().toUpperCase()), 
                request.getQuantity(), 
                latestData
        );
        return ResponseEntity.ok(trade);
    }

    @Data
    public static class TradeRequest {
        private String symbol;
        private String type; // BUY or SELL
        private int quantity;
    }
}
