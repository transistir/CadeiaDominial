const js = require("@eslint/js");
const tsParser = require("@typescript-eslint/parser");
const tsPlugin = require("@typescript-eslint/eslint-plugin");
const globals = require("globals");

module.exports = [
  {
    files: ["eslint.config.js"],
    languageOptions: {
      globals: {
        ...globals.node
      },
      sourceType: "commonjs"
    }
  },
  {
    ignores: ["**/dist/**", "**/build/**", "**/coverage/**", "**/.turbo/**", "**/node_modules/**"]
  },
  js.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module"
      }
    },
    plugins: {
      "@typescript-eslint": tsPlugin
    },
    rules: {
      ...tsPlugin.configs.recommended.rules
    }
  },
  // Test files with vitest globals
  {
    files: ["**/*.test.ts", "**/*.test.tsx", "**/__tests__/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.vitest
      }
    }
  },
  // Web/browser files
  {
    files: ["packages/web/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.browser
      }
    }
  },
  // API files (Node.js)
  {
    files: ["packages/api/**/*.{ts,tsx}"],
    languageOptions: {
      globals: {
        ...globals.node
      }
    }
  }
];
