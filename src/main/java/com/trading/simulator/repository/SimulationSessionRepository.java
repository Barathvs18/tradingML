package com.trading.simulator.repository;

import com.trading.simulator.model.SimulationSession;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface SimulationSessionRepository extends JpaRepository<SimulationSession, String> {
}
