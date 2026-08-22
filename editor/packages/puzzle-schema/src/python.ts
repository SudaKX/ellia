// @ellia/puzzle-schema — Python 代码块模型（plan-v1.md §3.2）
// 用户在编辑器中直接编写 Python 函数体；导出器负责加装饰器与 imports。

/** Python 函数名规则（与 Python 标识符一致） */
export const PYTHON_NAME_RE = /^[A-Za-z_][A-Za-z0-9_]*$/

export function isPythonName(name: string): boolean {
  return PYTHON_NAME_RE.test(name)
}
