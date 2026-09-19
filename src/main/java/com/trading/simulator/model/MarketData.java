package com.trading.simulator.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import java.time.LocalDateTime;

@Entity
@Table(name = "market_data", indexes = {
    @Index(name = "idx_symbol_timestamp", columnList = "symbol, timestamp")
})
@Data
@NoArgsConstructor
@AllArgsConstructor
public class MarketData {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 10)
    private String symbol;

    @Column(nullable = false)
    private LocalDateTime timestamp;

    private double open;
    private double high;
    private double low;
    private double close;
    private long volume;
    private int barCount;
    private double average;
}
