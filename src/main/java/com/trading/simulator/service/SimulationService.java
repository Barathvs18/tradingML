package com.trading.simulator.service;

import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.repository.SimulationSessionRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;

@Service
@RequiredArgsConstructor
public class SimulationService {

    private final SimulationSessionRepository sessionRepository;
    private final StrategyService strategyService;

    public SimulationSession startSession(LocalDateTime startDate, double initialCapital, String algorithm) {
        SimulationSession session = new SimulationSession();
        session.setCurrentVirtualTime(startDate);
        session.setInitialCapital(initialCapital);
        session.setCurrentCash(initialCapital);
        session.setSelectedAlgorithm(algorithm);
        return sessionRepository.save(session);
    }

    public Optional<SimulationSession> getSession(String sessionId) {
        return sessionRepository.findById(sessionId);
    }

    @Transactional
    public SimulationSession seekForward(String sessionId, int minutesToAdvance) {
        SimulationSession session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Invalid session ID"));

        for (int i = 0; i < minutesToAdvance; i++) {
            session.setCurrentVirtualTime(session.getCurrentVirtualTime().plusMinutes(1));
            // At each minute step, we run the algorithm. 
            // In a real optimized system, we'd only query the next available data point.
            strategyService.executeAlgorithm(session);
        }
        
        return sessionRepository.save(session);
    }

    @Transactional
    public SimulationSession changeDate(String sessionId, LocalDateTime newDate) {
        SimulationSession session = sessionRepository.findById(sessionId)
                .orElseThrow(() -> new IllegalArgumentException("Invalid session ID"));
        
        session.setCurrentVirtualTime(newDate);
        return sessionRepository.save(session);
    }
}
