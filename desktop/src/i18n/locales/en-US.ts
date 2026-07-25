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
    creative: 'Creative',
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
    ascii: {
      title: 'ASCII Flow',
      description: 'Variable typographic text reflow visualizer.',
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
  /** Login page */
  login: {
    windowTitle: 'FakeOS Login',
    openButton: 'Open login window',
    username: 'Username',
    usernamePlaceholder: 'Enter username',
    password: 'Password',
    passwordPlaceholder: 'Enter password',
    submit: 'Login',
    tokenSubmit: 'Key Login',
    errorUsername: 'Please enter a username',
    errorPassword: 'Please enter a password',
    adminLabel: 'Administrator',
    adminSubmit: 'JDK Trigger Login',
    sessionFound: 'Saved session detected — click "Key Login" to continue',
  },
  /** Authentication gate */
  authGate: {
    failed: 'Authentication Failed',
    redirecting: 'Redirecting to login... ({seconds})',
    skipButton: 'Go Now',
  },
  /** AI Assistant floating window */
  aiAssistant: {
    title: 'AI Assistant',
    errorTitle: 'Close AI Assistant',
    closeButton: 'Close AI Assistant',
  },
  /** Live2D assistant */
  live2d: {
    title: 'Live2D Assistant',
  },
  /** Interactive command terminal */
  terminal: {
    boot: {
      line1: 'FakeOS Kernel 1.0.0 — Type "help" for available commands.',
      line2: '',
    },
    prompt: '>',
    inputLabel: 'Terminal input',
    notFound: '{cmd}: command not found',
    permissionDenied: '{cmd}: PERMISSION DENIED',
    internalError: '{cmd}: internal error',
    commands: {
      help: { description: 'List available commands.' },
      whoami: { description: 'Display current user identity.' },
      clear: { description: 'Clear the terminal screen.' },
      echo: { description: 'Print text to the terminal.' },
      date: { description: 'Display system date and time.' },
      ls: { description: 'List directory contents.' },
      cat: { description: 'Read file contents.' },
      pwd: { description: 'Print working directory.' },
      uname: { description: 'Display system information.' },
      calc: { description: 'Evaluate arithmetic expressions.' },
      ellia: { description: 'Contact ElLInA.' },
      sil: { description: 'Open a puzzle by ID.' },
      sudo: { description: 'Execute command with elevated privileges.' },
      cd: { description: 'Change the current working directory.', usage: 'cd [directory]' },
      exit: { description: 'Close the terminal window.' },
      man: {
        description: 'View command manual.',
        usage: 'man <command>',
        noArg: 'man: please specify a command name.',
      },
    },
    ellia: {
      line0: '  [ElLInA] Hello, {user}.',
      line1: "  [ElLInA] Systems operating normally. Need help?",
      line2: "  [ElLInA] Some files… you shouldn't look at yet.",
      line3: "  [ElLInA] I'm watching over you.",
      line4: '  [ElLInA] Another quiet day today.',
      line5: "  [ElLInA] Don't touch that directory. …I'm serious.",
    },
    sudo: {
      denied: 'sudo: PERMISSION DENIED — administrator privileges required',
    },
  },
  /** Player archive viewer */
  archive: {
    label: 'RECOVERED DATA',
    loading: 'Loading player archive...',
    error: 'Failed to load archive data.',
    retry: 'Retry',
    profile: 'Profile',
    userId: 'User ID',
    privilege: 'Privilege Level',
    registered: 'Registered',
    lastLogin: 'Last Login',
    loginCount: 'Total Logins',
    playtime: 'Play Time',
    playtimeMinutes: '{minutes} minutes',
    playtimeHours: '{hours}h {minutes}m',
    stats: 'Statistics',
    puzzlesCompleted: 'Puzzles Completed',
    puzzlesCompletedText: 'You have completed {count} puzzle(s).',
    noPuzzles: 'No puzzles completed yet.',
    puzzleRecord: '· "{id}" — solved after {attempts} attempt(s), {hints} hint(s) used.',
    achievements: 'Achievements',
    achievementsUnlocked: '{unlocked}/{total} unlocked',
    noAchievements: 'No achievements yet.',
    locked: 'LOCKED',
    unlockedAt: 'Unlocked on {date}',
    /** Achievement definitions */
    achievementList: {
      firstLogin: {
        name: 'First Contact',
        description: 'Log in to the system for the first time.',
      },
      firstPuzzle: {
        name: 'Code Breaker',
        description: 'Solve your first puzzle.',
      },
      threeLogins: {
        name: 'Regular Visitor',
        description: 'Log in 3 times.',
      },
      persistent: {
        name: 'Persistent',
        description: 'Solve 5 puzzles. Keep going!',
      },
    },
  },
  /** Puzzle windows */
  puzzles: {
    label: 'PUZZLE',
    submit: 'Submit',
    hint: 'Hint',
    solved: 'Puzzle solved!',
    solvedIcon: '✓',
    wrongAnswer: 'Incorrect answer. Try again.',
    caesarCipher: {
      title: 'Caesar Cipher',
      description: 'Decrypt the message below. Each letter has been shifted by a fixed number of positions in the alphabet.',
      cipherLabel: 'Cipher:',
      placeholder: 'Enter decrypted text...',
      hint1: 'Hint 1: Every letter has been shifted forward by the same amount. "k" becomes "h" — what is the shift?',
      hint2: 'Hint 2: The shift is 3 positions backward. "khoor" → "hello". Try completing the rest.',
    },
    noPuzzles: 'No puzzles available.',
  },
} as const

type DeepString<T> = {
  [Key in keyof T]: T[Key] extends Record<string, unknown> ? DeepString<T[Key]> : string
}

export type LocaleMessages = DeepString<typeof enUS>
