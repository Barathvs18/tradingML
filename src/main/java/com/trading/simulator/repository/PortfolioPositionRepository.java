package com.trading.simulator.repository;

import com.trading.simulator.model.PortfolioPosition;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PortfolioPositionRepository extends JpaRepository<PortfolioPosition, Long> {
    List<PortfolioPosition> findBySessionId(String sessionId);
    Optional<PortfolioPosition> findBySessionIdAndSymbol(String sessionId, String symbol);
}
