export const COPYRIGHT_OWNER = "InnerDrive Studio";
export const COPYRIGHT_YEAR = 2026;
export const NAVY = "#0a1e3d";

export interface VesselMeta {
  type: string;
  imo: string;
  flag: string;
  yearBuilt: number;
}

export const VESSEL_META: Record<string, VesselMeta> = {
  demo_ship_a:     { type: "General Cargo",  imo: "IMO 9 876 543", flag: "Panama",          yearBuilt: 2018 },
  demo_ship_b:     { type: "Bulk Carrier",   imo: "IMO 9 234 567", flag: "Singapore",       yearBuilt: 2015 },
  eastern_pioneer: { type: "Tanker",         imo: "IMO 9 341 122", flag: "Hong Kong",       yearBuilt: 2019 },
  southern_cross:  { type: "Bulk Carrier",   imo: "IMO 9 512 087", flag: "Marshall Islands", yearBuilt: 2016 },
  northern_star:   { type: "General Cargo",  imo: "IMO 9 689 341", flag: "Bahamas",         yearBuilt: 2020 },
  pacific_trader:  { type: "Container Ship", imo: "IMO 9 773 215", flag: "Panama",          yearBuilt: 2017 },
  asian_spirit:    { type: "Tanker",         imo: "IMO 9 429 560", flag: "Singapore",       yearBuilt: 2014 },
  pacific_eagle:   { type: "General Cargo",  imo: "IMO 9 634 782", flag: "Hong Kong",       yearBuilt: 2013 },
  ocean_pioneer:   { type: "Bulk Carrier",   imo: "IMO 9 881 034", flag: "Marshall Islands", yearBuilt: 2021 },
  eastern_wind:    { type: "Container Ship", imo: "IMO 9 558 901", flag: "Bahamas",         yearBuilt: 2022 },
};

export type VesselStatus = "to_review" | "pending_confirm" | "action_required" | "up_to_date" | "scheduled";

export interface VesselFleetEntry {
  projectId: string | null;  // null = no uploaded plans, not clickable
  historyKey: string;        // key used in reviewStore history (projectId for live vessels, slug otherwise)
  name: string;
  type: string;
  imo: string;
  flag: string;
  flagEmoji: string;
  yearBuilt: number;
  complianceMock: "GO" | "NO_GO" | "CONDITIONAL";
  status: VesselStatus;
  lastReviewMock: string;
}

export const VESSEL_FLEET: VesselFleetEntry[] = [
  { projectId: "demo_ship_a", historyKey: "demo_ship_a", name: "Demo Ship A", type: "General Cargo", imo: "IMO 9 876 543", flag: "Panama", flagEmoji: "🇵🇦", yearBuilt: 2018, complianceMock: "GO", status: "up_to_date", lastReviewMock: "2026-09-30" },
  { projectId: "demo_ship_b", historyKey: "demo_ship_b", name: "Demo Ship B", type: "Bulk Carrier", imo: "IMO 9 234 567", flag: "Singapore", flagEmoji: "🇸🇬", yearBuilt: 2015, complianceMock: "GO", status: "up_to_date", lastReviewMock: "2026-09-24" },
  { projectId: null, historyKey: "eastern_pioneer", name: "Eastern Pioneer", type: "Tanker", imo: "IMO 9 341 122", flag: "Hong Kong", flagEmoji: "🇭🇰", yearBuilt: 2019, complianceMock: "GO", status: "up_to_date", lastReviewMock: "2026-10-06" },
  { projectId: null, historyKey: "southern_cross", name: "Southern Cross", type: "Bulk Carrier", imo: "IMO 9 512 087", flag: "Marshall Is.", flagEmoji: "🇲🇭", yearBuilt: 2016, complianceMock: "NO_GO", status: "action_required", lastReviewMock: "2026-09-29" },
  { projectId: null, historyKey: "northern_star", name: "Northern Star", type: "General Cargo", imo: "IMO 9 689 341", flag: "Bahamas", flagEmoji: "🇧🇸", yearBuilt: 2020, complianceMock: "CONDITIONAL", status: "pending_confirm", lastReviewMock: "2026-10-02" },
  { projectId: null, historyKey: "pacific_trader", name: "Pacific Trader", type: "Container Ship", imo: "IMO 9 773 215", flag: "Panama", flagEmoji: "🇵🇦", yearBuilt: 2017, complianceMock: "NO_GO", status: "scheduled", lastReviewMock: "2026-08-21" },
  { projectId: null, historyKey: "asian_spirit", name: "Asian Spirit", type: "Tanker", imo: "IMO 9 429 560", flag: "Singapore", flagEmoji: "🇸🇬", yearBuilt: 2014, complianceMock: "GO", status: "up_to_date", lastReviewMock: "2026-09-18" },
  { projectId: null, historyKey: "ocean_pioneer", name: "Ocean Pioneer", type: "Bulk Carrier", imo: "IMO 9 881 034", flag: "Marshall Is.", flagEmoji: "🇲🇭", yearBuilt: 2021, complianceMock: "CONDITIONAL", status: "scheduled", lastReviewMock: "2026-09-25" },
  { projectId: null, historyKey: "pacific_eagle", name: "Pacific Eagle", type: "General Cargo", imo: "IMO 9 634 782", flag: "Hong Kong", flagEmoji: "🇭🇰", yearBuilt: 2013, complianceMock: "GO", status: "up_to_date", lastReviewMock: "2026-09-10" },
  { projectId: null, historyKey: "eastern_wind", name: "Eastern Wind", type: "Container Ship", imo: "IMO 9 558 901", flag: "Bahamas", flagEmoji: "🇧🇸", yearBuilt: 2022, complianceMock: "GO", status: "scheduled", lastReviewMock: "2026-08-30" },
];

// ─── Upload specification (ADR-F30) — single source for the modal, the checks and the Help Center ───

export const UPLOAD_LIMITS = {
  imageBytes: 20 * 1024 * 1024,
  pdfBytes: 50 * 1024 * 1024,
  pdfPages: 10,
  minLongEdge: 2000,
  maxLongEdge: 12000,
  maxPlansPerVessel: 5,
} as const;

export interface UploadRule {
  id: "U1" | "U2" | "U3" | "U4" | "U5" | "U6";
  kind: "hard" | "confirm" | "notice";
  label: { en: string; zh: string };
  text: { en: string; zh: string };
}

export const UPLOAD_SPEC: UploadRule[] = [
  { id: "U1", kind: "hard", label: { en: "Format", zh: "格式" },
    text: { en: "PNG, JPEG or PDF. Multi-page PDFs are stitched page by page; DWG / DXF are not supported.",
            zh: "PNG、JPEG 或 PDF。多页 PDF 会按页拼接；不支持 DWG / DXF。" } },
  { id: "U2", kind: "hard", label: { en: "Size", zh: "大小" },
    text: { en: "Images up to 20 MB. PDFs up to 50 MB and 10 pages.", zh: "图片不超过 20 MB；PDF 不超过 50 MB 且不超过 10 页。" } },
  { id: "U3", kind: "hard", label: { en: "Resolution", zh: "分辨率" },
    text: { en: "Long edge between 2000 and 12000 px. PDF pages are rasterised automatically.", zh: "长边 2000–12000 像素。PDF 页面会自动栅格化。" } },
  { id: "U4", kind: "confirm", label: { en: "Content", zh: "内容" },
    text: { en: "A fire control / general arrangement plan of this vessel, one vessel per upload, scale 1:100–1:500, IMO symbols legible.",
            zh: "该船的消防控制图 / 总布置图，一次只传一艘船，比例 1:100–1:500，IMO 图例清晰可辨。" } },
  { id: "U5", kind: "confirm", label: { en: "Quality", zh: "质量" },
    text: { en: "Upright and not mirrored; not a photo of a screen.", zh: "方向正确、未镜像；不是对屏幕的拍照。" } },
  { id: "U6", kind: "notice", label: { en: "Confidentiality", zh: "保密" },
    text: { en: "Demo only: do not upload confidential or commercial plans. Files are deleted automatically after 24 hours.",
            zh: "仅限演示：请勿上传保密或商业敏感的图纸。文件会在 24 小时后自动删除。" } },
];
