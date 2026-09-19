package com.trading.simulator.controller;

import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.service.SimulationService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/simulation/{sessionId}/seek")
@RequiredArgsConstructor
public class TimeMachineController {

    private final SimulationService simulationService;

    @PostMapping
    public ResponseEntity<SimulationSession> seekForward(
            @PathVariable String sessionId,
            @RequestBody Map<String, Integer> body) {
        
        int minutes = body.getOrDefault("minutes", 1);
        SimulationSession session = simulationService.seekForward(sessionId, minutes);
        return ResponseEntity.ok(session);
    }
}
