import { parseOriginMetadataText, type ParsedOriginMetadata } from "./regularTaskRunJournal";

export type SplitTaskDescription = {
  humanText: string;
  metadataBlock: string | null;
  originMetadata: ParsedOriginMetadata;
  hasOriginMetadata: boolean;
};

const ORIGIN_BLOCK_MARKER = "ID запуска:";

function normalizeNewlines(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
}

function isOriginMetadataBlock(text: string): boolean {
  return String(text ?? "").includes(ORIGIN_BLOCK_MARKER);
}

/** One scheduler block: `---` + lines with `ID запуска:` + closing `---`. */
const LEADING_ORIGIN_BLOCK_RE = /^---\n([\s\S]*?\n)---(?:\n|$)/;
const TRAILING_ORIGIN_BLOCK_RE = /\n---\n([\s\S]*?\n)---\s*$/;
const WHOLE_ORIGIN_BLOCK_RE = /^---\n([\s\S]*?\n)---\s*$/;

function stripOriginMetadataBlocks(text: string): {
  humanText: string;
  metadataBlocks: string[];
} {
  let current = text.trim();
  const metadataBlocks: string[] = [];

  for (;;) {
    const leading = current.match(LEADING_ORIGIN_BLOCK_RE);
    if (!leading || !isOriginMetadataBlock(leading[1])) break;
    metadataBlocks.push(leading[1].trim());
    current = current.slice(leading[0].length).trim();
  }

  for (;;) {
    const trailing = current.match(TRAILING_ORIGIN_BLOCK_RE);
    if (!trailing || !isOriginMetadataBlock(trailing[1])) break;
    metadataBlocks.push(trailing[1].trim());
    current = current.slice(0, trailing.index).trim();
  }

  const whole = current.match(WHOLE_ORIGIN_BLOCK_RE);
  if (whole && isOriginMetadataBlock(whole[1])) {
    metadataBlocks.push(whole[1].trim());
    current = "";
  }

  return { humanText: current.trim(), metadataBlocks };
}

/**
 * Splits user-authored task text from scheduler origin metadata appended by regular-tasks runs.
 * Backend format: optional human text, then one or more `\n---\n` + metadata lines + `\n---` blocks.
 * Dedup re-appends a second block when the same task is touched by another run_id.
 */
export function splitTaskDescription(description?: string | null): SplitTaskDescription {
  const raw = String(description ?? "");
  const trimmed = normalizeNewlines(raw).trim();

  if (!trimmed) {
    return {
      humanText: "",
      metadataBlock: null,
      originMetadata: {},
      hasOriginMetadata: false,
    };
  }

  const { humanText, metadataBlocks } = stripOriginMetadataBlocks(trimmed);

  if (metadataBlocks.length === 0) {
    return {
      humanText: trimmed,
      metadataBlock: null,
      originMetadata: {},
      hasOriginMetadata: false,
    };
  }

  const lastBlock = metadataBlocks[metadataBlocks.length - 1];
  return {
    humanText,
    metadataBlock: lastBlock,
    originMetadata: parseOriginMetadataText(lastBlock),
    hasOriginMetadata: true,
  };
}

/** User-facing description without scheduler origin metadata blocks. */
export function taskDescriptionForUser(description?: string | null): string {
  return splitTaskDescription(description).humanText;
}
