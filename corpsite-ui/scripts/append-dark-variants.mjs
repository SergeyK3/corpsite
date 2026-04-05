/**
 * Append Tailwind `dark:` counterparts for zinc-based light theme classes.
 * Run once from corpsite-ui: node scripts/append-dark-variants.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");

const SKIP_FILES = new Set(["ThemeControl.tsx"]);

/** Prefix: do not match hover:, dark:, etc. */
const P = String.raw`(?<![\w:/])`;

const replacements = [
  [/placeholder:text-zinc-400/g, "placeholder:text-zinc-400 dark:placeholder:text-zinc-500"],

  [/hover:bg-zinc-200\/80/g, "hover:bg-zinc-200/80 dark:hover:bg-zinc-800/80"],
  [/hover:bg-zinc-200\/50/g, "hover:bg-zinc-200/50 dark:hover:bg-zinc-800/50"],
  [/hover:bg-zinc-200/g, "hover:bg-zinc-200 dark:hover:bg-zinc-700"],
  [/hover:bg-zinc-100/g, "hover:bg-zinc-100 dark:hover:bg-zinc-800"],
  [/hover:border-zinc-300/g, "hover:border-zinc-300 dark:hover:border-zinc-600"],
  [/hover:border-zinc-200/g, "hover:border-zinc-200 dark:hover:border-zinc-700"],
  [/hover:text-zinc-800/g, "hover:text-zinc-800 dark:hover:text-zinc-200"],

  [/bg-zinc-600\/35/g, "bg-zinc-600/35 dark:bg-black/50"],
  [/bg-black\/30/g, "bg-black/30 dark:bg-black/55"],

  [/bg-white\/60/g, "bg-white/60 dark:bg-zinc-900/60"],
  [/bg-white\/50/g, "bg-white/50 dark:bg-zinc-900/50"],
  [/bg-zinc-100\/30/g, "bg-zinc-100/30 dark:bg-zinc-900/30"],
  [/bg-zinc-200\/80/g, "bg-zinc-200/80 dark:bg-zinc-800/80"],
  [/bg-zinc-200\/60/g, "bg-zinc-200/60 dark:bg-zinc-800/60"],

  [/border-red-300/g, "border-red-300 dark:border-red-800"],
  [/border-red-200/g, "border-red-200 dark:border-red-900/55"],
  [/bg-red-50/g, "bg-red-50 dark:bg-red-950/35"],
  [/text-red-800/g, "text-red-800 dark:text-red-200"],
  [/text-red-700/g, "text-red-700 dark:text-red-300"],

  [/border-emerald-200/g, "border-emerald-200 dark:border-emerald-800"],
  [/bg-emerald-50/g, "bg-emerald-50 dark:bg-emerald-950/30"],
  [/text-emerald-800/g, "text-emerald-800 dark:text-emerald-200"],

  [/border-amber-200/g, "border-amber-200 dark:border-amber-800"],
  [/bg-amber-50/g, "bg-amber-50 dark:bg-amber-950/30"],
  [/text-amber-900/g, "text-amber-900 dark:text-amber-200"],

  [/divide-zinc-200/g, "divide-zinc-200 dark:divide-zinc-800"],

  [new RegExp(`${P}(border-zinc-400)`, "g"), "$1 dark:border-zinc-600"],
  [new RegExp(`${P}(border-zinc-300)`, "g"), "$1 dark:border-zinc-700"],
  [new RegExp(`${P}(border-zinc-200)`, "g"), "$1 dark:border-zinc-800"],

  [new RegExp(`${P}(bg-zinc-50)(?!\\/)`, "g"), "$1 dark:bg-zinc-950"],
  [new RegExp(`${P}(bg-zinc-100)(?!\\/)`, "g"), "$1 dark:bg-zinc-900"],
  [new RegExp(`${P}(bg-zinc-200)(?!\\/)`, "g"), "$1 dark:bg-zinc-800"],
  [new RegExp(`${P}(bg-white)(?!\\/)`, "g"), "$1 dark:bg-zinc-950"],

  [new RegExp(`${P}(text-zinc-900)(?!\\/)`, "g"), "$1 dark:text-zinc-50"],
  [new RegExp(`${P}(text-zinc-800)(?!\\/)`, "g"), "$1 dark:text-zinc-200"],
  [new RegExp(`${P}(text-zinc-700)(?!\\/)`, "g"), "$1 dark:text-zinc-300"],
  [new RegExp(`${P}(text-zinc-600)(?!\\/)`, "g"), "$1 dark:text-zinc-400"],

  [new RegExp(`${P}(text-blue-600)(?!\\/)`, "g"), "$1 dark:text-blue-400"],

  [new RegExp(`${P}(ring-zinc-200)(?!\\/)`, "g"), "$1 dark:ring-zinc-800"],
  [new RegExp(`${P}(ring-zinc-300)(?!\\/)`, "g"), "$1 dark:ring-zinc-700"],
];

function walkTsx(dir, files = []) {
  if (!fs.existsSync(dir)) return files;
  for (const name of fs.readdirSync(dir)) {
    const p = path.join(dir, name);
    const st = fs.statSync(p);
    if (st.isDirectory()) walkTsx(p, files);
    else if (name.endsWith(".tsx")) files.push(p);
  }
  return files;
}

const dirs = [path.join(root, "app"), path.join(root, "components")];
let changed = 0;
for (const dir of dirs) {
  for (const file of walkTsx(dir)) {
    if (SKIP_FILES.has(path.basename(file))) continue;
    let s = fs.readFileSync(file, "utf8");
    const orig = s;
    for (const [re, to] of replacements) {
      s = s.replace(re, to);
    }
    if (s !== orig) {
      fs.writeFileSync(file, s, "utf8");
      changed++;
      console.log("updated", path.relative(root, file));
    }
  }
}
console.log("files changed:", changed);
