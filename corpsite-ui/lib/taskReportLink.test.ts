import { describe, expect, it } from "vitest";

import {
  REPORT_LINK_EMPTY_LABEL,
  REPORT_LINK_NETWORK_HINT,
  isHttpUrl,
  isLocalOrNetworkPath,
  isUncPath,
  reportLinkDisplayText,
  reportLinkHint,
  resolveTaskReportLink,
} from "./taskReportLink";

describe("taskReportLink", () => {
  it("resolveTaskReportLink reads report_link and aliases", () => {
    expect(resolveTaskReportLink({ report_link: " https://a.test " })).toBe("https://a.test");
    expect(resolveTaskReportLink({ report_url: "\\\\server\\share" })).toBe("\\\\server\\share");
    expect(resolveTaskReportLink({ reportLink: "d:\\docs\\r.pdf" })).toBe("d:\\docs\\r.pdf");
    expect(resolveTaskReportLink({ report_link: null })).toBe("");
  });

  it("report_link=null → display fallback, no network/http hint", () => {
    expect(reportLinkDisplayText("")).toBe(REPORT_LINK_EMPTY_LABEL);
    expect(reportLinkHint("")).toBeNull();
  });

  it("report_link=https://example.com/report → http url + no hint", () => {
    const link = "https://example.com/report";
    expect(isHttpUrl(link)).toBe(true);
    expect(reportLinkDisplayText(link)).toBe(link);
    expect(reportLinkHint(link)).toBeNull();
  });

  it("report_link UNC → local/network path, neutral hint, not empty fallback", () => {
    const link = "\\\\192.168.103.88\\obmen\\Отчеты\\report";
    expect(isUncPath(link)).toBe(true);
    expect(isLocalOrNetworkPath(link)).toBe(true);
    expect(reportLinkDisplayText(link)).toBe(link);
    expect(reportLinkHint(link)).toBe(REPORT_LINK_NETWORK_HINT);
    expect(reportLinkDisplayText(link)).not.toBe(REPORT_LINK_EMPTY_LABEL);
  });

  it("recognizes UNC paths stored with a single leading backslash", () => {
    const link = "\\192.168.103.88\\obmen\\Отчеты\\report";
    expect(isUncPath(link)).toBe(true);
    expect(reportLinkHint(link)).toBe(REPORT_LINK_NETWORK_HINT);
  });

  it("recognizes Windows drive paths", () => {
    const link = "d:\\reports\\june.pdf";
    expect(isLocalOrNetworkPath(link)).toBe(true);
    expect(reportLinkHint(link)).toBe(REPORT_LINK_NETWORK_HINT);
  });
});
