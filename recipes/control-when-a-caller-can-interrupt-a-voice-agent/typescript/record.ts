/**
 * The recorder verify.py drives. It renders the document with the configured
 * turn-taking, then again with one override per argument, and runs the same
 * table of raw environment values through the parsers. Expected values and the
 * schema bounds live in verify.py.
 */
const recipe = await import("./index.js");
const overrides = JSON.parse(process.argv[2] ?? "[]") as Record<string, unknown>[];
const barges = JSON.parse(process.argv[3] ?? "[]") as string[];
const numbers = JSON.parse(process.argv[4] ?? "[]") as string[];
const bad = JSON.parse(process.argv[5] ?? "[]") as string[];

const attempt = (fn: () => number) => {
  try { return fn(); } catch { return "threw"; }
};

console.log(JSON.stringify({
  doc: recipe.render(),
  variants: overrides.map((o) => recipe.render({ ...recipe.TURN_TAKING, ...o })),
  barge: barges.map((raw) => recipe.bargeValue(raw)),
  number: numbers.map((raw) => recipe.numberValue(raw, 52)),
  badInt: bad.map((raw) => attempt(() => recipe.intValue(raw, 3))),
}));
