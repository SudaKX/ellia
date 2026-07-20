export const enUS = {
  common: {
    close: 'Close',
    locked: 'Locked',
    permissionDenied: 'Permission denied',
  },
  launchpad: {
    allApplications: 'All applications',
    close: 'Close launchpad',
  },
  applicationGroups: {
    system: 'System',
    restricted: 'Restricted',
  },
  applications: {
    files: {
      title: 'File Explorer',
      description: 'Inspect authorized system volumes.',
    },
    archive: {
      title: 'Archive Viewer',
      description: 'Read recovered session material.',
    },
    terminal: {
      title: 'Command Terminal',
      description: 'Execute local console utilities.',
    },
    sandbox: {
      title: 'Sandbox Control',
      description: 'Restricted administrative environment.',
    },
    settings: {
      title: 'Settings',
      description: 'Configure desktop preferences.',
    },
  },
  settings: {
    label: 'Desktop preferences',
    language: 'Language',
    languageDescription: 'Choose the display language for the desktop interface.',
    languageOptions: {
      enUS: 'English(US)',
      zhCN: '中文（简体）',
    },
  },
  network: {
    status: {
      ariaLabel: 'Network status',
      connected: 'Connected',
      disconnect: 'Disconnect',
      ipAssignment: 'IP assignment',
      dnsAssignment: 'DNS server assignment',
      automaticDhcp: 'Automatic (DHCP)',
      edit: 'Edit',
    },
    dialogs: {
      disconnect: 'Disconnect network',
      editIp: 'IP assignment',
      editDns: 'DNS server assignment',
    },
  },
  sound: {
    title: 'Sound',
    mute: 'Mute audio',
    unmute: 'Unmute audio',
    unavailable: 'Audio is unavailable in this browser.',
    master: 'Master',
    interface: 'Interface',
    system: 'System',
    masterVolume: 'Master volume',
    interfaceVolume: 'Interface volume',
    systemVolume: 'System volume',
    spectrumLabel: 'Audio output frequency spectrum',
  },
} as const

type DeepString<T> = {
  [Key in keyof T]: T[Key] extends Record<string, unknown> ? DeepString<T[Key]> : string
}

export type LocaleMessages = DeepString<typeof enUS>
