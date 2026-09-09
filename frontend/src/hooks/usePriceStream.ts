"use client";

import { useEffect, useRef, useState } from "react";
import type { ConnectionStatus, PriceMap } from "@/lib/types";
import { FLASH_DURATION_MS, SSE_STREAM_PATH } from "@/lib/constants";

export type FlashDirection = "up" | "down" | null;
export type FlashState = Record<string, FlashDirection>;

export interface PriceStreamState {
  prices: PriceMap;
  status: ConnectionStatus;
  flashes: FlashState;
}

/**
 * Owns the single SSE connection to /api/stream/prices for the whole app.
 * PLAN §13.A2: each message is ONE event containing a map of ALL tracked
 * tickers (`data: {"AAPL": {...}, ...}`), not one event per ticker --
 * this hook is the one place that parses that shape; nothing downstream
 * touches EventSource or JSON.parse on the raw frame.
 *
 * Also derives, per ticker, a transient flash direction ("up"/"down")
 * whenever that ticker's price changed since the previous frame, cleared
 * again after FLASH_DURATION_MS -- driven by the tick-over-tick `price`
 * field, independent of whatever `day_change` ends up meaning.
 */
export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<PriceMap>({});
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [flashes, setFlashes] = useState<FlashState>({});

  const prevPricesRef = useRef<PriceMap>({});
  const flashTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({});
  const everConnectedRef = useRef(false);

  useEffect(() => {
    if (typeof EventSource === "undefined") {
      // Non-browser environment (shouldn't happen in the shipped app, but
      // keeps SSR/build-time evaluation safe).
      return;
    }

    const source = new EventSource(SSE_STREAM_PATH);

    source.onopen = () => {
      everConnectedRef.current = true;
      setStatus("connected");
    };

    source.onmessage = (event: MessageEvent<string>) => {
      setStatus("connected");

      let map: PriceMap;
      try {
        map = JSON.parse(event.data) as PriceMap;
      } catch {
        return; // Malformed frame: skip it, keep the stream alive.
      }

      const prevPrices = prevPricesRef.current;
      const changed: FlashState = {};
      for (const ticker of Object.keys(map)) {
        const prev = prevPrices[ticker];
        const next = map[ticker];
        if (prev && prev.price !== next.price) {
          changed[ticker] = next.price > prev.price ? "up" : "down";
        }
      }

      if (Object.keys(changed).length > 0) {
        setFlashes((f) => ({ ...f, ...changed }));
        for (const ticker of Object.keys(changed)) {
          clearTimeout(flashTimersRef.current[ticker]);
          flashTimersRef.current[ticker] = setTimeout(() => {
            setFlashes((f) => ({ ...f, [ticker]: null }));
          }, FLASH_DURATION_MS);
        }
      }

      prevPricesRef.current = map;
      setPrices(map);
    };

    source.onerror = () => {
      // EventSource retries automatically (PLAN §6's `retry: 1000`
      // directive plus native browser behavior). readyState tells us
      // whether this is a transient blip (still trying) or the browser
      // has given up entirely (only happens after an outright rejection,
      // e.g. the server refusing the connection at the HTTP level).
      if (source.readyState === EventSource.CLOSED) {
        setStatus("disconnected");
      } else {
        setStatus(everConnectedRef.current ? "reconnecting" : "connecting");
      }
    };

    return () => {
      source.close();
      Object.values(flashTimersRef.current).forEach(clearTimeout);
      flashTimersRef.current = {};
    };
  }, []);

  return { prices, status, flashes };
}
