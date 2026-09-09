import { formatPrice, NULL_PLACEHOLDER } from "@/lib/format";
import type { FlashDirection } from "@/hooks/usePriceStream";

/**
 * Renders a price with the flash background class applied when
 * `flash` is set, and null-safe (renders NULL_PLACEHOLDER, never $0.00 —
 * PLAN §13.B6 / the null-price contract note).
 */
export function PriceCell({
  price,
  flash,
  className = "",
}: {
  price: number | null | undefined;
  flash?: FlashDirection;
  className?: string;
}) {
  const flashClass = flash === "up" ? "price-flash-up" : flash === "down" ? "price-flash-down" : "price-flash-none";
  const display = price === null || price === undefined ? NULL_PLACEHOLDER : formatPrice(price);
  return (
    <span
      className={`font-data inline-block px-1 rounded-sm ${flashClass} ${className}`}
      data-testid="price-cell"
      data-flash={flash ?? "none"}
    >
      {display}
    </span>
  );
}
