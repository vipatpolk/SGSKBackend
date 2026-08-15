import asyncio
import csv
import io

import httpx

from config.sheet_config import ASSET_TABS, get_sheet_export_url
from models.transaction import (
    ClosedShareLot,
    ClosedSymbolSummary,
    ShareLot,
    SheetResult,
    SymbolSummary,
    SymbolTransaction,
    SymbolTransactionSummary,
    Transaction,
)
from utils.format_utils import get_asset_type, normalize_asset_type
from utils.google_auth import get_google_auth_headers
from utils.http_client import get_http_client, get_outbound_semaphore


class ShareLotService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self._custom_client = client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._custom_client or get_http_client()

    async def fetch_sheet(self, tab_id: str) -> SheetResult:
        tab = next((t for t in ASSET_TABS if t["id"] == tab_id), None)
        if not tab or not tab["sheetGid"]:
            return self.create_empty_result(f"Invalid tab id: {tab_id}", False)

        url = get_sheet_export_url(tab["sheetGid"])
        is_closed = tab["id"] == "closed-position"
        asset_type = tab["id"]
        headers = get_google_auth_headers()

        try:
            async with get_outbound_semaphore():
                res = await self.client.get(url, headers=headers)
            res.raise_for_status()
            csv_text = res.text

            transactions = self.parse_csv(csv_text, asset_type)
            summaries, closed_summaries, transaction_summaries = self.process_transactions(transactions)

            return self.build_result(summaries, closed_summaries, transaction_summaries, transactions, is_closed)
        except Exception as e:
            return self.create_empty_result(f"Failed to fetch data: {e}", is_closed)

    async def fetch_all_sheets(self) -> SheetResult:
        sheet_tabs = [t for t in ASSET_TABS if t["sheetGid"]]

        async def fetch_and_parse(tab):
            try:
                headers = get_google_auth_headers()
                async with get_outbound_semaphore():
                    res = await self.client.get(get_sheet_export_url(tab["sheetGid"]), headers=headers)
                res.raise_for_status()
                return self.parse_csv(res.text, tab["id"])
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
            isClosed=is_closed,
        )

    def build_result(
        self,
        summaries: list[SymbolSummary],
        closed_summaries: list[ClosedSymbolSummary],
        transaction_summaries: list[SymbolTransactionSummary],
        raw_transactions: list[Transaction],
        is_closed: bool,
    ) -> SheetResult:

        total_cost_by_currency: dict[str, float] = {}
        total_proceeds_by_currency: dict[str, float] = {}
        total_realized_pl_by_currency: dict[str, float] = {}

        if is_closed:
            for s in closed_summaries:
                total_cost_by_currency[s.currency] = total_cost_by_currency.get(s.currency, 0) + s.totalCost
                total_proceeds_by_currency[s.currency] = total_proceeds_by_currency.get(s.currency, 0) + s.totalProceeds
                total_realized_pl_by_currency[s.currency] = (
                    total_realized_pl_by_currency.get(s.currency, 0) + s.realizedPL
                )

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
                isClosed=True,
            )

        for open_sum in summaries:
            total_cost_by_currency[open_sum.currency] = (
                total_cost_by_currency.get(open_sum.currency, 0) + open_sum.totalCost
            )

        for closed_sum in closed_summaries:
            total_proceeds_by_currency[closed_sum.currency] = (
                total_proceeds_by_currency.get(closed_sum.currency, 0) + closed_sum.totalProceeds
            )
            total_realized_pl_by_currency[closed_sum.currency] = (
                total_realized_pl_by_currency.get(closed_sum.currency, 0) + closed_sum.realizedPL
            )

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
            isClosed=False,
        )

    def parse_csv(self, csv_text: str, tab_asset_type: str) -> list[Transaction]:
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)
        if len(rows) < 2:
            return []

        header = [h.strip().lower() for h in rows[0]]

        def find_idx(*names):
            for i, h in enumerate(header):
                if any(n == h or n in h for n in names):
                    return i
            return -1

        sym_idx = max(0, find_idx("symbol"))
        date_idx = max(1, find_idx("date"))
        qty_idx = max(2, find_idx("quantity", "qty"))
        price_idx = max(3, find_idx("price"))
        curr_idx = max(4, find_idx("currency", "curr"))
        type_idx = find_idx("assettype", "asset type", "asset")
        tx_type_idx = find_idx("transaction type", "tx_type", "txtype", "action", "trade type", "trade_type", "type")
        ex_from_idx = find_idx(
            "exchange from",
            "exchnage from",
            "exchange_from",
            "exchnage_from",
            "exchange in",
            "exchnage in",
            "exchange_in",
            "exchnage_in",
            "switch from",
            "switch_from",
            "switch in",
            "switch_in",
            "from fund",
            "from_fund",
            "from symbol",
            "from_symbol",
            "source fund",
            "source_fund",
            "from",
        )
        ex_to_idx = find_idx(
            "exchange to",
            "exchnage to",
            "exchange_to",
            "exchnage_to",
            "exchange out",
            "exchnage out",
            "exchange_out",
            "exchnage_out",
            "switch to",
            "switch_to",
            "switch out",
            "switch_out",
            "to fund",
            "to_fund",
            "to symbol",
            "to_symbol",
            "target fund",
            "target_fund",
            "to",
        )

        transactions = []
        for row in rows[1:]:
            if len(row) < 5:
                continue
            symbol = row[sym_idx].strip() if len(row) > sym_idx else ""
            date = row[date_idx].strip() if len(row) > date_idx else ""

            try:
                qty_str = row[qty_idx].strip().replace(",", "")
                quantity = float(qty_str)
                price_str = row[price_idx].strip().replace(",", "")
                price = float(price_str)
            except ValueError:
                continue

            if not symbol:
                continue

            currency = row[curr_idx].strip() if len(row) > curr_idx and row[curr_idx].strip() else "USD"

            raw_type = row[type_idx].strip() if type_idx != -1 and len(row) > type_idx else ""
            parsed_type = normalize_asset_type(raw_type) if raw_type else None
            asset_type = parsed_type or get_asset_type(tab_asset_type, symbol)

            ex_from = (
                row[ex_from_idx].strip()
                if ex_from_idx != -1 and len(row) > ex_from_idx and row[ex_from_idx].strip()
                else None
            )
            ex_to = (
                row[ex_to_idx].strip() if ex_to_idx != -1 and len(row) > ex_to_idx and row[ex_to_idx].strip() else None
            )
            parsed_tx_type = (
                row[tx_type_idx].strip().upper()
                if tx_type_idx != -1 and len(row) > tx_type_idx and row[tx_type_idx].strip()
                else None
            )
            if not parsed_tx_type and raw_type:
                parsed_tx_type = raw_type.strip().upper()

            # Row text fallback scan for exchange metadata
            row_str = " ".join([c.strip() for c in row]).upper()
            if any(
                kw in row_str
                for kw in ["EXCHANGE OUT", "EXCHNAGE OUT", "SWITCH OUT", "EX-OUT", "SW-OUT", "EXCHANGE_OUT"]
            ):
                parsed_tx_type = "EXCHANGE_OUT"
            elif any(
                kw in row_str for kw in ["EXCHANGE IN", "EXCHNAGE IN", "SWITCH IN", "EX-IN", "SW-IN", "EXCHANGE_IN"]
            ):
                parsed_tx_type = "EXCHANGE_IN"
            elif any(kw in row_str for kw in ["DIVIDEND", "DIV", "INCOME", "DISTRIBUTION"]):
                parsed_tx_type = "DIVIDEND"
            elif any(kw in row_str for kw in ["EXCHANGE", "EXCHNAGE", "SWITCH", "SWTICH"]) and not parsed_tx_type:
                parsed_tx_type = "EXCHANGE"

            transactions.append(
                Transaction(
                    symbol=symbol,
                    date=date,
                    quantity=quantity,
                    price=price,
                    currency=currency,
                    assetType=asset_type,
                    exchangeFrom=ex_from,
                    exchangeTo=ex_to,
                    txType=parsed_tx_type,
                )
            )

        return transactions

    def process_transactions(
        self, transactions: list[Transaction]
    ) -> tuple[list[SymbolSummary], list[ClosedSymbolSummary], list[SymbolTransactionSummary]]:
        symbol_map: dict[str, list[Transaction]] = {}
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
            exchange_count = 0
            total_realized_pl = 0.0
            total_realized_cost_basis = 0.0

            for i, tx in enumerate(txs):
                is_buy = tx.quantity > 0
                qty = abs(tx.quantity)
                price = tx.price
                total_amount = qty * price
                tx_id = f"{symbol}-{tx.date}-{i + 1}"

                tx_type, is_exchange = self._classify_transaction_type(tx, is_buy)
                if is_exchange:
                    exchange_count += 1

                if tx_type == "DIVIDEND":
                    running_avg = running_total_cost / running_shares if running_shares > 0 else 0
                    processed_tx_list.append(
                        SymbolTransaction(
                            id=tx_id,
                            symbol=tx.symbol,
                            date=tx.date,
                            type="DIVIDEND",
                            quantity=qty,
                            rawQuantity=tx.quantity,
                            price=price,
                            totalAmount=total_amount,
                            currency=tx.currency,
                            assetType=tx.assetType,
                            runningShares=running_shares,
                            runningTotalCost=running_total_cost,
                            runningAverageCost=running_avg,
                            exchangeFrom=tx.exchangeFrom,
                            exchangeTo=tx.exchangeTo,
                        )
                    )
                    continue

                if tx_type in ("BUY", "EXCHANGE_IN") or (is_buy and tx_type != "EXCHANGE_OUT"):
                    if not is_exchange:
                        buy_count += 1
                    total_buy_shares += qty
                    total_buy_amount += total_amount
                    running_shares += qty
                    running_total_cost += total_amount
                    running_avg = running_total_cost / running_shares if running_shares > 0 else 0

                    open_lots.append(
                        ShareLot(
                            symbol=tx.symbol,
                            purchaseDate=tx.date,
                            quantity=qty,
                            costBasis=price,
                            totalCost=total_amount,
                            assetType=tx.assetType,
                        )
                    )

                    processed_tx_list.append(
                        SymbolTransaction(
                            id=tx_id,
                            symbol=tx.symbol,
                            date=tx.date,
                            type=tx_type,
                            quantity=qty,
                            rawQuantity=tx.quantity,
                            price=price,
                            totalAmount=total_amount,
                            currency=tx.currency,
                            assetType=tx.assetType,
                            runningShares=running_shares,
                            runningTotalCost=running_total_cost,
                            runningAverageCost=running_avg,
                            exchangeFrom=tx.exchangeFrom,
                            exchangeTo=tx.exchangeTo,
                        )
                    )
                else:
                    if not is_exchange:
                        sell_count += 1
                    total_sell_shares += qty
                    total_sell_amount += total_amount

                    remaining_to_sell = qty
                    matched_cost = 0.0

                    for lot in list(open_lots):
                        if remaining_to_sell <= EPSILON:
                            break
                        if lot.quantity <= EPSILON:
                            continue

                        matched_qty = min(lot.quantity, remaining_to_sell)
                        buy_cost = matched_qty * lot.costBasis
                        sell_proceeds = matched_qty * price
                        lot_realized_pl = sell_proceeds - buy_cost
                        lot_realized_pl_pct = (lot_realized_pl / buy_cost) * 100.0 if buy_cost > 0 else 0.0

                        closed_lots.append(
                            ClosedShareLot(
                                symbol=tx.symbol,
                                purchaseDate=lot.purchaseDate,
                                closeDate=tx.date,
                                quantity=matched_qty,
                                costBasis=lot.costBasis,
                                sellPrice=price,
                                totalCost=buy_cost,
                                totalProceeds=sell_proceeds,
                                realizedPL=lot_realized_pl,
                                realizedPLPercent=lot_realized_pl_pct,
                                currency=tx.currency,
                                assetType=tx.assetType,
                            )
                        )

                        lot.quantity -= matched_qty
                        lot.totalCost = lot.quantity * lot.costBasis
                        remaining_to_sell -= matched_qty
                        matched_cost += buy_cost

                    tx_realized_pl: float | None = None
                    tx_realized_pl_pct: float | None = None

                    if matched_cost > 0:
                        tx_realized_pl = total_amount - matched_cost
                        tx_realized_pl_pct = (tx_realized_pl / matched_cost) * 100.0
                        total_realized_pl += tx_realized_pl
                        total_realized_cost_basis += matched_cost

                    running_shares = max(0.0, running_shares - qty)
                    running_total_cost = sum(lot.totalCost for lot in open_lots)
                    if running_shares <= EPSILON:
                        running_shares = 0.0
                        running_total_cost = 0.0
                    running_avg = running_total_cost / running_shares if running_shares > 0 else 0

                    processed_tx_list.append(
                        SymbolTransaction(
                            id=tx_id,
                            symbol=tx.symbol,
                            date=tx.date,
                            type=tx_type,
                            quantity=qty,
                            rawQuantity=tx.quantity,
                            price=price,
                            totalAmount=total_amount,
                            currency=tx.currency,
                            assetType=tx.assetType,
                            runningShares=running_shares,
                            runningTotalCost=running_total_cost,
                            runningAverageCost=running_avg,
                            realizedPL=tx_realized_pl,
                            realizedPLPercent=tx_realized_pl_pct,
                            exchangeFrom=tx.exchangeFrom,
                            exchangeTo=tx.exchangeTo,
                        )
                    )

            remaining_lots = [lot for lot in open_lots if lot.quantity > EPSILON]

            if remaining_lots:
                total_shares = sum(lot.quantity for lot in remaining_lots)
                total_cost = sum(lot.totalCost for lot in remaining_lots)
                avg_cost = total_cost / total_shares if total_shares > 0 else 0
                summaries.append(
                    SymbolSummary(
                        symbol=symbol,
                        totalShares=total_shares,
                        totalCost=total_cost,
                        averageCost=avg_cost,
                        currency=currency,
                        lots=remaining_lots,
                        assetType=asset_type,
                    )
                )
            elif closed_lots:
                closed_shares = sum(lot.quantity for lot in closed_lots)
                total_cost = sum(lot.totalCost for lot in closed_lots)
                total_proceeds = sum(lot.totalProceeds for lot in closed_lots)
                realized_pl = total_proceeds - total_cost
                realized_pl_percent = (realized_pl / total_cost) * 100 if total_cost > 0 else 0
                avg_buy = total_cost / closed_shares if closed_shares > 0 else 0
                avg_sell = total_proceeds / closed_shares if closed_shares > 0 else 0
                closed_summaries.append(
                    ClosedSymbolSummary(
                        symbol=symbol,
                        totalShares=0,
                        closedShares=closed_shares,
                        totalCost=total_cost,
                        totalProceeds=total_proceeds,
                        realizedPL=realized_pl,
                        realizedPLPercent=realized_pl_percent,
                        averageBuyPrice=avg_buy,
                        averageSellPrice=avg_sell,
                        currency=currency,
                        lots=closed_lots,
                        assetType=asset_type,
                    )
                )

            avg_buy = total_buy_amount / total_buy_shares if total_buy_shares > 0 else 0
            avg_sell = total_sell_amount / total_sell_shares if total_sell_shares > 0 else 0
            overall_realized_pl_percent = (
                (total_realized_pl / total_realized_cost_basis) * 100 if total_realized_cost_basis > 0 else 0
            )
            current_status = "OPEN" if running_shares > EPSILON else "CLOSED"

            transaction_summaries.append(
                SymbolTransactionSummary(
                    symbol=symbol,
                    assetType=asset_type,
                    currency=currency,
                    totalTransactions=len(txs),
                    buyCount=buy_count,
                    sellCount=sell_count,
                    exchangeCount=exchange_count,
                    totalBuyShares=total_buy_shares,
                    totalSellShares=total_sell_shares,
                    totalBuyAmount=total_buy_amount,
                    totalSellAmount=total_sell_amount,
                    averageBuyPrice=avg_buy,
                    averageSellPrice=avg_sell,
                    netShares=running_shares,
                    netInvested=running_total_cost,
                    currentStatus=current_status,
                    realizedPL=total_realized_pl,
                    realizedPLPercent=overall_realized_pl_percent,
                    firstTradeDate=txs[0].date,
                    lastTradeDate=txs[-1].date,
                    transactions=processed_tx_list,
                )
            )

        summaries.sort(key=lambda x: x.totalCost, reverse=True)
        closed_summaries.sort(key=lambda x: x.realizedPL, reverse=True)
        transaction_summaries.sort(key=lambda x: (-x.totalTransactions, x.symbol))

        return summaries, closed_summaries, transaction_summaries

    @staticmethod
    def _classify_transaction_type(tx: Transaction, is_buy: bool) -> tuple[str, bool]:
        if tx.txType and any(kw in tx.txType for kw in ["DIVIDEND", "DIV", "INCOME", "DISTRIBUTION"]):
            return "DIVIDEND", False

        is_exchange_out = bool(
            tx.exchangeTo
            or (
                tx.txType
                and any(
                    kw in tx.txType
                    for kw in [
                        "EXCHANGE_OUT",
                        "EXCHANGE OUT",
                        "EXCHNAGE OUT",
                        "SWITCH_OUT",
                        "SWITCH OUT",
                        "EX-OUT",
                        "SW-OUT",
                    ]
                )
            )
        )
        is_exchange_in = bool(
            tx.exchangeFrom
            or (
                tx.txType
                and any(
                    kw in tx.txType
                    for kw in ["EXCHANGE_IN", "EXCHANGE IN", "EXCHNAGE IN", "SWITCH_IN", "SWITCH IN", "EX-IN", "SW-IN"]
                )
            )
        )
        is_generic_exchange = bool(
            tx.txType
            and any(kw in tx.txType for kw in ["EXCHANGE", "EXCHNAGE", "SWITCH", "SWTICH"])
            and not is_exchange_out
            and not is_exchange_in
        )

        is_exchange = is_exchange_out or is_exchange_in or is_generic_exchange

        if is_exchange_out or (is_generic_exchange and not is_buy):
            tx_type = "EXCHANGE_OUT"
        elif is_exchange_in or (is_generic_exchange and is_buy):
            tx_type = "EXCHANGE_IN"
        else:
            tx_type = "BUY" if is_buy else "SELL"

        return tx_type, is_exchange
