import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import type { Extension } from '@codemirror/state'
import { HighlightStyle, syntaxHighlighting } from '@codemirror/language'
import { createTheme } from 'thememirror'
import { tags } from '@lezer/highlight'

const TOKEN_NAMES = [
  '--md-sys-color-surface-container',
  '--md-sys-color-on-surface',
  '--md-sys-color-primary',
  '--md-sys-color-secondary',
  '--md-sys-color-tertiary',
  '--md-sys-color-error',
  '--md-sys-color-on-surface-variant',
  '--md-sys-color-surface-container-high',
] as const

function cssVar(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function withAlpha(hex: string, alpha: number): string {
  const clean = hex.replace('#', '')
  if (clean.length === 6) {
    const alphaHex = Math.round(alpha * 255)
      .toString(16)
      .padStart(2, '0')
    return `#${clean}${alphaHex}`
  }
  return hex
}

function buildM3Theme(variant: 'light' | 'dark'): Extension {
  const isDarkVariant = variant === 'dark'
  const background = cssVar(
    '--md-sys-color-surface-container',
    isDarkVariant ? '#211f26' : '#f3edf7',
  )
  const foreground = cssVar(
    '--md-sys-color-on-surface',
    isDarkVariant ? '#e6e1e5' : '#1c1b1f',
  )
  const primary = cssVar(
    '--md-sys-color-primary',
    isDarkVariant ? '#d0bcff' : '#6750a4',
  )
  const secondary = cssVar(
    '--md-sys-color-secondary',
    isDarkVariant ? '#ccc2dc' : '#625b71',
  )
  const tertiary = cssVar(
    '--md-sys-color-tertiary',
    isDarkVariant ? '#efb8c8' : '#7d5260',
  )
  const error = cssVar(
    '--md-sys-color-error',
    isDarkVariant ? '#f2b8b5' : '#b3261e',
  )
  const onSurfaceVariant = cssVar(
    '--md-sys-color-on-surface-variant',
    isDarkVariant ? '#cac4d0' : '#49454f',
  )
  const gutterBackground = cssVar(
    '--md-sys-color-surface-container-high',
    isDarkVariant ? '#2b2930' : '#ece6f0',
  )

  return createTheme({
    variant,
    settings: {
      background,
      foreground,
      caret: primary,
      selection: withAlpha(primary, 0.2),
      lineHighlight: withAlpha(foreground, isDarkVariant ? 0.08 : 0.1),
      gutterBackground,
      gutterForeground: onSurfaceVariant,
    },
    styles: [
      { tag: tags.propertyName, color: primary },
      { tag: tags.string, color: tertiary },
      { tag: tags.number, color: secondary },
      { tag: [tags.bool, tags.null], color: error },
      { tag: tags.punctuation, color: onSurfaceVariant },
    ],
  })
}

function buildPythonHighlight(variant: 'light' | 'dark'): Extension {
  const isDarkVariant = variant === 'dark'
  const primary = cssVar('--md-sys-color-primary', isDarkVariant ? '#d0bcff' : '#6750a4')
  const secondary = cssVar('--md-sys-color-secondary', isDarkVariant ? '#ccc2dc' : '#625b71')
  const tertiary = cssVar('--md-sys-color-tertiary', isDarkVariant ? '#efb8c8' : '#7d5260')
  const error = cssVar('--md-sys-color-error', isDarkVariant ? '#f2b8b5' : '#b3261e')
  const onSurface = cssVar('--md-sys-color-on-surface', isDarkVariant ? '#e6e1e5' : '#1c1b1f')
  const onSurfaceVariant = cssVar(
    '--md-sys-color-on-surface-variant',
    isDarkVariant ? '#cac4d0' : '#49454f',
  )
  const outline = cssVar('--md-sys-color-outline', isDarkVariant ? '#938f99' : '#79747e')
  const onPrimaryContainer = cssVar(
    '--md-sys-color-on-primary-container',
    isDarkVariant ? '#eaddff' : '#21005d',
  )
  const onSecondaryContainer = cssVar(
    '--md-sys-color-on-secondary-container',
    isDarkVariant ? '#e8def8' : '#1d192b',
  )
  const onTertiaryContainer = cssVar(
    '--md-sys-color-on-tertiary-container',
    isDarkVariant ? '#ffd8e4' : '#31111d',
  )

  return syntaxHighlighting(
    HighlightStyle.define([
      { tag: tags.keyword, color: primary, fontWeight: 'bold' },
      { tag: [tags.comment, tags.lineComment, tags.blockComment], color: onSurfaceVariant, fontStyle: 'italic' },
      { tag: [tags.string, tags.special(tags.string)], color: tertiary },
      { tag: [tags.number, tags.integer, tags.float], color: secondary },
      { tag: [tags.bool, tags.null, tags.atom], color: error },
      { tag: [tags.function(tags.variableName), tags.function(tags.definition(tags.variableName))], color: onSecondaryContainer },
      { tag: tags.definition(tags.variableName), color: onPrimaryContainer, fontWeight: 'bold' },
      { tag: tags.variableName, color: onSurface },
      { tag: tags.propertyName, color: primary },
      { tag: tags.operator, color: outline },
      { tag: tags.punctuation, color: onSurfaceVariant },
      { tag: [tags.className, tags.typeName], color: onSecondaryContainer, fontWeight: 'bold' },
      { tag: [tags.annotation, tags.meta], color: onTertiaryContainer, fontStyle: 'italic' },
      { tag: tags.self, color: onTertiaryContainer },
      { tag: tags.special(tags.variableName), color: error, fontWeight: 'bold' },
    ]),
  )
}

function buildJsonHighlight(variant: 'light' | 'dark'): Extension {
  const isDarkVariant = variant === 'dark'
  const primary = cssVar('--md-sys-color-primary', isDarkVariant ? '#d0bcff' : '#6750a4')
  const secondary = cssVar('--md-sys-color-secondary', isDarkVariant ? '#ccc2dc' : '#625b71')
  const tertiary = cssVar('--md-sys-color-tertiary', isDarkVariant ? '#efb8c8' : '#7d5260')
  const error = cssVar('--md-sys-color-error', isDarkVariant ? '#f2b8b5' : '#b3261e')
  const onSurfaceVariant = cssVar(
    '--md-sys-color-on-surface-variant',
    isDarkVariant ? '#cac4d0' : '#49454f',
  )
  const onPrimaryContainer = cssVar(
    '--md-sys-color-on-primary-container',
    isDarkVariant ? '#eaddff' : '#21005d',
  )

  return syntaxHighlighting(
    HighlightStyle.define([
      { tag: tags.propertyName, color: primary, fontWeight: 'bold' },
      { tag: tags.string, color: tertiary },
      { tag: tags.number, color: secondary },
      { tag: [tags.bool, tags.null, tags.atom], color: error },
      { tag: tags.punctuation, color: onSurfaceVariant },
      { tag: tags.operator, color: onPrimaryContainer },
      { tag: tags.invalid, color: error, textDecoration: 'underline', fontWeight: 'bold' },
    ]),
  )
}

export const useStyleStore = defineStore('style', () => {
  const isDark = ref(false)
  const tokens = ref<Record<string, string>>({})
  const lightEditorTheme = ref<unknown>([])
  const darkEditorTheme = ref<unknown>([])
  const lightPythonHighlight = ref<unknown>([])
  const darkPythonHighlight = ref<unknown>([])
  const lightJsonHighlight = ref<unknown>([])
  const darkJsonHighlight = ref<unknown>([])
  let observer: MutationObserver | null = null
  let initialized = false

  const editorTheme = computed(
    () => (isDark.value ? darkEditorTheme.value : lightEditorTheme.value) as Extension,
  )
  const pythonHighlight = computed(
    () => (isDark.value ? darkPythonHighlight.value : lightPythonHighlight.value) as Extension,
  )
  const jsonHighlight = computed(
    () => (isDark.value ? darkJsonHighlight.value : lightJsonHighlight.value) as Extension,
  )

  function readTokens(): void {
    const style = getComputedStyle(document.documentElement)
    const next: Record<string, string> = {}
    for (const name of TOKEN_NAMES) {
      next[name] = style.getPropertyValue(name).trim()
    }
    tokens.value = next
  }

  function refresh(): void {
    isDark.value = document.documentElement.dataset.theme === 'dark'
    readTokens()
    lightEditorTheme.value = buildM3Theme('light')
    darkEditorTheme.value = buildM3Theme('dark')
    lightPythonHighlight.value = buildPythonHighlight('light')
    darkPythonHighlight.value = buildPythonHighlight('dark')
    lightJsonHighlight.value = buildJsonHighlight('light')
    darkJsonHighlight.value = buildJsonHighlight('dark')
  }

  function init(): void {
    if (initialized) return
    initialized = true
    refresh()
    observer = new MutationObserver(refresh)
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['data-theme'],
    })
  }

  return {
    isDark,
    tokens,
    lightEditorTheme,
    darkEditorTheme,
    editorTheme,
    lightPythonHighlight,
    darkPythonHighlight,
    pythonHighlight,
    lightJsonHighlight,
    darkJsonHighlight,
    jsonHighlight,
    refresh,
    init,
  }
})
