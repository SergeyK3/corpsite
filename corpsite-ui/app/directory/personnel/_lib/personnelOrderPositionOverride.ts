/** An explicitly saved empty override restores the selected position. */
export function personnelOrderPositionOverride(payload:Record<string,unknown>):{ru:string;kk:string} {
  const assignment=payload.assignment as Record<string,unknown>|undefined;
  const root=payload.position_text_override;
  const source=(root && typeof root==='object' && !Array.isArray(root) ? root : assignment?.position_text_override) as {ru?:unknown;kk?:unknown}|undefined;
  return {ru:String(source?.ru || '').trim(),kk:String(source?.kk || '').trim()};
}
