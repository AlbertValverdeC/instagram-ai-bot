export interface DaySchedule {
  enabled: boolean;
  time: string | null;
}

export interface SchedulerConfig {
  enabled: boolean;
  schedule: Record<string, DaySchedule>;
}

export interface QueueItem {
  id: number;
  scheduled_date: string;
  scheduled_time: string | null;
  topic: string | null;
  template: number | null;
  status: "pending" | "processing" | "completed" | "error" | "skipped";
  post_id: number | null;
  result_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface NextRun {
  date: string;
  time: string;
  day_name: string;
  topic: string | null;
  hours_until: number;
}

export interface SchedulerState {
  config: SchedulerConfig;
  queue: QueueItem[];
  next_run: NextRun | null;
  pipeline_running: boolean;
  timezone: string;
}
