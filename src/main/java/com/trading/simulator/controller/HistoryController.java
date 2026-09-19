package com.trading.simulator.controller;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.service.MarketDataService;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.List;

@RestController
@RequestMapping("/api/v1/history")
@RequiredArgsConstructor
public class HistoryController {

    private final MarketDataService marketDataService;

    @GetMapping("/data")
    public ResponseEntity<List<MarketData>> getHistoricalData(
            @RequestParam String symbol,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime start,
            @RequestParam @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) LocalDateTime end) {
        
        List<MarketData> data = marketDataService.getHistoryByDateRange(symbol, start, end);
        return ResponseEntity.ok(data);
    }
}
