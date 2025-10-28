import { execa } from 'execa'

export async function run(
  cmd: string,
  args: string[],
  opts: {
    cwd?: string
    env?: Record<string, string>
    timeoutSec?: number
    pipe?: boolean
  } = {}
): Promise<{ exitCode: number; log: string }> {
  const subprocess = execa(cmd, args, {
    cwd: opts.cwd,
    env: opts.env,
    timeout: (opts.timeoutSec ?? 0) * 1000 || undefined,
    all: true,
  })
  const { exitCode, all } = await subprocess
  return { exitCode: exitCode ?? 0, log: all ?? '' }
}
