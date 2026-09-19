package com.trading.simulator.controller;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.service.MarketDataService;
import com.trading.simulator.service.SimulationService;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/simulation")
@RequiredArgsConstructor
public class SimulationController {

    private final SimulationService simulationService;
    private final MarketDataService marketDataService;

    @PostMapping("/start")
    public ResponseEntity<SimulationSession> startSession(@RequestBody StartSessionRequest request) {
        SimulationSession session = simulationService.startSession(
                request.getStartDate(),
                request.getInitialCapital(),
                request.getAlgorithm()
        );
        return ResponseEntity.ok(session);
    }

    @GetMapping("/{sessionId}/market-data")
    public ResponseEntity<List<MarketData>> getSimulationMarketData(
            @PathVariable String sessionId,
            @RequestParam(defaultValue = "SPY") String symbol) {
        
        SimulationSession session = simulationService.getSession(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));
        
        // This is strictly limited to the current virtual time (no future data leak)
        List<MarketData> data = marketDataService.getSimulationData(symbol, session.getCurrentVirtualTime());
        return ResponseEntity.ok(data);
    }

    @GetMapping("/{sessionId}/portfolio")
    public ResponseEntity<Map<String, Object>> getPortfolio(@PathVariable String sessionId) {
        SimulationSession session = simulationService.getSession(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));
        
        return ResponseEntity.ok(Map.of(
                "cash", session.getCurrentCash(),
                "positions", session.getPositions(),
                "trades", session.getTrades(),
                "virtualTime", session.getCurrentVirtualTime()
        ));
    }

    @PostMapping("/{sessionId}/change-date")
    public ResponseEntity<SimulationSession> changeDate(
            @PathVariable String sessionId,
            @RequestBody Map<String, String> body) {
        LocalDateTime newDate = LocalDateTime.parse(body.get("newDate"));
        SimulationSession updatedSession = simulationService.changeDate(sessionId, newDate);
        return ResponseEntity.ok(updatedSession);
    }

    @Data
    public static class StartSessionRequest {
        private LocalDateTime startDate;
        private double initialCapital;
        private String algorithm;
    }
}
