"use client";

import { useCallback, useState } from "react";
import { Header } from "@/components/header/Header";
import { Watchlist } from "@/components/watchlist/Watchlist";
import { MainChart } from "@/components/chart/MainChart";
import { PortfolioHeatmap } from "@/components/heatmap/PortfolioHeatmap";
import { PnlChart } from "@/components/pnl/PnlChart";
import { PositionsTable } from "@/components/positions/PositionsTable";
import { TradeBar } from "@/components/tradebar/TradeBar";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { usePriceStream } from "@/hooks/usePriceStream";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useWatchlist } from "@/hooks/useWatchlist";
import { useChat } from "@/hooks/useChat";
import { computeLiveTotalValue } from "@/lib/portfolio";

export default function Home() {
  const { prices, status, flashes } = usePriceStream();
  const { portfolio, trade, reset, setPortfolio } = usePortfolio();
  const { watchlist, add, remove, setWatchlist } = useWatchlist();
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [tradeVersion, setTradeVersion] = useState(0);

  const { messages, loading: chatLoading, sending, send } = useChat({
    onApplied: (nextPortfolio, nextWatchlist) => {
      setPortfolio(nextPortfolio);
      setWatchlist(nextWatchlist);
      setTradeVersion((v) => v + 1);
    },
  });

  const effectiveSelected = selectedTicker ?? watchlist[0]?.ticker ?? null;

  const handleTrade = useCallback(
    async (ticker: string, side: "buy" | "sell", quantity: number) => {
      const res = await trade(ticker, side, quantity);
      setTradeVersion((v) => v + 1);
      return res;
    },
    [trade]
  );

  const handleReset = useCallback(async () => {
    const res = await reset();
    setWatchlist(res.watchlist);
    setSelectedTicker(null);
    setTradeVersion((v) => v + 1);
  }, [reset, setWatchlist]);

  // B6: recomputed client-side from the live SSE map every render (i.e.
  // every ~500ms tick), so the header moves faster than a portfolio poll
  // ever could, while staying defined by the exact same formula the
  // backend uses.
  const liveTotalValue = computeLiveTotalValue(portfolio, prices);

  return (
    <>
      <Header
        totalValue={liveTotalValue}
        cashBalance={portfolio?.cash_balance ?? null}
        status={status}
        onReset={handleReset}
      />
      <main className="flex-1 min-h-0 grid grid-cols-[300px_1fr_360px] gap-2 p-2 bg-bg-base">
        <div className="min-h-0">
          <Watchlist
            watchlist={watchlist}
            prices={prices}
            flashes={flashes}
            selectedTicker={effectiveSelected}
            onSelectTicker={setSelectedTicker}
            onAdd={add}
            onRemove={remove}
          />
        </div>

        <div className="min-h-0 grid grid-rows-[2fr_1fr_1fr_auto] gap-2">
          <MainChart ticker={effectiveSelected} prices={prices} />
          <div className="grid grid-cols-2 gap-2 min-h-0">
            <PortfolioHeatmap positions={portfolio?.positions ?? []} />
            <PnlChart refreshToken={tradeVersion} />
          </div>
          <PositionsTable positions={portfolio?.positions ?? []} />
          <TradeBar onTrade={handleTrade} defaultTicker={effectiveSelected} />
        </div>

        <div className="min-h-0">
          <ChatPanel messages={messages} loading={chatLoading} sending={sending} onSend={send} />
        </div>
      </main>
    </>
  );
}
