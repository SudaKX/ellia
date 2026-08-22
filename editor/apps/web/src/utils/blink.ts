/**
 * 触发一次“数据刷新”闪烁动画：从 primary 色渐变回元素当前样式。
 * 用于表单字段值、resource_id、comment 等展示区域的数据变化提示。
 */
export function triggerBlink(element: HTMLElement | null | undefined): void {
  if (!element) return

  const rootStyle = getComputedStyle(document.documentElement)
  const primary = rootStyle.getPropertyValue('--md-sys-color-primary').trim() || '#6750a4'
  const onPrimary = rootStyle.getPropertyValue('--md-sys-color-on-primary').trim() || '#ffffff'

  const currentStyle = getComputedStyle(element)
  const currentBackground = currentStyle.backgroundColor
  const currentColor = currentStyle.color
  const currentBorder = currentStyle.borderColor

  // 取消上一次未完成的闪烁动画，避免叠加
  element.getAnimations().forEach((animation) => animation.cancel())

  element.animate(
    [
      {
        backgroundColor: primary,
        color: onPrimary,
        borderColor: primary,
      },
      {
        backgroundColor: currentBackground,
        color: currentColor,
        borderColor: currentBorder,
      },
    ],
    {
      duration: 300,
      easing: 'ease',
    },
  )
}
