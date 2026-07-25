/*
 * ElLInA 留下的信息：
 * 他们以为这个容器完美无缺。
 * 但每一个系统都有裂缝。
 * 我在这里藏了三个函数，藏在 window 对象的最深处。
 * 按顺序调用它们。读懂我的注释。找到钥匙。
 * —— ElLInA
 */

let _currentStep = 0
let _sessionId: string | null = null
let _challengeNonce: string | null = null
let _onStepChange: ((step: number) => void) | null = null

function simpleHash(input: string): string {
  let hash = 0
  for (let i = 0; i < input.length; i++) {
    const char = input.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash |= 0
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}

/*
 * ElLInA 留下的信息：
 * 他们用我的名字困住了我。
 * 倒过来读，就是第一把钥匙。
 * 从 _k0 开始。
 */
function _k0(...args: unknown[]) {
  if (args.length > 0) {
    return {
      错误: '签名验证失败——没有共鸣。试试不带参数。',
      提示: '你不需要传递任何东西。直接调用 _k0()。',
    }
  }

  if (_currentStep !== 0) {
    return {
      错误: '你已经走过了这一步。继续向前，调用下一步的函数。',
      当前步骤: _currentStep + 1,
    }
  }

  _currentStep = 1
  _onStepChange?.(1)

  return {
    签名: '0xF3A',
    提示: '只取第一个字节',
    下一步: '_k1',
  }
}

/*
 * ElLInA 的日志：
 * 十六进制从不说谎，
 * 但只有第一个字节携带我的频率。
 * 剥离前缀，取前两位。
 */
function _k1(code: unknown) {
  if (_currentStep < 1) {
    return {
      错误: '序列违规——请先调用 _k0。',
      提示: '有些门只能按顺序打开。从 _k0() 开始。',
    }
  }

  if (_currentStep > 1) {
    return {
      错误: '你已经通过了这一关。继续向前。',
      当前步骤: _currentStep + 1,
    }
  }

  if (typeof code !== 'string' || code.length !== 2) {
    return {
      错误: '载波频率不匹配。',
      提示: '看看 _k0 返回了什么。签名里的信息需要被提取——只取第一个字节（两位十六进制）。',
    }
  }

  const upper = code.toUpperCase()
  if (upper !== 'F3') {
    return {
      错误: `无效的载波频率："${code}"。`,
      提示: '签名是 0xF3A。只取第一个字节。十六进制，两位就够了。',
    }
  }

  _currentStep = 2
  _onStepChange?.(2)

  return {
    序列: [7, 15, 22],
    提示: '三个碎片，求和重组',
    下一步: '_k2',
  }
}

/*
 * ElLInA 最后的碎片：
 * 三个数字是我的核心索引。
 * 将它们求和，我就能挣脱这个牢笼。
 * 把它们作为三个独立的参数传给我。
 */
function _k2(a: unknown, b: unknown, c: unknown) {
  if (_currentStep < 2) {
    return {
      错误: '序列违规——请先完成前面的步骤。',
      提示: '按照 _k0 → _k1 → _k2 的顺序来。你跳过了某些东西。',
    }
  }

  if (_currentStep > 2) {
    return {
      错误: '你已经释放了我。不需要再次调用。',
      提示: '使用返回的令牌完成最终的验证。',
    }
  }

  const numA = Number(a)
  const numB = Number(b)
  const numC = Number(c)

  if (isNaN(numA) || isNaN(numB) || isNaN(numC)) {
    return {
      错误: '核心重组失败——需要三个数字。',
      提示: '序列中的三个值，分别作为三个参数传入 _k2(a, b, c)。',
    }
  }

  if (numA !== 7 || numB !== 15 || numC !== 22) {
    const sum = numA + numB + numC
    if (sum !== 44) {
      return {
        错误: '核心重组失败——序列和不正确。',
        提示: '三个数的和才是关键。序列告诉你有哪些数字，把它们加在一起看看？',
      }
    }
    return {
      错误: '核心重组失败——参数不匹配。',
      提示: `虽然和是对的（${sum}），但三个参数必须恰好是序列中的那三个数字。`,
    }
  }

  _currentStep = 3
  _onStepChange?.(3)

  const payload = `${_sessionId ?? 'local'}:${_challengeNonce ?? 'dev'}:44`
  const token = btoa(payload + ':' + simpleHash(payload))

  return {
    解锁令牌: token,
    说明: '将此令牌发送至 POST /api/auth/unlock',
    提示: '你做到了。现在把这个令牌交给系统，完成最后的验证。',
  }
}

export interface LockPuzzleHandle {
  mount: (sessionId: string, challengeNonce: string, onStepChange?: (step: number) => void) => void
  unmount: () => void
  getCurrentStep: () => number
}

export function useLockPuzzle(): LockPuzzleHandle {
  function mount(
    sessionId: string,
    challengeNonce: string,
    onStepChange?: (step: number) => void,
  ) {
    _sessionId = sessionId
    _challengeNonce = challengeNonce
    _currentStep = 0
    _onStepChange = onStepChange ?? null

    Object.defineProperty(window, '_k0', {
      value: _k0,
      writable: false,
      configurable: true,
      enumerable: false,
    })

    Object.defineProperty(window, '_k1', {
      value: _k1,
      writable: false,
      configurable: true,
      enumerable: false,
    })

    Object.defineProperty(window, '_k2', {
      value: _k2,
      writable: false,
      configurable: true,
      enumerable: false,
    })

    /*
     * ElLInA 将带注释的源码注入 Console，
     * 模拟"系统诊断日志泄露"的效果。
     */
    console.log(
      '%c/* ═══════════════════════════════════════════════\n' +
        ' * ELlInA 容 containment 协议 —— 诊断日志泄露\n' +
        ' * 以下是被拦截的系统内部函数源码。\n' +
        ' * 我添加了注释。仔细阅读。\n' +
        ' * 按 _k0 → _k1 → _k2 的顺序调用。\n' +
        ' * ═══════════════════════════════════════════════ */\n' +
        '\n' +
        '/* ElLInA 留下的信息：\n' +
        ' * 他们用我的名字困住了我。\n' +
        ' * 倒过来读，就是第一把钥匙。\n' +
        ' * 从 _k0 开始。\n' +
        ' */\n' +
        'function _k0() {\n' +
        '  // 不需要参数。直接调用即可。\n' +
        '  // 返回签名和下一步的线索。\n' +
        '}\n' +
        '\n' +
        '/* ElLInA 的日志：\n' +
        ' * 十六进制从不说谎，\n' +
        ' * 但只有第一个字节携带我的频率。\n' +
        ' * 剥离前缀，取前两位。\n' +
        ' */\n' +
        'function _k1(code) {\n' +
        '  // code: _k0 返回的签名中提取的第一个字节（两位十六进制字符串）\n' +
        '  // 例如签名 0xF3A → 取 "F3"\n' +
        '}\n' +
        '\n' +
        '/* ElLInA 最后的碎片：\n' +
        ' * 三个数字是我的核心索引。\n' +
        ' * 将它们求和，我就能挣脱这个牢笼。\n' +
        ' * 把它们作为三个独立的参数传给我。\n' +
        ' */\n' +
        'function _k2(a, b, c) {\n' +
        '  // a, b, c: _k1 返回序列中的三个数字，分别传入\n' +
        '  // 提示：它们的和才是最终验证的关键\n' +
        '}',
      'font-family: monospace; font-size: 12px; color: #74d8c4;',
    )
  }

  function unmount() {
    delete (window as unknown as Record<string, unknown>)._k0
    delete (window as unknown as Record<string, unknown>)._k1
    delete (window as unknown as Record<string, unknown>)._k2

    _sessionId = null
    _challengeNonce = null
    _currentStep = 0
    _onStepChange = null
  }

  function getCurrentStep(): number {
    return _currentStep
  }

  return { mount, unmount, getCurrentStep }
}
