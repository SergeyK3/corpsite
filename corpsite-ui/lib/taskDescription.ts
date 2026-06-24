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

function splitFromMetadataBlock(
  humanText: string,
  metadataBlock: string,
): SplitTaskDescription {
  const trimmedBlock = metadataBlock.trim();
  return {
    humanText: humanText.trim(),
    metadataBlock: trimmedBlock,
    originMetadata: parseOriginMetadataText(trimmedBlock),
    hasOriginMetadata: true,
  };
}

/**
 * Splits user-authored task text from scheduler origin metadata appended by regular-tasks runs.
 * Backend format: optional human text, then `\n---\n` + metadata lines + `\n---`.
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

  const trailingBlockMatch = trimmed.match(/\n---\n([\s\S]*)\n---\s*$/);
  if (trailingBlockMatch && isOriginMetadataBlock(trailingBlockMatch[1])) {
    return splitFromMetadataBlock(
      trimmed.slice(0, trailingBlockMatch.index),
      trailingBlockMatch[1],
    );
  }

  if (trimmed.startsWith("---") && trimmed.endsWith("---") && isOriginMetadataBlock(trimmed)) {
    const metadataBlock = trimmed.replace(/^---\n?/, "").replace(/\n?---\s*$/, "");
    return splitFromMetadataBlock("", metadataBlock);
  }

  const looseTrailingMatch = trimmed.match(/\n---\n([\s\S]*)$/);
  if (looseTrailingMatch && isOriginMetadataBlock(looseTrailingMatch[1])) {
    return splitFromMetadataBlock(
      trimmed.slice(0, looseTrailingMatch.index),
      looseTrailingMatch[1].replace(/\n---\s*$/, ""),
    );
  }

  return {
    humanText: trimmed,
    metadataBlock: null,
    originMetadata: {},
    hasOriginMetadata: false,
  };
}

/** User-facing description without scheduler origin metadata block. */
export function taskDescriptionForUser(description?: string | null): string {
  return splitTaskDescription(description).humanText;
}
