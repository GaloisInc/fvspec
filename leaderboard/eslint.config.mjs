import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Pin React version explicitly so eslint-plugin-react does not invoke its
  // detectReactVersion() codepath, which calls the removed
  // `context.getFilename()` API and crashes under ESLint v10.
  { settings: { react: { version: '19.2.1' } } },
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts', 'server/**']),
])

export default eslintConfig
