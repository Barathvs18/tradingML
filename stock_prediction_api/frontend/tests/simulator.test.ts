import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialWallet, openPosition, closePosition, unrealized } from '../src/lib/simulator.ts';

test('long and short close at the actual replay price', () => {
  const long = openPosition(initialWallet(), 'BUY', 10, 100);
  assert.equal(unrealized(long, 110), 100);
  const closed = closePosition(long, 110);
  assert.equal(closed.realizedPnl, 100);
  assert.equal(closed.position, 0);
  const short = openPosition(closed, 'SELL', 10, 110);
  assert.equal(closePosition(short, 90).realizedPnl, 300);
});

test('reversal settles the old position before opening the new one', () => {
  const long = openPosition(initialWallet(), 'BUY', 10, 100);
  const short = openPosition(long, 'SELL', 5, 110);
  assert.equal(short.realizedPnl, 100);
  assert.equal(short.position, -5);
  assert.equal(short.entryPrice, 110);
  assert.equal(closePosition(short, 120).realizedPnl, 50);
});

test('invalid and unaffordable trades leave the wallet intact', () => {
  const wallet = initialWallet();
  for (const quantity of [0, -1, 1.5, 2000]) assert.equal(openPosition(wallet, 'BUY', quantity, 100), wallet);
  assert.equal(openPosition(wallet, 'SELL', 1, NaN), wallet);
  const long = openPosition(wallet, 'BUY', 10, 100);
  assert.equal(openPosition(long, 'BUY', 10, 110), long);
});
