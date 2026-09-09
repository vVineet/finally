// Thin accessor around the global MockEventSource stub installed in
// jest.setup.ts, so tests don't need to know about the global directly.

interface MockEventSourceInstance {
  url: string;
  readyState: number;
  onopen: ((ev: Event) => void) | null;
  onmessage: ((ev: MessageEvent) => void) | null;
  onerror: ((ev: Event) => void) | null;
  close: () => void;
}

interface MockEventSourceCtor {
  instances: MockEventSourceInstance[];
  CONNECTING: number;
  OPEN: number;
  CLOSED: number;
}

export function getLatestEventSource(): MockEventSourceInstance {
  const ctor = (global as unknown as { __MockEventSource: MockEventSourceCtor }).__MockEventSource;
  const instance = ctor.instances[ctor.instances.length - 1];
  if (!instance) throw new Error("No MockEventSource instance was created yet");
  return instance;
}

export function emitPriceMap(map: Record<string, unknown>) {
  const source = getLatestEventSource();
  source.onmessage?.({ data: JSON.stringify(map) } as MessageEvent);
}
