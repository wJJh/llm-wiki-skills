// LLM Wiki Skills —— DSH 合集插件入口
//
// 把 skills/ 下的每个技能注册为按需加载的 agent skill。
// 新增技能只需放置 skills/<name>/SKILL.md，本文件无需改动。
//
// DSH 文件系统技能发现只扫一层 <root>/<name>/SKILL.md；
// 本合集通过 ctx.skills.register(...) 注册内嵌技能，资源目录指向各技能目录。

import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'dsh-llm-wiki-skills'
export const inject = ['skills']

const packageRoot = dirname(fileURLToPath(import.meta.url))
const skillsRoot = join(packageRoot, 'skills')

/**
 * 解析 SKILL.md 的 YAML frontmatter。
 *
 * 兼容：
 * - CRLF / CR / LF
 * - description: > / | / >- / |- 多行块
 * - 单行普通值、成对引号
 *
 * 嵌套字段（如 metadata）不展开，只保留顶层键；本插件只依赖 name/description/whenToUse。
 *
 * @param {string} raw
 * @returns {{meta: Record<string, string>, body: string}}
 */
export function splitSkillDocument(raw) {
  const text = String(raw).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n')
  if (!text.startsWith('---\n')) return { meta: {}, body: text }

  const lines = text.split('\n')
  if (lines[0].trim() !== '---') return { meta: {}, body: text }

  let closing = -1
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === '---') {
      closing = i
      break
    }
  }
  if (closing < 0) return { meta: {}, body: text }

  const meta = {}
  const metaLines = lines.slice(1, closing)
  for (let i = 0; i < metaLines.length; i += 1) {
    const line = metaLines[i]
    const match = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line)
    if (!match) continue

    const key = match[1]
    let value = match[2].trim()

    if (value === '>' || value === '|' || value === '>-' || value === '|-') {
      const folded = value.startsWith('>')
      const block = []
      let j = i + 1
      while (j < metaLines.length) {
        const next = metaLines[j]
        if (next.trim() === '' || /^\s+/.test(next)) {
          block.push(next.trim())
          j += 1
        } else {
          break
        }
      }
      value = (folded ? block.join(' ') : block.join('\n')).trim()
      i = j - 1
    } else if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1)
    }

    meta[key] = value
  }

  const body = lines.slice(closing + 1).join('\n').replace(/^\n+/, '')
  return { meta, body }
}

/**
 * 发现 skills/ 下所有含 SKILL.md 的直接子目录。
 * @returns {Array<{name: string, dir: string, skillFile: string}>}
 */
export function discoverSkills() {
  if (!existsSync(skillsRoot)) return []

  return readdirSync(skillsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith('.'))
    .map((entry) => {
      const dir = join(skillsRoot, entry.name)
      return { name: entry.name, dir, skillFile: join(dir, 'SKILL.md') }
    })
    .filter((skill) => existsSync(skill.skillFile))
    .sort((a, b) => a.name.localeCompare(b.name))
}

/**
 * 注册全部技能。
 * @param {import('@deepseek-ai/dsh').Context} ctx
 */
export function apply(ctx) {
  const skills = discoverSkills()
  if (skills.length === 0) {
    throw new Error(
      `LLM Wiki Skills: ${skillsRoot} 下没有找到技能。` +
        '每个技能应当是含 SKILL.md 的直接子目录。',
    )
  }

  for (const skill of skills) {
    const { meta, body } = splitSkillDocument(readFileSync(skill.skillFile, 'utf8'))
    const description =
      (meta.description || '').trim() ||
      `（${skill.name}：SKILL.md 缺少 description 字段）`
    const whenToUse = (meta.whenToUse || '').trim()

    ctx.effect(() =>
      ctx.skills.register({
        name: skill.name,
        source: 'bundled',
        description,
        ...(whenToUse ? { whenToUse } : {}),
        content: body,
        resourceBase: { kind: 'directory', path: skill.dir },
      }),
    )
  }
}
