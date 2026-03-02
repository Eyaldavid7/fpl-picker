"use client";

import { useState, useMemo } from "react";
import {
  TrendingUp,
  Loader2,
  AlertCircle,
  BarChart3,
  Play,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ErrorBar,
} from "recharts";
import { useBatchPredict, useModels, useGameweeks } from "@/hooks/useApi";
import type { Prediction, ModelInfo } from "@/types";

export default function PredictionsPage() {
  const { data: models, isLoading: modelsLoading } = useModels();
  const { data: gameweeks } = useGameweeks();

  const [selectedModel, setSelectedModel] = useState<string>("ensemble");
  const [selectedGw, setSelectedGw] = useState<number | null>(null);

  const batchPredict = useBatchPredict();

  // Determine next gameweek
  const nextGw = gameweeks?.find((gw) => gw.is_next);
  const targetGw = selectedGw ?? nextGw?.id ?? 1;

  const handlePredict = () => {
    batchPredict.mutate({
      gameweeks: [targetGw],
      model: selectedModel,
    });
  };

  const predictions: Prediction[] = batchPredict.data?.predictions ?? [];

  // Top 20 predicted players for bar chart
  const topPredictions = useMemo(() => {
    return [...predictions]
      .sort((a, b) => b.predicted_points - a.predicted_points)
      .slice(0, 20)
      .map((p) => ({
        name: p.player_name ?? `Player ${p.player_id}`,
        predicted: Number(p.predicted_points.toFixed(2)),
        lower: Number(
          (p.predicted_points - p.confidence_lower).toFixed(2)
        ),
        upper: Number(
          (p.confidence_upper - p.predicted_points).toFixed(2)
        ),
        model: p.model,
      }));
  }, [predictions]);

  // Sorted predictions for table
  const sortedPredictions = useMemo(() => {
    return [...predictions].sort(
      (a, b) => b.predicted_points - a.predicted_points
    );
  }, [predictions]);

  // Model display name helper
  const modelDisplayName = (name: string): string => {
    const m = models?.find((md: ModelInfo) => md.name === name);
    return m?.display_name ?? name;
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold fpl-gradient-text">Predictions</h1>
        <p className="mt-1 text-[var(--muted-foreground)]">
          ML-powered point predictions with confidence intervals and model
          comparison
        </p>
      </div>

      {/* Controls */}
      <div className="fpl-card">
        <h2 className="text-lg font-semibold mb-4">Prediction Parameters</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Model selector */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Prediction Model
            </label>
            {modelsLoading ? (
              <div className="skeleton h-10 w-full" />
            ) : (
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="fpl-select"
              >
                <option value="ensemble">Ensemble (All Models)</option>
                {models?.map((m: ModelInfo) => (
                  <option key={m.name} value={m.name}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Gameweek selector */}
          <div>
            <label className="block text-sm font-medium text-[var(--muted-foreground)] mb-2">
              Gameweek
            </label>
            <select
              value={targetGw}
              onChange={(e) => setSelectedGw(Number(e.target.value))}
              className="fpl-select"
            >
              {gameweeks
                ?.filter((gw) => !gw.finished)
                .map((gw) => (
                  <option key={gw.id} value={gw.id}>
                    GW {gw.id}
                    {gw.is_next ? " (Next)" : ""}
                  </option>
                ))}
              {!gameweeks && (
                <option value={targetGw}>GW {targetGw}</option>
              )}
            </select>
          </div>

          {/* Run button */}
          <div className="flex items-end">
            <button
              onClick={handlePredict}
              disabled={batchPredict.isPending}
              className="fpl-button-primary w-full gap-2"
            >
              {batchPredict.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Predicting...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Predictions
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {batchPredict.isError && (
        <div className="fpl-card border-red-500/30 bg-red-500/5">
          <div className="flex items-center gap-3 text-red-400">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <div>
              <p className="font-semibold">Prediction Failed</p>
              <p className="text-sm mt-1 text-red-400/80">
                {batchPredict.error?.message ||
                  "Could not run predictions. Make sure the backend is running."}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Loading */}
      {batchPredict.isPending && (
        <div className="fpl-card flex flex-col items-center justify-center py-16">
          <Loader2 className="h-10 w-10 animate-spin text-[var(--primary)]" />
          <p className="mt-4 text-[var(--muted-foreground)]">
            Running {modelDisplayName(selectedModel)} predictions for GW{" "}
            {targetGw}...
          </p>
        </div>
      )}

      {/* Results */}
      {predictions.length > 0 && !batchPredict.isPending && (
        <>
          {/* Bar chart */}
          <div className="fpl-card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold">
                  Top 20 Predicted Players
                </h2>
                <p className="text-sm text-[var(--muted-foreground)]">
                  GW {targetGw} - {modelDisplayName(selectedModel)} model
                </p>
              </div>
              <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
                <BarChart3 className="h-4 w-4" />
                {predictions.length} players predicted
              </div>
            </div>
            <div className="h-[400px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={topPredictions}
                  layout="vertical"
                  margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.05)"
                  />
                  <XAxis
                    type="number"
                    tick={{ fill: "#a0a0a0", fontSize: 12 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: "#f0f0f0", fontSize: 11 }}
                    axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
                    width={95}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#1a0022",
                      border: "1px solid #3d0050",
                      borderRadius: 8,
                      color: "#f0f0f0",
                    }}
                    formatter={(value: number) => [
                      `${value.toFixed(1)} pts`,
                      "Predicted",
                    ]}
                  />
                  <Legend />
                  <Bar
                    dataKey="predicted"
                    name="Predicted Points"
                    fill="#00ff87"
                    radius={[0, 4, 4, 0]}
                  >
                    <ErrorBar
                      dataKey="upper"
                      width={4}
                      strokeWidth={1.5}
                      stroke="#04f5ff"
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Predictions table */}
          <div className="fpl-card overflow-hidden p-0">
            <div className="px-6 pt-6 pb-2">
              <h2 className="text-lg font-semibold">All Predictions</h2>
              <p className="text-sm text-[var(--muted-foreground)]">
                {sortedPredictions.length} player predictions for GW{" "}
                {targetGw}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="fpl-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Player</th>
                    <th>Predicted</th>
                    <th>Confidence Low</th>
                    <th>Confidence High</th>
                    <th>Model</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedPredictions.slice(0, 50).map((pred, idx) => (
                    <tr key={`${pred.player_id}-${pred.model}`}>
                      <td className="text-[var(--muted-foreground)]">
                        {idx + 1}
                      </td>
                      <td className="font-medium">
                        {pred.player_name ?? `Player ${pred.player_id}`}
                      </td>
                      <td className="text-[var(--primary)] font-bold">
                        {pred.predicted_points.toFixed(2)}
                      </td>
                      <td className="text-[var(--muted-foreground)]">
                        {pred.confidence_lower.toFixed(2)}
                      </td>
                      <td className="text-[var(--muted-foreground)]">
                        {pred.confidence_upper.toFixed(2)}
                      </td>
                      <td>
                        <span className="fpl-badge bg-[var(--accent)]/10 text-[var(--accent)]">
                          {pred.model}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {sortedPredictions.length > 50 && (
              <div className="border-t border-[var(--border)] px-4 py-3 text-center text-xs text-[var(--muted-foreground)]">
                Showing top 50 of {sortedPredictions.length} predictions
              </div>
            )}
          </div>
        </>
      )}

      {/* Empty state */}
      {predictions.length === 0 && !batchPredict.isPending && !batchPredict.isError && (
        <div className="fpl-card flex flex-col items-center justify-center py-16 text-center">
          <TrendingUp className="h-12 w-12 text-[var(--muted-foreground)]" />
          <h3 className="mt-4 text-lg font-semibold">
            No Predictions Yet
          </h3>
          <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md">
            Select a prediction model and gameweek, then click &quot;Run
            Predictions&quot; to generate point forecasts for all players.
          </p>
        </div>
      )}
    </div>
  );
}
