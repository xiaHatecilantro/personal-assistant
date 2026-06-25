import {
  CaretRightOutlined,
  PauseOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "antd";
import { useCallback, useEffect, useRef, useState } from "react";
import { updateTimer } from "../api/tasks";
import type { Task } from "../types/task";

interface Props {
  task: Task;
}

export default function TaskTimer({ task }: Props) {
  const queryClient = useQueryClient();
  const [elapsed, setElapsed] = useState(task.timer_total_seconds || 0);
  const [running, setRunning] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isCountdown = task.timer_preset != null && task.timer_preset > 0;
  const total = isCountdown ? task.timer_preset! : elapsed;

  const timerMutation = useMutation({
    mutationFn: (seconds: number) => updateTimer(task.id, seconds),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });

  // 同步外部计时变化
  useEffect(() => {
    if (!running && task.timer_total_seconds !== elapsed) {
      setElapsed(task.timer_total_seconds || 0);
    }
  }, [task.timer_total_seconds]);

  const stopInterval = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const tick = useCallback(() => {
    setElapsed((prev) => {
      const next = prev + 1;
      // 倒计时到 0 自动停止
      if (isCountdown && next >= total) {
        stopInterval();
        setRunning(false);
        timerMutation.mutate(next);
        return total;
      }
      return next;
    });
  }, [isCountdown, total, stopInterval, timerMutation]);

  const start = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      // 倒计时归零时重新开始
      if (isCountdown && elapsed >= total) {
        setElapsed(0);
      }
      setRunning(true);
      stopInterval();
      intervalRef.current = setInterval(tick, 1000);
    },
    [isCountdown, elapsed, total, tick, stopInterval],
  );

  const pause = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setRunning(false);
      stopInterval();
      timerMutation.mutate(elapsed);
    },
    [elapsed, stopInterval, timerMutation],
  );

  const reset = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      setRunning(false);
      stopInterval();
      setElapsed(0);
      timerMutation.mutate(0);
    },
    [stopInterval, timerMutation],
  );

  const remaining = isCountdown ? total - elapsed : elapsed;

  const fmt = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div
      style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* 手动计时器 */}
      <span
        style={{
          fontFamily: "Consolas, monospace",
          fontSize: 14,
          minWidth: 44,
          textAlign: "right",
          color: isCountdown && remaining <= 60 ? "#f5222d" : "#333",
        }}
      >
        {isCountdown ? fmt(remaining) : fmt(elapsed)}
      </span>

      {/* 环形进度条 */}
      {isCountdown && (
        <svg width={28} height={28} style={{ flexShrink: 0 }}>
          <circle
            cx={14}
            cy={14}
            r={11}
            fill="none"
            stroke="#f0f0f0"
            strokeWidth={3}
          />
          <circle
            cx={14}
            cy={14}
            r={11}
            fill="none"
            stroke={remaining <= 60 ? "#f5222d" : "#1677ff"}
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={2 * Math.PI * 11}
            strokeDashoffset={2 * Math.PI * 11 * (1 - elapsed / total)}
            transform="rotate(-90 14 14)"
            style={{ transition: "stroke-dashoffset 1s linear" }}
          />
        </svg>
      )}

      {/* 操作按钮 */}
      <Button
        type="text"
        size="small"
        icon={
          running ? (
            <PauseOutlined />
          ) : (
            <CaretRightOutlined />
          )
        }
        onClick={running ? pause : start}
        style={{ color: running ? "#1677ff" : "#52c41a" }}
      />
      {!running && elapsed > 0 && (
        <Button
          type="text"
          size="small"
          icon={<ReloadOutlined />}
          onClick={reset}
          danger
        />
      )}
    </div>
  );
}
