package com.trading.simulator.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

@Entity
@Table(name = "portfolio_positions")
@Data
@NoArgsConstructor
public class PortfolioPosition {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id", nullable = false)
    private SimulationSession session;

    @Column(nullable = false, length = 10)
    private String symbol;

    private int quantity;
    private double averagePrice;
}
