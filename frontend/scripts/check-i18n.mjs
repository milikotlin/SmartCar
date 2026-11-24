// Checks the dictionaries and the components:  npm run check:i18n
//  1. messages/*.json have the same keys; 2. the same placeholders and tags; 3. every Hebrew text is Hebrew (or a listed name); 4. no text is written directly in a component.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const flat = (o, p = "") => Object.entries(o).flatMap(([k, v]) => (typeof v === "string" ? [[p + k, v]] : flat(v, `${p}${k}.`)));
const load = (l) => new Map(flat(JSON.parse(readFileSync(join(ROOT, "messages", `${l}.json`), "utf8"))));
const en = load("en");
const he = load("he");

const SAME_IN_BOTH = new Set(["meta.title", "language.en", "metrics.auc", "subsystem.models", "garages.hoursSource", "garages.googleMaps", "garages.waze"]);
/** Placeholders ({value}, {count, plural, ...}) and tags (<b>), without the words inside plural forms. */
const marks = (s) => [...new Set([...s.matchAll(/\{(\w+)(?=[,}])|<(\w+)>/g)].map((m) => m[1] ?? `<${m[2]}>`))].sort().join();
for (const k of en.keys()) if (!he.has(k)) errors.push(`he.json: missing ${k}`);
for (const k of he.keys()) if (!en.has(k)) errors.push(`he.json: unknown ${k}`);
for (const [k, v] of en) {
  const h = he.get(k);
  if (h === undefined) continue;
  if (!v.trim() || !h.trim()) errors.push(`${k}: empty`);
  if (marks(v) !== marks(h)) errors.push(`${k}: placeholders differ (${marks(v)} / ${marks(h)})`);
  if (!SAME_IN_BOTH.has(k) && !/[א-ת]/.test(h)) errors.push(`${k}: not translated ("${h}")`);
  if (k !== "language.he" && /[א-ת]/.test(v)) errors.push(`${k}: Hebrew in en.json`);
}

const files = (d) => readdirSync(d).flatMap((f) => (statSync(join(d, f)).isDirectory() ? files(join(d, f)) : f.endsWith(".tsx") ? [join(d, f)] : []));
const NOT_TEXT = /^[\s\d·:,.()%★✓✗▾●—–＋→×/#|-]*$/;
const ALLOWED = new Set(["IL", "smartcar", "ops", "P"]); // country code on the plate, product name, percentile mark
const TEXT_ATTRIBUTES = new Set(["placeholder", "aria-label", "title", "alt", "label", "eyebrow"]);
for (const file of [...files(join(ROOT, "components")), ...files(join(ROOT, "app"))]) {
  const src = ts.createSourceFile(file, readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const report = (node, text) => errors.push(`${relative(ROOT, file)}:${src.getLineAndCharacterOfPosition(node.getStart()).line + 1}: text in the component: ${JSON.stringify(text.trim())}`);
  const visit = (node) => {
    if (ts.isJsxText(node) && !NOT_TEXT.test(node.text) && !ALLOWED.has(node.text.trim())) report(node, node.text);
    if (ts.isJsxAttribute(node) && TEXT_ATTRIBUTES.has(node.name.getText()) && node.initializer && ts.isStringLiteral(node.initializer) && !NOT_TEXT.test(node.initializer.text)) report(node, node.initializer.text);
    ts.forEachChild(node, visit);
  };
  visit(src);
}

if (errors.length) {
  console.error(errors.join("\n"));
  process.exit(1);
}
console.log(`i18n OK: ${en.size} texts in English and Hebrew, no text written in the components`);
