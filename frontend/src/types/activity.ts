export type ActivityEntryStatus = "info" | "running" | "success" | "error";

export interface ActivityEntry {
  id: string;
  timestamp: Date;
  status: ActivityEntryStatus;
  level: 1 | 2 | 3 | 4 | null;
  message: string;
  detail?: string;
}
