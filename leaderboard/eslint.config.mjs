import { createRequire } from 'module'
import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

// Read the installed react version so eslint-plugin-react skips its
// detectReactVersion() codepath, which calls the removed
// `context.getFilename()` API and crashes under ESLint v10. Reading from
// react/package.json keeps this in lockstep with whatever react version is
// actually installed (so dependabot bumps to react don't require touching
// this file).
const require = createRequire(import.meta.url)
const reactVersion = require('react/package.json').version

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  { settings: { react: { version: reactVersion } } },
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts', 'server/**']),
])

export default eslintConfig
