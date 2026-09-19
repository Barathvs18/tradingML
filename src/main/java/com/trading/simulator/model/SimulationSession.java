package com.trading.simulator.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

@Entity
@Table(name = "simulation_sessions")
@Data
@NoArgsConstructor
public class SimulationSession {

    @Id
    private String id = UUID.randomUUID().toString();

    @Column(nullable = false)
    private LocalDateTime currentVirtualTime;

    private double initialCapital;
    private double currentCash;

    private String status = "ACTIVE"; // ACTIVE, FINISHED
    
    private String selectedAlgorithm;
    private String timeframe = "1m"; // 1m, 5m, 1h, 1d

    @OneToMany(mappedBy = "session", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<Trade> trades = new ArrayList<>();

    @OneToMany(mappedBy = "session", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private List<PortfolioPosition> positions = new ArrayList<>();
}
