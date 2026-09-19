package com.trading.simulator.controller;

import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.repository.SimulationSessionRepository;
import com.trading.simulator.service.SimulationService;
import com.trading.simulator.service.StrategyService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/simulation")
@RequiredArgsConstructor
public class AlgorithmController {

    private final StrategyService strategyService;
    private final SimulationService simulationService;
    private final SimulationSessionRepository sessionRepository;

    @GetMapping("/algorithms")
    public ResponseEntity<List<String>> getAlgorithms() {
        return ResponseEntity.ok(strategyService.getAvailableAlgorithms());
    }

    @PostMapping("/{sessionId}/algorithm/select")
    public ResponseEntity<SimulationSession> selectAlgorithm(
            @PathVariable String sessionId,
            @RequestBody Map<String, String> body) {
        
        SimulationSession session = simulationService.getSession(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));
        
        session.setSelectedAlgorithm(body.get("algorithm"));
        return ResponseEntity.ok(sessionRepository.save(session));
    }

    @PostMapping("/{sessionId}/algorithm/execute")
    public ResponseEntity<String> executeAlgorithm(@PathVariable String sessionId) {
        SimulationSession session = simulationService.getSession(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Session not found"));
        
        strategyService.executeAlgorithm(session);
        return ResponseEntity.ok("Algorithm executed for virtual time: " + session.getCurrentVirtualTime());
    }
}
