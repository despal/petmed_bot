/** Stable appointment card colors (6–8). Readable on light and dark. */

const PALETTE = [
  '#3d7ea6',
  '#6b7c3c',
  '#a65c3d',
  '#6b5b95',
  '#2f8f7a',
  '#a63d5c',
  '#4a6fa5',
  '#8a6d3b',
]

export function colorForAppointment(appointmentId: number): string {
  const idx = Math.abs(appointmentId) % PALETTE.length
  return PALETTE[idx]
}

export { PALETTE }
