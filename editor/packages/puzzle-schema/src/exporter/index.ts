// @ellia/puzzle-schema/exporter — 导出生成器（纯函数，M3 实现）
// 产物（plan-v1.md §6）：
//   puzzles/<module_id>/__init__.py    模板生成：imports、MODULE_ID、_handler、
//                                       code 函数体（自动加 @_handler 装饰器）、
//                                       register() 按固定顺序调用各 Registry
//   puzzles/<module_id>/assets/**      全部资产原样
//   puzzles/<module_id>/assets/file-tree.json  由 file-node 实体生成 manifest
//   puzzles/__init__.py                合并版：deploy_baseline + 本模块幂等合并
//   README.txt                         部署说明
// 导出前不做校验（与方案一致）。

export interface ExportFile {
  /** zip 内路径，如 `puzzles/<module_id>/__init__.py` */
  path: string
  content: string | Uint8Array
}

export interface ExportBundle {
  module_id: string
  files: ExportFile[]
}

function notImplemented(fn: string): never {
  throw new Error(`[puzzle-schema/exporter] ${fn} 尚未实现（M3）`)
}

/** file-node / asset 实体 → file-tree.json manifest 文本（schema_version: 1） */
export function buildFileTreeManifest(
  _moduleId: string,
  _fileTreeNodes: unknown[],
  _assets: unknown[],
): string {
  return notImplemented('buildFileTreeManifest')
}

/** code 实体 → puzzles/<module_id>/__init__.py 文本 */
export function buildModuleInit(
  _moduleId: string,
  _pythonBlocks: unknown[],
  _registrations: unknown[],
): string {
  return notImplemented('buildModuleInit')
}

/**
 * deploy_baseline + 本模块 → 合并版 puzzles/__init__.py（幂等）。
 * baseline 为 null 时降级为 register_all.patch 片段。
 */
export function mergeRegisterAll(_baseline: string | null, _moduleId: string): string {
  return notImplemented('mergeRegisterAll')
}

/** ExportBundle → zip 字节 */
export async function buildExportZip(_bundle: ExportBundle): Promise<Uint8Array> {
  return notImplemented('buildExportZip')
}
