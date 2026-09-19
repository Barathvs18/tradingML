package com.trading.simulator.repository;

import com.trading.simulator.model.MarketData;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;

@Repository
public interface MarketDataRepository extends JpaRepository<MarketData, Long> {

    // Fetch strictly up to virtual time to prevent data leaks
    @Query("SELECT m FROM MarketData m WHERE m.symbol = :symbol AND m.timestamp <= :virtualTime ORDER BY m.timestamp DESC")
    List<MarketData> findHistoricalData(@Param("symbol") String symbol, @Param("virtualTime") LocalDateTime virtualTime);

    // Get a specific range of history (for General History API)
    @Query("SELECT m FROM MarketData m WHERE m.symbol = :symbol AND m.timestamp BETWEEN :start AND :end ORDER BY m.timestamp ASC")
    List<MarketData> findDataByDateRange(@Param("symbol") String symbol, @Param("start") LocalDateTime start, @Param("end") LocalDateTime end);

    // Get latest tick up to virtual time
    @Query("SELECT m FROM MarketData m WHERE m.symbol = :symbol AND m.timestamp <= :virtualTime ORDER BY m.timestamp DESC LIMIT 1")
    Optional<MarketData> findLatestDataAtOrBefore(@Param("symbol") String symbol, @Param("virtualTime") LocalDateTime virtualTime);
}
