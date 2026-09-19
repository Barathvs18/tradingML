package com.trading.simulator.service;

import com.trading.simulator.model.MarketData;
import com.trading.simulator.model.PortfolioPosition;
import com.trading.simulator.model.SimulationSession;
import com.trading.simulator.model.Trade;
import com.trading.simulator.repository.PortfolioPositionRepository;
import com.trading.simulator.repository.SimulationSessionRepository;
import com.trading.simulator.repository.TradeRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Service
@RequiredArgsConstructor
public class TradingService {

    private final TradeRepository tradeRepository;
    private final PortfolioPositionRepository positionRepository;
    private final SimulationSessionRepository sessionRepository;

    @Transactional
    public Trade executeTrade(SimulationSession session, String symbol, Trade.TradeType type, int quantity, MarketData latestData) {
        if (latestData == null) {
            throw new IllegalArgumentException("No market data available to execute trade.");
        }

        double price = latestData.getClose();
        double totalValue = price * quantity;

        if (type == Trade.TradeType.BUY) {
            if (session.getCurrentCash() < totalValue) {
                throw new IllegalStateException("Insufficient funds to buy " + quantity + " " + symbol);
            }
            session.setCurrentCash(session.getCurrentCash() - totalValue);

            PortfolioPosition position = positionRepository.findBySessionIdAndSymbol(session.getId(), symbol)
                    .orElseGet(() -> {
                        PortfolioPosition p = new PortfolioPosition();
                        p.setSession(session);
                        p.setSymbol(symbol);
                        p.setQuantity(0);
                        p.setAveragePrice(0);
                        return p;
                    });
            
            double newTotalCost = (position.getQuantity() * position.getAveragePrice()) + totalValue;
            position.setQuantity(position.getQuantity() + quantity);
            position.setAveragePrice(newTotalCost / position.getQuantity());
            positionRepository.save(position);

        } else if (type == Trade.TradeType.SELL) {
            PortfolioPosition position = positionRepository.findBySessionIdAndSymbol(session.getId(), symbol)
                    .orElseThrow(() -> new IllegalStateException("No position exists for " + symbol));
            
            if (position.getQuantity() < quantity) {
                throw new IllegalStateException("Insufficient quantity to sell " + quantity + " " + symbol);
            }

            session.setCurrentCash(session.getCurrentCash() + totalValue);
            position.setQuantity(position.getQuantity() - quantity);
            
            if (position.getQuantity() == 0) {
                positionRepository.delete(position);
            } else {
                positionRepository.save(position);
            }
        }

        Trade trade = new Trade();
        trade.setSession(session);
        trade.setSymbol(symbol);
        trade.setType(type);
        trade.setQuantity(quantity);
        trade.setPrice(price);
        trade.setTimestamp(latestData.getTimestamp());
        tradeRepository.save(trade);

        sessionRepository.save(session);
        return trade;
    }
}
