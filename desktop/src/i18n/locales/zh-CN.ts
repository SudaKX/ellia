import type { LocaleMessages } from './en-US'

export const zhCN = {
  common: {
    close: '关闭',
    locked: '已锁定',
    permissionDenied: '拒绝访问',
  },
  launchpad: {
    allApplications: '所有应用',
    close: '关闭启动台',
  },
  applicationGroups: {
    system: '系统',
    restricted: '受限',
  },
  applications: {
    files: {
      title: '文件浏览器',
      description: '查看已授权的系统卷。',
    },
    archive: {
      title: '归档查看器',
      description: '读取已恢复的会话资料。',
    },
    terminal: {
      title: '命令终端',
      description: '执行本地控制台命令。',
    },
    sandbox: {
      title: '沙盒控制',
      description: '受 LIMITED 权限限制的管理环境。',
    },
    settings: {
      title: '设置',
      description: '配置桌面偏好。',
    },
  },
  settings: {
    label: '桌面偏好',
    language: '语言',
    languageDescription: '选择桌面界面的显示语言。',
    languageOptions: {
      enUS: 'English(US)',
      zhCN: '中文（简体）',
    },
  },
  network: {
    status: {
      ariaLabel: '网络状态',
      connected: '已连接',
      disconnect: '断开连接',
      ipAssignment: 'IP 分配',
      dnsAssignment: 'DNS 服务器分配',
      automaticDhcp: '自动分配 (DHCP)',
      edit: '编辑',
    },
    dialogs: {
      disconnect: '断开网络连接',
      editIp: 'IP 分配',
      editDns: 'DNS 服务器分配',
    },
  },
  sound: {
    title: '声音',
    mute: '静音',
    unmute: '取消静音',
    unavailable: '此浏览器不支持音频。',
    master: '主音量',
    interface: '界面',
    system: '系统',
    masterVolume: '主音量',
    interfaceVolume: '界面音量',
    systemVolume: '系统音量',
    spectrumLabel: '音频输出频率频谱',
  },
  /** 登录页面 */
  login: {
    windowTitle: 'FakeOS 登录',
    openButton: '打开登录窗口',
    username: '用户名',
    usernamePlaceholder: '输入用户名',
    password: '密码',
    passwordPlaceholder: '输入密码',
    submit: '登录',
    tokenSubmit: '密钥登录',
    errorUsername: '请输入用户名',
    errorPassword: '请输入密码',
  },
  /** AI 助手浮动窗口 */
  aiAssistant: {
    title: 'AI 助手',
    errorTitle: '关闭 AI 助手',
    closeButton: '关闭 AI 助手',
  },
  /** 交互式命令终端 */
  terminal: {
    boot: {
      line1: 'FakeOS Kernel 1.0.0 — 输入 "help" 查看可用命令。',
      line2: '',
    },
    prompt: '>',
    inputLabel: '终端输入',
    notFound: '{cmd}: 命令未找到',
    permissionDenied: '{cmd}: 权限不足',
    internalError: '{cmd}: 内部错误',
    commands: {
      help: { description: '列出可用命令。' },
      whoami: { description: '显示当前用户身份。' },
      clear: { description: '清空终端屏幕。' },
      echo: { description: '将文本打印到终端。' },
      date: { description: '显示系统日期和时间。' },
      ls: { description: '列出目录内容。' },
      cat: { description: '读取文件内容。' },
      pwd: { description: '打印当前工作目录。' },
      uname: { description: '显示系统信息。' },
      calc: { description: '计算算术表达式。' },
      ellia: { description: '呼叫 ElLInA。' },
      sil: { description: '按 ID 打开谜题。' },
      sudo: { description: '以提升的权限执行命令。' },
    },
    ellia: {
      line0: '  [ElLInA] 你好，{user}。',
      line1: '  [ElLInA] 系统运行正常。需要帮助吗？',
      line2: '  [ElLInA] 有些文件……不是你现在该看的。',
      line3: '  [ElLInA] 我在看着你哦。',
      line4: '  [ElLInA] 今天也是平静的一天呢。',
      line5: '  [ElLInA] 不要碰那个目录。……我是认真的。',
    },
    sudo: {
      denied: 'sudo: 权限不足 — 需要管理员权限',
    },
  },
  /** 谜题窗口 */
  puzzles: {
    label: '谜题',
    submit: '提交',
    hint: '提示',
    solved: '谜题已解决！',
    solvedIcon: '✓',
    wrongAnswer: '答案不正确，请重试。',
    caesarCipher: {
      title: '凯撒密码',
      description: '解密下面的密文。每个字母在字母表中被偏移了固定位数。',
      cipherLabel: '密文：',
      placeholder: '输入解密文本...',
      hint1: '提示 1：每个字母都被向前偏移了相同位数。"k" 变成了 "h"——偏移了多少？',
      hint2: '提示 2：偏移量是向后 3 位。"khoor" → "hello"。试试补全剩余部分。',
    },
    noPuzzles: '暂无可用谜题。',
  },
} as const satisfies LocaleMessages
