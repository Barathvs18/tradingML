package com.trading.simulator.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "trades")
@Data
@NoArgsConstructor
public class Trade {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "session_id", nullable = false)
    private SimulationSession session;

    @Column(nullable = false, length = 10)
    private String symbol;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 10)
    private TradeType type;

    private int quantity;
    private double price;
    
    @Column(nullable = false)
    private LocalDateTime timestamp;

    public enum TradeType {
        BUY, SELL
    }
}
