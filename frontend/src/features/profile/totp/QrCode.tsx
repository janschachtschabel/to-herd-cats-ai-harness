import { useMemo } from 'react'
import { encode } from 'uqr'

/** A QR code drawn here as SVG (no image service, no request leaves the browser).
 *  Dark modules on a white field with a quiet zone, whatever the theme: scanners need
 *  the contrast. */
export function QrCode({ value, label }: { value: string; label: string }) {
  const { size, path } = useMemo(() => {
    const { data } = encode(value, { ecc: 'M', border: 4 })
    const cells: string[] = []
    data.forEach((row, y) =>
      row.forEach((dark, x) => {
        if (dark) cells.push(`M${x} ${y}h1v1h-1z`)
      }),
    )
    return { size: data.length, path: cells.join('') }
  }, [value])
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${size} ${size}`}
      shapeRendering="crispEdges"
      className="size-48 rounded-md border bg-white"
    >
      <rect width={size} height={size} fill="#ffffff" />
      <path d={path} fill="#000000" />
    </svg>
  )
}
