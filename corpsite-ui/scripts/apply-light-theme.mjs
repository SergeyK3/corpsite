/**
 * One-off bulk replace: dark zinc UI -> light theme classes.
 * Run from corpsite-ui: node scripts/apply-light-theme.mjs
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");

const replacements = [
  [/border-zinc-600 bg-zinc-900 text-zinc-100/g, "border-zinc-400 bg-zinc-200 text-zinc-900"],

  [/bg-\[#050816\]/g, "bg-white"],
  [/bg-\[#04070f\]/g, "bg-zinc-50"],
  [/bg-white\/\[0\.03\]/g, "bg-zinc-100"],
  [/hover:bg-white\/\[0\.02\]/g, "hover:bg-zinc-100"],

  [/bg-zinc-950\/40/g, "bg-zinc-100"],
  [/bg-zinc-950\/30/g, "bg-zinc-50"],
  [/bg-zinc-950\/20/g, "bg-zinc-50"],
  [/bg-zinc-950/g, "bg-white"],

  [/bg-zinc-900 text-zinc-100/g, "bg-zinc-200 text-zinc-900"],
  [/text-zinc-300 hover:bg-zinc-900\/60/g, "text-zinc-700 hover:bg-zinc-200"],

  [/hover:bg-zinc-900\/60/g, "hover:bg-zinc-200"],
  [/bg-zinc-900\/60/g, "bg-zinc-200"],
  [/bg-zinc-900\/40/g, "bg-zinc-100"],
  [/hover:bg-zinc-900/g, "hover:bg-zinc-200"],
  [/bg-zinc-900/g, "bg-zinc-100"],

  [/bg-zinc-800/g, "bg-zinc-200"],

  [/border-zinc-800/g, "border-zinc-200"],
  [/border-zinc-700/g, "border-zinc-300"],
  [/border-zinc-600/g, "border-zinc-400"],
  [/focus:border-zinc-600/g, "focus:border-zinc-400"],

  [/text-zinc-100/g, "text-zinc-900"],
  [/text-zinc-200/g, "text-zinc-800"],
  [/text-zinc-300/g, "text-zinc-700"],
  [/text-zinc-400/g, "text-zinc-600"],
  [/text-zinc-500/g, "text-zinc-600"],

  [/placeholder:text-zinc-500/g, "placeholder:text-zinc-400"],

  [/border-red-900\/60/g, "border-red-200"],
  [/bg-red-950\/40/g, "bg-red-50"],
  [/bg-red-950\/30/g, "bg-red-50"],
  [/bg-red-950\/20/g, "bg-red-50"],
  [/hover:bg-red-950\/40/g, "hover:bg-red-100"],
  [/hover:bg-red-950\/30/g, "hover:bg-red-100"],
  [/text-red-200/g, "text-red-800"],
  [/text-red-300/g, "text-red-700"],
  [/border-red-800/g, "border-red-300"],

  [/text-blue-400/g, "text-blue-600"],

  [/text-emerald-300/g, "text-emerald-800"],
  [/text-emerald-200/g, "text-emerald-800"],
  [/bg-emerald-950\/60/g, "bg-emerald-100"],
  [/bg-emerald-950\/40/g, "bg-emerald-50"],
  [/bg-emerald-950\/30/g, "bg-emerald-50"],
  [/bg-emerald-950\/10/g, "bg-emerald-50"],
  [/border-emerald-900\/60/g, "border-emerald-200"],
  [/border-emerald-900\/50/g, "border-emerald-200"],
  [/border-emerald-800/g, "border-emerald-200"],

  [/text-amber-300/g, "text-amber-900"],
  [/text-amber-200/g, "text-amber-900"],
  [/border-amber-900\/60/g, "border-amber-200"],
  [/border-amber-900\/50/g, "border-amber-200"],
  [/bg-amber-950\/40/g, "bg-amber-50"],
  [/bg-amber-950\/30/g, "bg-amber-50"],
  [/bg-amber-950\/20/g, "bg-amber-50"],
  [/bg-amber-950\/10/g, "bg-amber-50"],
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
