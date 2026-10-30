import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { researchApi } from './research';
import type { Stock } from './research';

export function useResearchStocks() {
  const query = useQuery({ queryKey: ['research-stocks'], queryFn: async () => (await researchApi.get<Stock[]>('/app/analysis/stocks')).data });
  const [selected, setSelected] = useState('RELIANCE');
  const stocks = query.data || [];
  const symbol = stocks.some(stock => stock.symbol === selected) ? selected : stocks[0]?.symbol || '';
  return { ...query, stocks, symbol, setSymbol: setSelected, stock: stocks.find(stock => stock.symbol === symbol) };
}
