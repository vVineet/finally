import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // This rule flags the standard "fetch on mount" pattern (calling an
      // async function from a bare useEffect to load initial data), which
      // every data hook in src/hooks uses deliberately and consistently,
      // each already guarding against the stale-closure/unmounted-update
      // case it cares about (a `cancelled` flag, or -- for the plain
      // refresh-on-mount hooks -- a single fetch with no race to guard).
      // Not disabling it project-wide, just for this known-fine pattern.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
