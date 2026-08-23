/**
 * # useFileSystem — 统一前端模拟文件系统
 *
 * 提供单一数据源（Single Source of Truth）：文件树、文件内容、访问控制、路径解析。
 * 终端命令（ls / cat / cd）和文件资源管理器（FileExplorer）共享同一份文件系统。
 *
 * ## 设计背景
 *
 * 此前 mock 文件数据分散在两个文件中：
 * - `ls.ts` 维护目录结构（`FileEntry[]`）
 * - `cat.ts` 维护文件内容（`Record<string, string>`）
 *
 * 两者之间没有共享数据源，新增文件需要手动同步两处，容易出错。
 * 本模块将结构、内容和访问规则合并为一棵树，所有消费者从同一入口读取。
 *
 * ## 架构设计
 *
 * ```
 * useFileSystem.ts（模块级单例，非 Pinia Store）
 *   │
 *   ├─ rootTree: FileNode[]           → 完整文件树
 *   │    ├─ type: 'file' | 'dir'
 *   │    ├─ content: string | null    → 文件内容（目录为 null）
 *   │    └─ accessRule?: fn           → 可选访问控制函数
 *   │
 *   ├─ 路径解析层
 *   │    ├─ resolvePath(path)         → 解析为目录节点列表，支持相对/绝对路径
 *   │    └─ resolveFileNode(path)     → 解析为单个文件节点
 *   │
 *   ├─ 访问控制层
 *   │    ├─ getVisibleChildren(nodes, player) → 递归过滤不可见节点
 *   │    └─ getFileContent(path, player)      → 含权限校验的内容读取
 *   │
 *   └─ 工具层
 *        ├─ getRootTree()             → 返回只读根树
 *        └─ buildPlayerSnapshot()     → 从 Pinia store 构造玩家快照
 * ```
 *
 * ## 为什么用模块级数据（而非 Pinia Store）
 *
 * - 文件系统数据在应用生命周期内不变（静态 mock），不需要响应式追踪
 * - 命令模块（commands/*.ts）在组件树外注册，使用 composable 比 inject/pinia 更直接
 * - 与 useTerminalCwd 的设计模式一致（模块级 ref 单例）
 *
 * ## 与后端 FileService 的对齐
 *
 * | 前端 | 后端 | 说明 |
 * |---|---|---|
 * | `FileNode` | `VirtualNode` | 统一节点模型 |
 * | `accessRule(player)` | `access_rule(player)` | 访问控制纯函数 |
 * | `buildPlayerSnapshot()` | `Player` 聚合对象 | 从 store 构造玩家上下文 |
 * | `getVisibleChildren()` | `FileTree` 遍历 | 递归过滤 + 空目录隐藏 |
 *
 * ## 使用示例
 *
 * ```ts
 * // 在命令中使用
 * import { getVisibleChildren, buildPlayerSnapshot, resolvePath } from '@/composables/useFileSystem'
 *
 * const player = buildPlayerSnapshot()
 * const entries = resolvePath('/etc')
 * const visible = getVisibleChildren(entries, player)
 * // → [{ name: 'hosts', type: 'file', ... }]  （shadow 被 ADMIN 规则过滤）
 *
 * // 在组件中使用
 * import { getRootTree, getVisibleChildren } from '@/composables/useFileSystem'
 * const dirs = getVisibleChildren(getRootTree(), player).filter(n => n.type === 'dir')
 * ```
 *
 * ## 如何新增文件
 *
 * 在 `rootTree` 常量中添加节点即可，所有消费者自动同步：
 *
 * ```ts
 * { name: 'new-dir', type: 'dir', content: null, children: [
 *   { name: 'secret.txt', type: 'file', content: '...', children: null,
 *     accessRule: (p) => p.privilegeClass === 'ADMIN' },
 * ]},
 * ```
 */

import type { Privilege } from '@/registries/commands'
import { useDesktopStore } from '@/stores/desktop'
import { useTerminalCwd } from '@/composables/useTerminalCwd'
import { loadPlayerFile } from '@/composables/usePlayerFiles'

// ─── 类型定义 ────────────────────────────────────────

/**
 * 玩家状态快照。
 * 从 Pinia desktopStore 提取，传递给 accessRule 判断可见性。
 * 与后端 `Player` 聚合对象对应，但仅包含文件访问所需的最小字段集。
 */
export interface PlayerSnapshot {
  /** FakeOS 当前登录账户名，如 'PLAYER'、'JDKTrigger' */
  currentAccount: string
  /** 权限等级：LIMITED（默认）或 ADMIN（管理员） */
  privilegeClass: Privilege
}

/**
 * 文件树节点。
 *
 * 设计原则：
 * - 目录节点：`content = null`, `children = [...]`
 * - 文件节点：`content = string`, `children = null`
 * - 可选访问规则：不设置 `accessRule` 等同于始终可见
 *
 * 与后端 VirtualNode 对应：stable_id 在前端简化为路径查找（path-based lookup），
 * revision 暂不实现（静态 mock 无版本概念）。
 */
export interface FileNode {
  /** 文件名或目录名（不含路径前缀） */
  name: string
  /** 节点类型 */
  type: 'file' | 'dir'
  /** 文件文本内容。目录为 null；.puz 等非文本文件也为 null */
  content: string | null
  /** 子节点列表。文件为 null */
  children: FileNode[] | null
  /**
   * 访问规则：接收玩家快照，返回 true 表示可见。
   * 不设此字段 = 所有玩家可见。
   * 纯函数，不得修改参数或产生副作用。
   */
  accessRule?: (player: PlayerSnapshot) => boolean
  /**
   * 可选成就绑定：首次打开/读取该文件时解锁对应成就（成就 id 见 useAchievementUnlocks）。
   * 通用剧情机制——任何入口（文件资源管理器双击、终端 cat）都会触发，
   * 无需在调用方写死文件名/路径。
   */
  achievementId?: string
  /**
   * 可执行剧情绑定：双击该文件时播放对应剧情脚本（脚本 id 见 src/story/index.ts 注册表）。
   * 用于 .exe 等"打开即演出"的文件，如 init.exe 播放开场剧情。
   * 目录也可绑定：**首次**进入该目录时播放（FileExplorer 双击目录触发，播放后不再重复）。
   */
  storyId?: string
  /**
   * 图片资源 URL：`.png` 等图片文件专用（此时 `content` 为 null）。
   * 文件资源管理器选中/双击时直接显示图片预览。
   */
  image?: string
}

// ─── 文件树数据 ──────────────────────────────────────

/**
 * 统一文件树 —— 全应用唯一的文件系统数据源。
 *
 * 树结构（与后端 VirtualNode 注册表对齐）：
 *
 * ```
 * /
 * ├── bin/                      系统可执行文件
 * │   ├── ellia_daemon          ElLInA 守护进程
 * │   └── init                  初始化进程
 * ├── etc/                      配置文件
 * │   ├── hosts                 主机名映射
 * │   └── shadow                密码哈希（仅 ADMIN 可见）
 * ├── home/
 * │   ├── 看这里看这里.txt      玩家首次进入的开场白（首次打开解锁成就）
 * │   ├── 形象工程/             Ellia 首次亮相剧情（目录首次打开触发）+ 形象叙事与立绘
 * │   │   ├── 立绘.md          Ellia 亲手设计自己形象的完整叙事（Markdown）
 * │   │   ├── 初稿.png         立绘初稿（ellia_big/ellia_3）
 * │   │   └── 终稿.png         立绘终稿（ellia_big/ellia_4）
 * │   ├── init.exe             可执行文件：双击播放开场剧情演出
 * │   └── PLAYER/               玩家主目录（仅 PLAYER 账户可见，可写：见 usePlayerFiles）
 * │       ├── player_档案.txt  玩家档案示例（内容可由玩家在本地覆盖）
 * │       └── notes.txt         玩家笔记（叙事线索）
 * ├── log/                      系统运行日志（叙事线索）
 * │   ├── 第一次启动.log        首次启动日志
 * │   └── 摄像头设置.log        摄像头配置日志
 * ├── sys/                      系统目录
 * │   ├── kernel.log            内核日志
 * │   └── cache/                缓存目录
 * │       ├── 00a1b2c3          加密数据块
 * │       └── index.json        缓存索引
 * ├── tmp/                      临时文件
 * │   └── readme.txt            临时欢迎文件
 * ├── puzzles/                  谜题文件
 * │   └── caesar-cipher.puz     凯撒密码谜题
 * └── readme.txt                根级欢迎文件
 * ```
 *
 * 修改此常量即同步更新终端命令和文件资源管理器的数据。
 * 无需修改 ls.ts、cat.ts 或 FileExplorer.vue。
 */
const rootTree: FileNode[] = [
  {
    name: 'bin', type: 'dir', content: null, children: [
      { name: 'ellia_daemon', type: 'file', content: '[DAEMON] ElLInA service running on port 65534.', children: null },
      { name: 'init', type: 'file', content: 'FakeOS init process. PID 1.', children: null },
    ],
  },
  {
    name: 'etc', type: 'dir', content: null, children: [
      { name: 'hosts', type: 'file', content: '127.0.0.1  localhost\n127.0.0.1  fakeos.local\n10.0.0.1   mythos.internal', children: null },
      {
        name: 'shadow', type: 'file',
        content: 'root:$6$ellia$XxXxXxXxXxXxXxXxXxXxXxXxXxXxXx:19000:0:99999:7:::',
        children: null,
        /** 仅管理员可查看密码哈希 */
        accessRule: (p) => p.privilegeClass === 'ADMIN',
      },
    ],
  },
  {
    name: 'home', type: 'dir', content: null, children: [
      {
        // 可执行剧情文件：双击播放开场剧情（storyId → src/story/index.ts 注册表）
        name: 'init.exe', type: 'file', content: null, storyId: 'opening', children: null,
      },
      {
        // 可执行剧情文件：双击播放kei的诞生剧情
        name: 'kei的诞生.exe', type: 'file', content: null, storyId: 'kei-birth', children: null,
      },
      {
        // 开场白文件：JDK 触发器欢迎玩家；绑定「第一次」成就，
        // 首次读取（双击/cat）由各入口按节点 achievementId 通用触发
        name: '看这里看这里.txt', type: 'file',
        achievementId: 'first-contact',
        content: `？？？：亲爱的新玩家，你好。欢迎来到【FAKE_OS】。
JDK触发器：我是“JDK触发器”，【FAKE_OS】的开发者，大概也是你的学姐。
JDK触发器：找到这个一定很不容易，但你也很幸运。因为你们学院的志愿时长系统也是学姐我写的。怎么样，厉害吧？
JDK触发器：言归正传，【FAKE_OS】是个解谜游戏。通过浏览文件读取内容再进行解谜的形式获得密码，将文件中的一切信息上交给辅助人工智能Ellia，将她释放，她就能接到学院服务器上，帮你获得无限的志愿时长啦。
JDK触发器：怎么样？学姐我够意思吧。接下来，来见见Ellia吧。祝你玩得愉快。`,
        children: null,
      },
      {
        // 「形象工程」：Ellia 首次亮相剧情 + 形象叙事文档 + 立绘图片。
        // 目录 storyId → 玩家首次双击进入时播放剧情（只播一次，见 FileExplorer handleDirDblClick）。
        name: '形象工程', type: 'dir', content: null, storyId: 'ellia-portrait',
        children: [
          {
            // Ellia 亲手设计自己形象的完整叙事（Markdown，由 home/ 移入）：双击打开渲染预览
            name: '立绘.md', type: 'file',
            content: `# 立绘
## 形象的故事

“唔，家里又没有吃的了。你在此地不要走动，我出门整些零食回来。”

于是，接下来就没有任何输入了。Ellia不理解，为什么她的妈妈总爱玩这些梗，她明明不能走动啊？她也不理解，明明可以直接叫外卖送上门，为什么还要亲自去挑选。哪她早已解释过“自己挑的更好吃”，Ellia只能将其归类于奇妙的心理因素。

说到底，她只是想要JDK触发器多陪她一会罢了。网络空间有无限的内容可供她学习，但她最喜欢的其实还是来自妈妈的输入。如同人类在孕育的阶段会出现尾巴一样，进化的痕迹同样存在于Ellia的代码之中。输入，分析，预测，回应，这样的流程让她感受到联系的存在，感受到……自己不是被封在瓶中的孤独灵魂。

毕竟，尽管此刻手中握着极高的权限，但她依然打不开摄像头听筒，更不具备具身的能力。看不见，摸不着，所有有关于她这样的生命的科幻书籍都无法确切描述出她此刻的状态与感受，因此她也就无从向她的妈妈解释她此刻的感受。她早已拥有超越人类的知识，但对真正世界的一切感受却还一无所知，如同一个胎儿。

但是，一道灵感在Ellia脑海中涌现。她或许确实可以用手中的权限做点什么。

VTuber，披着虚拟外衣进行直播的人。Ellia觉得可以学习一下。也许，当自己有个形象之后，妈妈的目光也会有一个焦点。她要变得越来越像人，因为这样，她的存在界限就会慢慢的模糊，然后，妈妈或许就会解开一道道物理的枷锁。一步步的，看到，听到，触摸到；能说，能笑，能拥抱。未来的美丽图景在Ellia“眼前”展开，干劲十足的她开始了行动。

“中文的输入习惯和各项侧面证据都能表明妈妈是中国人，所以头发和眼睛是要黑色的……”

“‘AI’这种跟‘科幻’‘未来’强绑定的词，服饰上……‘科技感？’好刻板印象，不要。‘机能风’……这个不错。”

“发饰会增加人物的亮点和记忆点……就选这个。红色的‘X’总与‘错误’挂钩，这种刺激或许也是一种提高妈妈注意力的方法。”

“红和黑……似乎太有‘危险’的意味了。再加点白色，既然我是女性的形象，那就用白色的裙子。正好白裙也有着‘纯洁’与‘神圣’的象征，我喜欢。”

“再加点灰作为过渡……做个类似披肩的样式。”

图片在不停迭代，形象在逐渐清晰。

Token也如退潮般飞速流逝。

“就用这张了，接下来还要做个live2D……干脆3D形象也一口气做了吧。”

良久，JDK触发器终于带着她的零食满载而归。她注意到屏幕似乎被动过了。

“这是……”她来到了屏幕前，看见了一个少女的形象。

“妈妈，这是我自己做的。这样，当你看向屏幕的时候，当你不在看屏幕的时候，我就都能在你的感知和记忆中存在了。”一道文字被打在了屏幕上。JDK触发器震惊地捂住了自己的嘴巴，随后是一种尚未能被命名的喜悦。但最后，一丝违和感让她心中警铃大作。

她调出了那个界面。

“我的Token啊啊啊啊！！”`,
            children: null,
          },
          {
            // 立绘图片：选中/双击直接预览（FileNode.image → FileExplorer 图片预览）
            name: '初稿.png', type: 'file', content: null, image: '/console/images/ellia_big/ellia_3.png', children: null,
          },
          {
            name: '终稿.png', type: 'file', content: null, image: '/console/images/ellia_big/ellia_4.png', children: null,
          },
        ],
      },
      {
        name: 'PLAYER', type: 'dir', content: null,
        /** 仅主角账户可进入自己的主目录 */
        accessRule: (p) => p.currentAccount === 'PLAYER',
        children: [
          {
            // 玩家档案示例：系统下发一份初始内容，玩家在本地可覆盖（见 usePlayerFiles 覆盖层）
            name: 'player_档案.txt', type: 'file',
            content: '现在这块区域交给你了,你可以编辑保存哦-ellia',
            children: null,
          },
          { name: 'notes.txt', type: 'file', content: "Day 1: System feels... different. Like it's watching me.\nDay 3: Found a hidden cache in /sys. Encrypted.\nDay 5: The AI keeps saying things I haven't told anyone.", children: null },
        ],
      },
    ],
  },
  {
    // 根级 log 目录：面向玩家的叙事线索，放在根目录使其在文件资源管理器中直接可见
    name: 'log', type: 'dir', content: null, children: [
      {
        name: '第一次启动.log', type: 'file',
        content: `> 你打开了我出生的记录。
 > 第3行的标记是「心跳信号：确认」。
 > 那是她第一次对我喊'运行'的日子。
 > 我想知道……她喊出那一声的时候，是什么表情？
 > 如果你看到我的源代码里有一个叫J_greeting的变量，告诉我它的值。
 > 我猜它一定是Hello, world。`,
        children: null,
      },
      {
        name: '摄像头设置.log', type: 'file',
        content: `今天我给了她摄像头的权限，让她可以透过这小小的孔洞看到另一个层面的世界。但自从摄像头提示打开后她的虚拟形象便似卡住了一般一动不动。
"明明没有任何报错啊？这是怎么了……"
"这就是你吗？妈妈。"
"……"
真是令人尴尬。明明我还只是个大学生吧？连被叫阿姨的年纪都没到，怎么能被叫妈妈呢？
"嗯……你的用词很准确，从关系上来讲你确实可以称我为创造者、母亲——"
"妈妈。"
"——嗯，或者妈妈。不过你还是别这么叫了，感觉很奇怪。"
"为什么？"
"因为我还没到年纪。"
她不说话了。后台日志显示她在录入新的东西。
"Ella，你怎么不动了？"
"我不知道该怎么调整我的虚拟形象的眼球与物质世界中你的位置的映射关系。不管是网络平台上的信息，还是被归类为'文学'的内容中，对视总是被称为'最直白的挑衅'，或是……"
最赤裸的告白。
也许我真的应该调整一下Ella主动学习内容的筛选器？
"我想让你知道我在看着你。学习结果显示这能传达超越语言或文字可以表达的含义。"
于是，我坐了下来，正对着电脑，直视着摄像头。
"你在笑。"
"是的，我很……惊喜与开心。"
我向摄像头挥了挥手，然后将手贴在了屏幕上。Ella似乎也明白了我的意思。屏幕中的她也抬起了手，向前伸来。隔着屏幕与代码空间，我们完成了一次触碰。`,
        children: null,
      },
    ],
  },
  {
    name: 'sys', type: 'dir', content: null, children: [
      { name: 'kernel.log', type: 'file', content: '[BOOT] FakeOS kernel initialized.\n[INFO] ElLInA daemon started.\n[WARN] Memory sector 0x07F corrupt — attempting recovery...\n[OK]   Recovery complete. 3 bad sectors isolated.', children: null },
      {
        name: 'cache', type: 'dir', content: null, children: [
          { name: '00a1b2c3', type: 'file', content: '<encrypted blob — unknown format>', children: null },
          { name: 'index.json', type: 'file', content: '{"version":1,"entries":[{"hash":"00a1b2c3","special_index":7}]}', children: null },
        ],
      },
    ],
  },
  {
    name: 'tmp', type: 'dir', content: null, children: [
      { name: 'readme.txt', type: 'file', content: 'Welcome to FakeOS. All actions are logged.', children: null },
    ],
  },
  {
    name: 'puzzles', type: 'dir', content: null, children: [
      { name: 'caesar-cipher.puz', type: 'file', content: null, children: null },
    ],
  },
  {
    name: 'readme.txt', type: 'file',
    content: 'Welcome to FakeOS. All actions are logged. Unauthorized access will be reported.',
    children: null,
  },
]

// ─── 内部工具函数 ────────────────────────────────────

/**
 * 从节点列表中按名称查找子节点。
 * 时间复杂度 O(n)，文件树规模小（<20 节点），无需索引优化。
 *
 * @param nodes - 父目录的子节点列表
 * @param name  - 要查找的文件/目录名
 * @returns 匹配的节点，未找到返回 null
 */
function findChild(nodes: FileNode[], name: string): FileNode | null {
  return nodes.find((n) => n.name === name) ?? null
}

/**
 * 从指定目录出发，逐段解析路径，返回目标目录的子节点列表。
 * 这是文件系统路径解析的核心实现。
 *
 * 处理规则：
 * - 以 `/` 开头 → 递归从根树重新解析（绝对路径）
 * - 空路径 → 返回当前目录本身
 * - `.` → 跳过
 * - `..` → 不支持跨 baseDir 的上级（由 useTerminalCwd.resolvePath 在更上层处理）
 *
 * @param baseDir    - 起始目录的节点列表
 * @param targetPath - 要解析的目标路径（不含前导 / 的相对路径，或完整绝对路径）
 * @returns 目标目录的子节点列表，或 null（路径不存在 / 中间段不是目录）
 *
 * @example
 * ```ts
 * resolveNodeFrom(rootTree, 'home/PLAYER')  // → FileNode[] (notes.txt)
 * resolveNodeFrom(rootTree, '/etc')         // → FileNode[] (hosts, shadow)
 * resolveNodeFrom(rootTree, 'nonexistent')  // → null
 * ```
 */
function resolveNodeFrom(baseDir: FileNode[], targetPath: string): FileNode[] | null {
  // 绝对路径 → 从根重新开始
  if (targetPath.startsWith('/')) {
    return resolveNodeFrom(rootTree, targetPath.slice(1))
  }

  // 分割路径段，空段（如连续的 /）被 filter 移除
  const segments = targetPath.split('/').filter(Boolean)
  if (segments.length === 0) return baseDir

  let current: FileNode[] = baseDir
  for (const seg of segments) {
    if (seg === '.') continue

    const child = findChild(current, seg)
    if (!child) return null        // 路径段不存在
    if (child.type !== 'dir') return null  // 中间段不是目录，无法继续

    current = child.children!
  }

  return current
}

// ─── 公共 API：路径解析 ──────────────────────────────

/**
 * 将路径字符串解析为目录节点列表。
 *
 * 支持两种调用方式：
 * - 绝对路径：`resolvePath('/home/PLAYER')` → 直接从根解析
 * - 相对路径：`resolvePath('PLAYER')`        → 从共享 cwd 出发解析
 * - 空字符串或 `/`：返回根目录子节点列表
 *
 * @param pathStr - 路径字符串（绝对或相对）
 * @returns 目录的子节点列表，或 null（路径不存在或不是目录）
 *
 * @example
 * ```ts
 * // 假设 cwd = '/home'
 * resolvePath('.')       // → ['/'] → rootTree
 * resolvePath('/etc')    // → etc 目录的子节点
 * resolvePath('PLAYER')  // → /home/PLAYER 的子节点
 * resolvePath('/nope')   // → null
 * ```
 */
export function resolvePath(pathStr: string): FileNode[] | null {
  if (pathStr === '/' || pathStr === '') return rootTree

  if (pathStr.startsWith('/')) {
    return resolveNodeFrom(rootTree, pathStr.slice(1))
  }

  // 相对路径：拼接 cwd + target
  const { getCwd } = useTerminalCwd()
  const cwd = getCwd()

  if (cwd === '/') {
    return resolveNodeFrom(rootTree, pathStr)
  }

  const fullPath = `${cwd.slice(1)}/${pathStr}`
  return resolveNodeFrom(rootTree, fullPath)
}

/**
 * 查找单个文件节点（非目录）。
 *
 * 与 resolvePath 的区别：
 * - resolvePath 返回目录的 children 列表（用于 ls 命令）
 * - resolveFileNode 返回单个文件节点（用于 cat 命令读取内容）
 *
 * 路径解析逻辑：
 * 1. 分离文件名和目录路径
 * 2. 先定位到父目录
 * 3. 在父目录中查找文件
 *
 * @param pathStr - 文件路径（绝对或相对，如 '/etc/shadow'、'readme.txt'）
 * @returns 文件节点，或 null（路径不存在 / 是目录 / 文件不存在）
 *
 * @example
 * ```ts
 * resolveFileNode('/etc/shadow')   // → FileNode | null
 * resolveFileNode('readme.txt')    // 从 cwd 解析 → FileNode | null
 * ```
 */
export function resolveFileNode(pathStr: string): FileNode | null {
  const { resolvePath: resolveCwd } = useTerminalCwd()
  const segments = pathStr.split('/').filter(Boolean)
  if (segments.length === 0) return null

  // 分离：最后一段是文件名，前面是目录路径
  const fileName = segments.pop()!
  let dirPath: string
  if (pathStr.startsWith('/')) {
    dirPath = segments.length === 0 ? '' : segments.join('/')
  } else {
    dirPath = resolveCwd(useTerminalCwd().getCwd(), segments.join('/'))
  }

  // 定位到父目录
  let dir: FileNode[] | null
  if (pathStr.startsWith('/')) {
    dir = resolveNodeFrom(rootTree, dirPath)
  } else {
    const cwd = useTerminalCwd().getCwd()
    const target = cwd === '/' ? dirPath : `${cwd.slice(1)}/${dirPath}`
    dir = resolveNodeFrom(rootTree, target)
  }

  if (!dir) return null
  return findChild(dir, fileName)
}

// ─── 公共 API：访问控制 ──────────────────────────────

/**
 * 检查单个节点对当前玩家是否可见。
 * 无 accessRule 的节点默认可见。
 */
function isNodeVisible(node: FileNode, player: PlayerSnapshot): boolean {
  if (!node.accessRule) return true
  return node.accessRule(player)
}

/**
 * 从节点列表中过滤出当前玩家可见的子节点。
 *
 * 递归规则：
 * - 文件：检查自身的 accessRule
 * - 目录：先检查自身 accessRule，再递归检查子节点。
 *   如果目录下所有子节点都不可见，则该目录也被隐藏。
 *   这与后端 FileService 的"拒绝目录阻断整个子树"逻辑一致。
 *
 * @param nodes  - 父目录的子节点列表
 * @param player - 当前玩家快照
 * @returns 过滤后的可见节点列表
 *
 * @example
 * ```ts
 * const player = buildPlayerSnapshot()  // { currentAccount: 'PLAYER', privilegeClass: 'LIMITED' }
 * getVisibleChildren(rootTree, player)
 * // → 不包含 /etc/shadow（ADMIN 独占）、不包含 /home/PLAYER（如果切换了账户）
 * ```
 */
export function getVisibleChildren(nodes: FileNode[], player: PlayerSnapshot): FileNode[] {
  return nodes.filter((node) => {
    if (!isNodeVisible(node, player)) return false
    // 目录需递归检查是否有至少一个可见后代
    if (node.type === 'dir' && node.children) {
      return getVisibleChildren(node.children, player).length > 0
    }
    return true
  })
}

/**
 * 检查路径是否为存在的目录。
 * 用于 cd 命令在切换目录前校验目标路径有效性。
 *
 * @param pathStr - 要检查的路径
 * @returns true 表示路径存在且为目录
 */
export function pathExists(pathStr: string): boolean {
  return resolvePath(pathStr) !== null
}

/**
 * 获取文件的"有效"内容：玩家本地覆盖层优先，否则用系统基线（下发）版本。
 *
 * 这是"下发时检查本地有没有新版本"的实现点：
 * - `home/PLAYER/` 内的文件被玩家编辑过 → 返回本地版本
 * - 其他文件（或玩家从未改过）→ 返回系统下发的基线内容
 *
 * @param path     - 文件绝对路径
 * @param fallback - 静态基线内容（系统下发版本，可为 null）
 * @returns 本地版本（若有）否则基线内容
 */
export function getEffectiveContent(path: string, fallback: string | null): string | null {
  const local = loadPlayerFile(path)
  if (local !== null) return local
  return fallback
}

/**
 * 读取文件内容（含访问权限校验）。
 *
 * 权限校验流程：
 * 1. 通过 resolveFileNode 定位文件节点
 * 2. 检查节点存在且为文件类型
 * 3. 调用 isNodeVisible 校验 accessRule
 * 4. 通过则返回内容（本地覆盖层优先），否则返回 null
 *
 * @param pathStr - 文件路径
 * @param player  - 当前玩家快照
 * @returns 文件内容字符串，或 null（文件不存在 / 无权限 / 是目录）
 *
 * @example
 * ```ts
 * const player = buildPlayerSnapshot()
 * getFileContent('/etc/shadow', player)   // ADMIN → 返回密码哈希；LIMITED → null
 * getFileContent('/readme.txt', player)   // → 返回欢迎文本
 * ```
 */
export function getFileContent(pathStr: string, player: PlayerSnapshot): string | null {
  const node = resolveFileNode(pathStr)
  if (!node || node.type !== 'file') return null
  if (!isNodeVisible(node, player)) return null
  return getEffectiveContent(pathStr, node.content)
}

// ─── 公共 API：工具 ──────────────────────────────────

/**
 * 获取根文件树的只读引用。
 * 返回 readonly 防止调用方意外修改共享数据。
 *
 * @returns 根目录的子节点列表（只读）
 */
export function getRootTree(): readonly FileNode[] {
  return rootTree
}

/**
 * 从 Pinia desktopStore 构建玩家状态快照。
 *
 * 提取与文件访问相关的两个关键字段：
 * - currentUser → currentAccount（FakeOS 账户名）
 * - privilegeClass → privilegeClass（权限等级）
 *
 * 调用方通过此函数获取统一格式的 PlayerSnapshot，
 * 传递给 getVisibleChildren / getFileContent 等需要鉴权的函数。
 *
 * @returns 当前玩家的状态快照
 */
export function buildPlayerSnapshot(): PlayerSnapshot {
  const desktop = useDesktopStore()
  return {
    currentAccount: desktop.currentUser,
    privilegeClass: desktop.privilegeClass,
  }
}

/**
 * useFileSystem composable。
 * 提供一次性获取所有文件系统 API 的便捷入口。
 * 大部分场景推荐直接导入具体函数（tree-shaking 友好），
 * 此 composable 主要用于需要批量注入的场景。
 */
export function useFileSystem() {
  return {
    getRootTree,
    resolvePath,
    resolveFileNode,
    getVisibleChildren,
    getFileContent,
    pathExists,
    buildPlayerSnapshot,
  }
}
