// CLI용 샌드박스 파일 위치: <dataDir>/fake/*.json

import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { SandboxFiles, type FileBackend } from "./files.ts";

export function folderBackend(dir: string): FileBackend {
  return {
    location: dir,
    read: (name) => (existsSync(join(dir, name)) ? readFileSync(join(dir, name), "utf8") : null),
    write: (name, text) => {
      mkdirSync(dir, { recursive: true });
      writeFileSync(join(dir, name), text);
    },
    clear: () => rmSync(dir, { recursive: true, force: true }),
  };
}

export function sandboxFilesIn(dataDir: string): SandboxFiles {
  return new SandboxFiles(folderBackend(join(dataDir, "fake")));
}
