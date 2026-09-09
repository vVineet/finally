import "@testing-library/jest-dom";

/**
 * jsdom has no EventSource implementation. This mock captures every
 * instance so tests can grab the most recent one and fire
 * onopen/onmessage/onerror by hand, exercising usePriceStream exactly
 * the way a real SSE frame would (PLAN §13.A2's map-of-tickers payload).
 */
class MockEventSource {
  static instances: MockEventSource[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState = MockEventSource.CONNECTING;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockEventSource.instances.push(this);
  }

  close() {
    this.readyState = MockEventSource.CLOSED;
  }
}

// @ts-expect-error -- test-only global stub, not a full EventSource
global.EventSource = MockEventSource;
// @ts-expect-error -- exposed for tests to reach into (see test-utils)
global.__MockEventSource = MockEventSource;
