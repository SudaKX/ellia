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
} as const satisfies LocaleMessages
