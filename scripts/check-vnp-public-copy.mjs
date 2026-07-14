import { readFileSync, statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const roots = [
  "frontend/src",
  "app/main.py",
  "app/api/routers",
  "DEPLOYMENT_PLAYBOOK.md",
  "README.md",
];

const forbidden = [
  "10" + "D",
  "10" + "-D",
  "10" + "-dimensional",
  "10" + "-Dimensional Scoring Model",
  "10 immutable vectors",
  "Unbiased " + "10" + "-D Composite Scores",
  "LOCKED SPECIFICATION " + "v0.1.5",
  "v0.1.5",
  "v0.1.16",
  "autonomously slashed",
  "x402 USDC ROUTE PAYMENTS (REAL)",
  "https://docs.veklom.com/vnp",
  "Signed telemetry', weight: 'Partial'",
  "Signed telemetry\", weight: \"Partial\"",
  "Robust scoring', weight: 'Partial'",
  "Robust scoring\", weight: \"Partial\"",
  "DEMO MODE: VNP_TOPOLOGY_MESH",
];

function files(root) {
  try {
    const stat = statSync(root);
    if (stat.isFile()) return [root];
    return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
      const path = join(root, entry.name);
      if (entry.isDirectory()) return files(path);
      return /\.(ts|tsx|py|md|json)$/.test(path) ? [path] : [];
    });
  } catch {
    return [];
  }
}

const failures = [];
for (const file of roots.flatMap(files)) {
  const text = readFileSync(file, "utf8");
  for (const term of forbidden) {
    if (text.includes(term)) {
      failures.push(`${file}: ${term}`);
    }
  }
}

if (failures.length) {
  console.error("Forbidden VNP public copy found:\n" + failures.join("\n"));
  process.exit(1);
}

console.log("VNP standalone public copy check passed.");
