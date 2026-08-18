export function hashString(input: string): number {
  let hash = 0
  for (let index = 0; index < input.length; index += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(index)
    hash |= 0
  }
  return Math.abs(hash)
}

export interface HashColorPair {
  background: string
  color: string
}

export function getHashColorPair(input: string): HashColorPair {
  const seed = hashString(input)
  const hue = seed % 360
  // 降低饱和度和提高亮度，生成更柔和的浅色背景，避免过于刺眼。
  const saturation = 30 + (seed % 20)
  const lightness = 60 + (seed % 15)

  const rgb = hslToRgb(hue, saturation / 100, lightness / 100)
  const luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
  const color = luminance > 0.5 ? '#000000' : '#ffffff'

  return {
    background: `hsl(${hue} ${saturation}% ${lightness}%)`,
    color,
  }
}

function hslToRgb(hue: number, saturation: number, lightness: number): [number, number, number] {
  const c = (1 - Math.abs(2 * lightness - 1)) * saturation
  const x = c * (1 - Math.abs(((hue / 60) % 2) - 1))
  const m = lightness - c / 2

  let r = 0
  let g = 0
  let b = 0
  if (hue < 60) {
    r = c
    g = x
    b = 0
  } else if (hue < 120) {
    r = x
    g = c
    b = 0
  } else if (hue < 180) {
    r = 0
    g = c
    b = x
  } else if (hue < 240) {
    r = 0
    g = x
    b = c
  } else if (hue < 300) {
    r = x
    g = 0
    b = c
  } else {
    r = c
    g = 0
    b = x
  }

  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)]
}