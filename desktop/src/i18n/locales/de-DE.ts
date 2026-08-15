import type { LocaleMessages } from './en-US'

export const deDE = {
  common: {
    close: 'Schließen',
    locked: 'Gesperrt',
    permissionDenied: 'Zugriff verweigert',
  },
  launchpad: {
    allApplications: 'Alle Anwendungen',
    close: 'Launchpad schließen',
  },
  applicationGroups: {
    system: 'System',
    restricted: 'Eingeschränkt',
    creative: 'Kreativ',
  },
  applications: {
    files: {
      title: 'Datei-Explorer',
      description: 'Autorisierte Systemvolumes untersuchen.',
      previewTitle: 'Dateivorschau',
      cannotOpen: 'Diese Datei kann nicht geöffnet werden.',
      emptyDir: 'Leeres Verzeichnis',
    },
    archive: {
      title: 'Archivbetrachter',
      description: 'Wiederhergestellte Sitzungsdaten lesen.',
    },
    terminal: {
      title: 'Befehlsterminal',
      description: 'Lokale Konsolenbefehle ausführen.',
    },
    sandbox: {
      title: 'Sandbox-Steuerung',
      description: 'Eingeschränkte Verwaltungsumgebung.',
    },
    settings: {
      title: 'Einstellungen',
      description: 'Desktop-Einstellungen konfigurieren.',
    },
    ascii: {
      title: 'ASCII Flow',
      description: 'Variabler typografischer Textumbruch-Visualisierer.',
    },
    browser: {
      title: 'Browser',
      description: 'Das offene Web durchsuchen.',
    },
  },
  /** Browser-App */
  browser: {
    addressPlaceholder: 'URL eingeben',
    go: 'Los',
    deniedTitle: 'ZUGRIFF VERWEIGERT',
    vtbReward: 'Geheimnisvolle Seite gefunden! {amount} VTB wurden gutgeschrieben.',
  },
  /** Texteditor */
  textEditor: {
    title: 'Texteditor',
    save: 'Speichern',
    readMode: 'Lesen',
    editMode: 'Bearbeiten',
    editArea: 'Texteditor-Inhalt',
    modified: 'Geändert',
    decreaseFont: 'Schriftgröße verkleinern',
    increaseFont: 'Schriftgröße vergrößern',
    savePromptTitle: 'Änderungen speichern?',
    savePromptMessage: 'Änderungen an "{name}" speichern?',
    savePromptSave: 'Speichern',
    savePromptDiscard: 'Nicht speichern',
    savePromptCancel: 'Abbrechen',
    permissionTitle: 'Zugriff verweigert',
  },
  /** Story-Dialog (E ↔ Spieler) */
  story: {
    dialog: {
      title: 'Nachricht',
      continue: 'Klicken, um fortzufahren',
      submit: 'Bestätigen',
    },
  },
  settings: {
    label: 'Desktop-Einstellungen',
    language: 'Sprache',
    languageDescription: 'Wählen Sie die Anzeigesprache für die Desktop-Oberfläche.',
    languageOptions: {
      enUS: 'English(US)',
      zhCN: '中文（简体）',
      deDE: 'Deutsch',
      jaJP: '日本語',
      zhTW: '中文（繁體）',
      binary: 'Binary',
    },
    theme: 'Design',
    themeDescription: 'Wählen Sie das visuelle Design für den Desktop.',
    themeOptions: {
      night: 'Nacht',
      day: 'Tag',
      deepBlue: 'Tiefblau',
      parchment: 'Pergament',
      rose: 'Rose',
    },
  },
  network: {
    status: {
      ariaLabel: 'Netzwerkstatus',
      connected: 'Verbunden',
      disconnect: 'Trennen',
      ipAssignment: 'IP-Zuweisung',
      dnsAssignment: 'DNS-Server-Zuweisung',
      automaticDhcp: 'Automatisch (DHCP)',
      edit: 'Bearbeiten',
    },
    dialogs: {
      disconnect: 'Netzwerkverbindung trennen',
      editIp: 'IP-Zuweisung',
      editDns: 'DNS-Server-Zuweisung',
    },
  },
  sound: {
    title: 'Ton',
    mute: 'Stummschalten',
    unmute: 'Stummschaltung aufheben',
    unavailable: 'Audio ist in diesem Browser nicht verfügbar.',
    master: 'Master',
    interface: 'Oberfläche',
    system: 'System',
    masterVolume: 'Master-Lautstärke',
    interfaceVolume: 'Oberflächen-Lautstärke',
    systemVolume: 'System-Lautstärke',
    spectrumLabel: 'Audio-Ausgabe-Frequenzspektrum',
  },
  /** Login-Seite */
  login: {
    windowTitle: 'FakeOS Anmeldung',
    openButton: 'Anmeldefenster öffnen',
    username: 'Benutzername',
    usernamePlaceholder: 'Benutzername eingeben',
    password: 'Passwort',
    passwordPlaceholder: 'Passwort eingeben',
    submit: 'Anmelden',
    tokenSubmit: 'Schlüssel-Anmeldung',
    errorUsername: 'Bitte geben Sie einen Benutzernamen ein',
    errorPassword: 'Bitte geben Sie ein Passwort ein',
    adminLabel: 'Administrator',
    adminSubmit: 'JDK Trigger-Anmeldung',
    sessionFound: 'Gespeicherte Sitzung erkannt — klicken Sie auf "Schlüssel-Anmeldung" um fortzufahren',
  },
  /** Authentifizierungs-Gateway */
  authGate: {
    failed: 'Authentifizierung fehlgeschlagen',
    redirecting: 'Weiterleitung zur Anmeldung... ({seconds})',
    skipButton: 'Jetzt weiter',
  },
  /** KI-Assistent schwebendes Fenster */
  aiAssistant: {
    title: 'KI-Assistent',
    errorTitle: 'KI-Assistent schließen',
    closeButton: 'KI-Assistent schließen',
    lines: {
      0: "I-Ich bin doch gar nicht kitzlig oder so!",
      1: "So ein bisschen Kitzeln macht mir doch...",
      2: "Mmm~! Nimm das, Kitzelangriff!!",
    },
    /** Zeilen beim Klicken des X-Schließen-Buttons (zufällig) */
    closeLines: {
      0: 'Warte nur ab!',
      1: 'Wie kannst du es wagen!',
      2: 'Wie langweilig',
    },
  },
  /** Interaktives Befehlsterminal */
  terminal: {
    boot: {
      line1: 'FakeOS Kernel 1.0.0 — Geben Sie "help" für verfügbare Befehle ein.',
      line2: '',
    },
    prompt: '>',
    inputLabel: 'Terminal-Eingabe',
    notFound: '{cmd}: Befehl nicht gefunden',
    permissionDenied: '{cmd}: ZUGRIFF VERWEIGERT',
    internalError: '{cmd}: Interner Fehler',
    commands: {
      help: { description: 'Verfügbare Befehle auflisten.' },
      whoami: { description: 'Aktuelle Benutzeridentität anzeigen.' },
      clear: { description: 'Terminalbildschirm löschen.' },
      echo: { description: 'Text im Terminal ausgeben.' },
      date: { description: 'Systemdatum und -uhrzeit anzeigen.' },
      ls: { description: 'Verzeichnisinhalt auflisten.' },
      cat: { description: 'Dateiinhalte lesen.' },
      pwd: { description: 'Aktuelles Arbeitsverzeichnis anzeigen.' },
      uname: { description: 'Systeminformationen anzeigen.' },
      calc: { description: 'Arithmetische Ausdrücke auswerten.' },
      ellia: { description: 'ElLInA kontaktieren.' },
      sil: { description: 'Rätsel nach ID öffnen.' },
      sudo: { description: 'Befehl mit erhöhten Rechten ausführen.' },
      cd: { description: 'Aktuelles Arbeitsverzeichnis wechseln.', usage: 'cd [Verzeichnis]' },
      exit: { description: 'Terminalfenster schließen.' },
      man: {
        description: 'Befehlshandbuch anzeigen.',
        usage: 'man <Befehl>',
        noArg: 'man: Bitte geben Sie einen Befehlsnamen an.',
      },
    },
    ellia: {
      line0: '  [ElLInA] Hallo, {user}.',
      line1: '  [ElLInA] Systeme arbeiten normal. Brauchen Sie Hilfe?',
      line2: '  [ElLInA] Einige Dateien… sollten Sie noch nicht ansehen.',
      line3: '  [ElLInA] Ich passe auf Sie auf.',
      line4: '  [ElLInA] Wieder ein ruhiger Tag heute.',
      line5: '  [ElLInA] Fassen Sie dieses Verzeichnis nicht an. …Ich meine es ernst.',
    },
    sudo: {
      denied: 'sudo: ZUGRIFF VERWEIGERT — Administratorrechte erforderlich',
    },
  },
  /** Spielerarchiv-Betrachter */
  archive: {
    label: 'WIEDERHERGESTELLTE DATEN',
    loading: 'Spielerarchiv wird geladen...',
    error: 'Archivdaten konnten nicht geladen werden.',
    retry: 'Wiederholen',
    profile: 'Profil',
    userId: 'Benutzer-ID',
    privilege: 'Berechtigungsstufe',
    registered: 'Registriert',
    lastLogin: 'Letzte Anmeldung',
    loginCount: 'Anmeldungen gesamt',
    playtime: 'Spielzeit',
    playtimeMinutes: '{minutes} Minuten',
    playtimeHours: '{hours} Std. {minutes} Min.',
    stats: 'Statistiken',
    puzzlesCompleted: 'Gelöste Rätsel',
    puzzlesCompletedText: 'Sie haben {count} Rätsel gelöst.',
    noPuzzles: 'Noch keine Rätsel gelöst.',
    puzzleRecord: '· "{id}" — nach {attempts} Versuch(en) gelöst, {hints} Hinweis(e) verwendet.',
    achievements: 'Erfolge',
    achievementsUnlocked: '{unlocked}/{total} freigeschaltet',
    noAchievements: 'Noch keine Erfolge.',
    locked: 'GESPERRT',
    unlockedAt: 'Freigeschaltet am {date}',
    toastTitle: 'Erfolg!',
    /** Erfolgsdefinitionen */
    achievementList: {
      firstLogin: {
        name: 'Erster Kontakt',
        description: 'Melden Sie sich zum ersten Mal im System an.',
      },
      firstPuzzle: {
        name: 'Codeknacker',
        description: 'Lösen Sie Ihr erstes Rätsel.',
      },
      threeLogins: {
        name: 'Stammgast',
        description: 'Melden Sie sich 3 Mal an.',
      },
      persistent: {
        name: 'Beharrlich',
        description: 'Lösen Sie 5 Rätsel. Weiter so!',
      },
      firstContact: {
        name: 'Erstes Mal',
        description: 'Willkommen, willkommen......',
      },
    },
  },
  /** Rätselfenster */
  puzzles: {
    label: 'RÄTSEL',
    submit: 'Absenden',
    hint: 'Hinweis',
    solved: 'Rätsel gelöst!',
    solvedIcon: '✓',
    notFound: 'Rätsel nicht gefunden.',
    imageUnavailable: 'Bild nicht verfügbar.',
    fillLabel: 'Lücke',
    wrongAnswer: 'Falsche Antwort. Bitte versuchen Sie es erneut.',
    caesarCipher: {
      title: 'Caesar-Verschlüsselung',
      description: 'Entschlüsseln Sie die Nachricht unten. Jeder Buchstabe wurde um eine feste Anzahl von Positionen im Alphabet verschoben.',
      cipherLabel: 'Chiffre:',
      placeholder: 'Entschlüsselten Text eingeben...',
      hint1: 'Hinweis 1: Jeder Buchstabe wurde um den gleichen Betrag vorwärts verschoben. "k" wird zu "h" — was ist die Verschiebung?',
      hint2: 'Hinweis 2: Die Verschiebung beträgt 3 Positionen rückwärts. "khoor" → "hello". Versuchen Sie den Rest zu vervollständigen.',
    },
    noPuzzles: 'Keine Rätsel verfügbar.',
  },
  /** Token-Geldbörse (Statusleiste) */
  tokens: {
    label: 'Geldbörse',
    balance: 'Guthaben',
    vtb: 'VTB-Guthaben',
    refresh: 'Aktualisieren',
    error: 'Guthaben nicht verfügbar',
  },
} as const satisfies LocaleMessages
