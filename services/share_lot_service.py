import httpx
import csv
import io
from typing import List, Dict, Tuple
import asyncio

from config.sheet_config import get_sheet_export_url, ASSET_TABS
from models.transaction import (
    Transaction, ShareLot, ClosedShareLot, SymbolSummary, ClosedSymbolSummary,
    SymbolTransaction, SymbolTransactionSummary, SheetResult
)
from utils.format_utils import get_asset_type, normalize_asset_type

class ShareLotService:
    def __init__(self):
        self.client = httpx.AsyncClient(follow_redirects=True)

    async def fetch_sheet(self, gid: str) -> SheetResult:
        url = get_sheet_export_url(gid)
        tab = next((t for t in ASSET_TABS if t['sheetGid'] == gid), None)
        is_closed = tab is not None and tab['id'] == 'closed-position'
        asset_type = tab['id'] if tab else 'unknown'

        try:
            res = await self.client.get(url)
            res.raise_for_status()
            csv_text = res.text
            
            transactions = self.parse_csv(csv_text, asset_type)
            summaries, closed_summaries, transaction_summaries = self.process_transactions(transactions)
            
            return self.build_result(summaries, closed_summaries, transaction_summaries, transactions, is_closed)
        except Exception as e:
            return self.create_empty_result(f"Failed to fetch data: {e}", is_closed)

    async def fetch_all_sheets(self) -> SheetResult:
        sheet_tabs = [t for t in ASSET_TABS if t['sheetGid']]
        
        async def fetch_and_parse(tab):
            try:
                res = await self.client.get(get_sheet_export_url(tab['sheetGid']))
                res.raise_for_status()
                return self.parse_csv(res.text, tab['id'])
            except Exception:
                return []

        results = await asyncio.gather(*[fetch_and_parse(t) for t in sheet_tabs])
        all_transactions = [tx for sublist in results for tx in sublist]
        
        summaries, closed_summaries, transaction_summaries = self.process_transactions(all_transactions)
        
        return self.build_result(summaries, closed_summaries, transaction_summaries, all_transactions, False)

    def create_empty_result(self, error: str, is_closed: bool) -> SheetResult:
        return SheetResult(
            summaries=[],
            closedSummaries=[],
            transactionSummaries=[],
            rawTransactions=[],
            totalCostByCurrency={},
            totalProceedsByCurrency={},
            totalRealizedPLByCurrency={},
            totalSymbols=0,
            totalLots=0,
            error=error,
            isClosed=is_closed
        )

    def build_result(self, summaries: List[SymbolSummary], closed_summaries: List[ClosedSymbolSummary], 
                     transaction_summaries: List[SymbolTransactionSummary], raw_transactions: List[Transaction], 
                     is_closed: bool) -> SheetResult:
        
        total_cost_by_currency = {}
        total_proceeds_by_currency = {}
        total_realized_pl_by_currency = {}

        if is_closed:
            for s in closed_summaries:
                total_cost_by_currency[s.currency] = total_cost_by_currency.get(s.currency, 0) + s.totalCost
                total_proceeds_by_currency[s.currency] = total_proceeds_by_currency.get(s.currency, 0) + s.totalProceeds
                total_realized_pl_by_currency[s.currency] = total_realized_pl_by_currency.get(s.currency, 0) + s.realizedPL
                
            return SheetResult(
                summaries=summaries,
                closedSummaries=closed_summaries,
                transactionSummaries=transaction_summaries,
                rawTransactions=raw_transactions,
                totalCostByCurrency=total_cost_by_currency,
                totalProceedsByCurrency=total_proceeds_by_currency,
                totalRealizedPLByCurrency=total_realized_pl_by_currency,
                totalSymbols=len(closed_summaries),
                totalLots=0,
                isClosed=True
            )
            
        for s in summaries:
            total_cost_by_currency[s.currency] = total_cost_by_currency.get(s.currency, 0) + s.totalCost
            
        for s in closed_summaries:
            total_proceeds_by_currency[s.currency] = total_proceeds_by_currency.get(s.currency, 0) + s.totalProceeds
            total_realized_pl_by_currency[s.currency] = total_realized_pl_by_currency.get(s.currency, 0) + s.realizedPL

        return SheetResult(
            summaries=summaries,
            closedSummaries=closed_summaries,
            transactionSummaries=transaction_summaries,
            rawTransactions=raw_transactions,
            totalCostByCurrency=total_cost_by_currency,
            totalProceedsByCurrency=total_proceeds_by_currency,
            totalRealizedPLByCurrency=total_realized_pl_by_currency,
            totalSymbols=len(summaries),
            totalLots=sum(len(s.lots) for s in summaries),
            isClosed=False
        )

    def parse_csv(self, csv_text: str, tab_asset_type: str) -> List[Transaction]:
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        if len(rows) < 2: return []
        
        header = [h.strip().lower() for h in rows[0]]
        
        def find_idx(*names):
            for i, h in enumerate(header):
                if any(n == h or n in h for n in names):
                    return i
            return -1

        sym_idx = max(0, find_idx('symbol'))
        date_idx = max(1, find_idx('date'))
        qty_idx = max(2, find_idx('quantity', 'qty'))
        price_idx = max(3, find_idx('price'))
        curr_idx = max(4, find_idx('currency', 'curr'))
        type_idx = find_idx('type', 'asset', 'assettype', 'asset type')

        transactions = []
        for row in rows[1:]:
            if len(row) < 5: continue
            symbol = row[sym_idx].strip() if len(row) > sym_idx else ''
            date = row[date_idx].strip() if len(row) > date_idx else ''
            
            try:
                quantity = float(row[qty_idx].strip())
                price_str = row[price_idx].strip().replace(',', '')
                price = float(price_str)
            except ValueError:
                continue

            if not symbol: continue
            
            currency = row[curr_idx].strip() if len(row) > curr_idx and row[curr_idx].strip() else 'USD'
            
            raw_type = row[type_idx].strip() if type_idx != -1 and len(row) > type_idx else ''
            parsed_type = normalize_asset_type(raw_type) if raw_type else None
            asset_type = parsed_type or get_asset_type(tab_asset_type, symbol)

            transactions.append(Transaction(
                symbol=symbol, date=date, quantity=quantity, 
                price=price, currency=currency, assetType=asset_type
            ))
            
        return transactions

    def process_transactions(self, transactions: List[Transaction]) -> Tuple[List[SymbolSummary], List[ClosedSymbolSummary], List[SymbolTransactionSummary]]:
        symbol_map = {}
        for tx in transactions:
            symbol_map.setdefault(tx.symbol, []).append(tx)
            
        summaries = []
        closed_summaries = []
        transaction_summaries = []
        EPSILON = 1e-7
        
        for symbol, txs in symbol_map.items():
            txs.sort(key=lambda x: x.date)
            currency = txs[0].currency
            asset_type = txs[0].assetType
            
            open_lots = []
            closed_lots = []
            processed_tx_list = []
            
            running_shares = 0.0
            running_total_cost = 0.0
            total_buy_shares = 0.0
            total_sell_shares = 0.0
            total_buy_amount = 0.0
            total_sell_amount = 0.0
            buy_count = 0
            sell_count = 0
            total_realized_pl = 0.0
            total_realized_cost_basis = 0.0
            
            for i, tx in enumerate(txs):
                is_buy = tx.quantity > 0
                qty = abs(tx.quantity)
                price = tx.price
                total_amount = qty * price
                tx_id = f"{symbol}-{tx.date}-{i+1}"
                
                if is_buy:
                    buy_count += 1
                    total_buy_shares += qty
                    total_buy_amount += total_amount
                    running_shares += qty
                    running_total_cost += total_amount
                    running_avg = running_total_cost / running_shares if running_shares > 0 else 0
                    
                    open_lots.append(ShareLot(
                        symbol=tx.symbol, purchaseDate=tx.date, quantity=qty,
                        costBasis=price, totalCost=total_amount, assetType=tx.assetType
                    ))
                    
                    processed_tx_list.append(SymbolTransaction(
                        id=tx_id, symbol=tx.symbol, date=tx.date, type='BUY',
                        quantity=qty, rawQuantity=tx.quantity, price=price, totalAmount=total_amount,
                        currency=tx.currency, assetType=tx.assetType, runningShares=running_shares,
                        runningTotalCost=running_total_cost, runningAverageCost=running_avg
                    ))
                else:
                    sell_count += 1
                    total_sell_shares += qty
                    total_sell_amount += total_amount
                    
                    remaining_to_sell = qty
                    matched_cost = 0.0
                    
                    for lot in list(open_lots):
                        if remaining_to_sell <= EPSILON: break
                        if lot.quantity <= EPSILON: continue
                        
                        matched_qty = min(lot.quantity, remaining_to_sell)
                        buy_cost = matched_qty * lot.costBasis
                        sell_proceeds = matched_qty * price
                        realized_pl = sell_proceeds - buy_cost
                        realized_pl_percent = (realized_pl / buy_cost) * 100 if buy_cost > 0 else 0
                        
                        closed_lots.append(ClosedShareLot(
                            symbol=tx.symbol, purchaseDate=lot.purchaseDate, closeDate=tx.date,
                            quantity=matched_qty, costBasis=lot.costBasis, sellPrice=price,
                            totalCost=buy_cost, totalProceeds=sell_proceeds, realizedPL=realized_pl,
                            realizedPLPercent=realized_pl_percent, currency=tx.currency, assetType=tx.assetType
                        ))
                        
                        lot.quantity -= matched_qty
                        lot.totalCost = lot.quantity * lot.costBasis
                        remaining_to_sell -= matched_qty
                        matched_cost += buy_cost
                        
                    realized_pl = total_amount - matched_cost
                    realized_pl_percent = (realized_pl / matched_cost) * 100 if matched_cost > 0 else 0
                    total_realized_pl += realized_pl
                    total_realized_cost_basis += matched_cost
                    
                    running_shares = max(0.0, running_shares - qty)
                    running_total_cost = sum(l.totalCost for l in open_lots)
                    if running_shares <= EPSILON:
                        running_shares = 0.0
                        running_total_cost = 0.0
                    running_avg = running_total_cost / running_shares if running_shares > 0 else 0
                    
                    processed_tx_list.append(SymbolTransaction(
                        id=tx_id, symbol=tx.symbol, date=tx.date, type='SELL',
                        quantity=qty, rawQuantity=tx.quantity, price=price, totalAmount=total_amount,
                        currency=tx.currency, assetType=tx.assetType, runningShares=running_shares,
                        runningTotalCost=running_total_cost, runningAverageCost=running_avg,
                        realizedPL=realized_pl, realizedPLPercent=realized_pl_percent
                    ))
                    
            remaining_lots = [lot for lot in open_lots if lot.quantity > EPSILON]
            
            if remaining_lots:
                total_shares = sum(l.quantity for l in remaining_lots)
                total_cost = sum(l.totalCost for l in remaining_lots)
                avg_cost = total_cost / total_shares if total_shares > 0 else 0
                summaries.append(SymbolSummary(
                    symbol=symbol, totalShares=total_shares, totalCost=total_cost,
                    averageCost=avg_cost, currency=currency, lots=remaining_lots, assetType=asset_type
                ))
            elif closed_lots:
                closed_shares = sum(l.quantity for l in closed_lots)
                total_cost = sum(l.totalCost for l in closed_lots)
                total_proceeds = sum(l.totalProceeds for l in closed_lots)
                realized_pl = total_proceeds - total_cost
                realized_pl_percent = (realized_pl / total_cost) * 100 if total_cost > 0 else 0
                avg_buy = total_cost / closed_shares if closed_shares > 0 else 0
                avg_sell = total_proceeds / closed_shares if closed_shares > 0 else 0
                closed_summaries.append(ClosedSymbolSummary(
                    symbol=symbol, totalShares=0, closedShares=closed_shares, totalCost=total_cost,
                    totalProceeds=total_proceeds, realizedPL=realized_pl, realizedPLPercent=realized_pl_percent,
                    averageBuyPrice=avg_buy, averageSellPrice=avg_sell, currency=currency, lots=closed_lots, assetType=asset_type
                ))

            avg_buy = total_buy_amount / total_buy_shares if total_buy_shares > 0 else 0
            avg_sell = total_sell_amount / total_sell_shares if total_sell_shares > 0 else 0
            overall_realized_pl_percent = (total_realized_pl / total_realized_cost_basis) * 100 if total_realized_cost_basis > 0 else 0
            current_status = 'OPEN' if running_shares > EPSILON else 'CLOSED'
            
            transaction_summaries.append(SymbolTransactionSummary(
                symbol=symbol, assetType=asset_type, currency=currency, totalTransactions=len(txs),
                buyCount=buy_count, sellCount=sell_count, totalBuyShares=total_buy_shares,
                totalSellShares=total_sell_shares, totalBuyAmount=total_buy_amount,
                totalSellAmount=total_sell_amount, averageBuyPrice=avg_buy, averageSellPrice=avg_sell,
                netShares=running_shares, netInvested=running_total_cost, currentStatus=current_status,
                realizedPL=total_realized_pl, realizedPLPercent=overall_realized_pl_percent,
                firstTradeDate=txs[0].date, lastTradeDate=txs[-1].date, transactions=processed_tx_list
            ))
            
        summaries.sort(key=lambda x: x.totalCost, reverse=True)
        closed_summaries.sort(key=lambda x: x.realizedPL, reverse=True)
        transaction_summaries.sort(key=lambda x: (-x.totalTransactions, x.symbol))
        
        return summaries, closed_summaries, transaction_summaries
