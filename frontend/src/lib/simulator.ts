export interface Wallet { capital: number; position: number; entryPrice: number; realizedPnl: number }
export const initialWallet = (): Wallet => ({ capital: 100000, position: 0, entryPrice: 0, realizedPnl: 0 });

export function unrealized(wallet: Wallet, price: number): number {
  return wallet.position * (price - wallet.entryPrice);
}

export function closePosition(wallet: Wallet, price: number): Wallet {
  return { ...wallet, realizedPnl: wallet.realizedPnl + unrealized(wallet, price), position: 0, entryPrice: 0 };
}

export function openPosition(wallet: Wallet, side: 'BUY' | 'SELL', quantity: number, price: number): Wallet {
  if (!Number.isFinite(price) || price <= 0 || !Number.isInteger(quantity) || quantity <= 0) return wallet;
  const sign = side === 'BUY' ? 1 : -1;
  if (Math.sign(wallet.position) === sign) return wallet;
  const closed = closePosition(wallet, price);
  // One-times notional limit for either direction; no hidden simulated leverage.
  if (quantity * price > closed.capital + closed.realizedPnl) return wallet;
  return { ...closed, position: sign * quantity, entryPrice: price };
}
