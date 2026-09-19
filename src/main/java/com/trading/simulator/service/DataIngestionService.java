package com.trading.simulator.service;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.repository.MarketDataRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Service;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Slf4j
public class DataIngestionService implements CommandLineRunner {

    private final MarketDataRepository marketDataRepository;
    private static final String CSV_FILE_PATH = "spy_data.csv"; 

    @Override
    public void run(String... args) throws Exception {
        if (marketDataRepository.count() > 0) {
            log.info("Market data already exists in database. Skipping ingestion.");
            return;
        }

        File file = new File(CSV_FILE_PATH);
        if (!file.exists()) {
            log.warn("Dataset CSV file '{}' not found. Please place the Kaggle SPY minute dataset here to ingest it on startup.", CSV_FILE_PATH);
            return;
        }

        log.info("Starting data ingestion from {}", CSV_FILE_PATH);
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"); // Adjust based on kaggle dataset format
        
        List<MarketData> batch = new ArrayList<>();
        int batchSize = 10000;

        try (BufferedReader br = new BufferedReader(new FileReader(file))) {
            String line = br.readLine(); // skip header
            while ((line = br.readLine()) != null) {
                String[] values = line.split(",");
                if (values.length < 8) continue;

                MarketData data = new MarketData();
                data.setSymbol("SPY");
                // Expected format: date,open,high,low,close,volume,barCount,average
                data.setTimestamp(LocalDateTime.parse(values[0], formatter));
                data.setOpen(Double.parseDouble(values[1]));
                data.setHigh(Double.parseDouble(values[2]));
                data.setLow(Double.parseDouble(values[3]));
                data.setClose(Double.parseDouble(values[4]));
                data.setVolume(Long.parseLong(values[5]));
                data.setBarCount(Integer.parseInt(values[6]));
                data.setAverage(Double.parseDouble(values[7]));

                batch.add(data);

                if (batch.size() >= batchSize) {
                    marketDataRepository.saveAll(batch);
                    log.info("Ingested {} rows...", batchSize);
                    batch.clear();
                }
            }
            if (!batch.isEmpty()) {
                marketDataRepository.saveAll(batch);
            }
            log.info("Data ingestion complete!");
        } catch (Exception e) {
            log.error("Failed to parse CSV file. Please ensure format matches expected columns.", e);
        }
    }
}
