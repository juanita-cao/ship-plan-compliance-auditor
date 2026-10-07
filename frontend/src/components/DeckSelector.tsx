import { useQuery } from "@tanstack/react-query";
import type { ImageResponse, ProjectInfo } from "../api/client";
import { get } from "../api/client";
import { useTranslation } from "react-i18next";
import { getDeckStatus, useReviewStore } from "../state/reviewStore";

const STATUS_STYLE: Record<string, { key: string; color: string; bg: string }> = {
  reviewed: { key: "deckReviewed", color: "#389e0d", bg: "rgba(56,158,13,0.12)" },
  done:     { key: "deckToReview", color: "#c2410c", bg: "rgba(234,88,12,0.10)" },
  new:      { key: "deckNew",      color: "#2F54EB", bg: "rgba(47,84,235,0.10)" },
};

function DeckCard({ projectId, image, selected, onSelect, onViewResults, disabled }: {
  projectId: string;
  image: ProjectInfo["images"][number];
  selected: boolean;
  onSelect: () => void;
  onViewResults: () => void;
  disabled?: boolean;
}) {
  const { data } = useQuery<ImageResponse>({
    queryKey: ["thumb", projectId, image.stem],
    queryFn: () => get<ImageResponse>(`/image/${projectId}/${image.stem}`),
    staleTime: Infinity,
  });

  const status = getDeckStatus(projectId, image.stem);
  const s = STATUS_STYLE[status];
  const { t } = useTranslation();

  return (
    <div
      onClick={onSelect}
      style={{
        width: 156, flexShrink: 0, cursor: "pointer", borderRadius: 10,
        border: selected ? "2.5px solid #2F54EB" : "2px solid #e8e8e8",
        background: "#fff",
        boxShadow: selected ? "0 0 0 3px rgba(47,84,235,0.15)" : "0 1px 4px rgba(0,0,0,.06)",
        overflow: "hidden", transition: "border 0.12s, box-shadow 0.12s",
      }}
    >
      {/* Thumbnail */}
      <div style={{ height: 88, background: "#f5f5f5", overflow: "hidden" }}>
        {data
          ? <img src={data.data} alt={image.label} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
          : <div style={{ height: "100%", background: "linear-gradient(135deg, #f0f2f5 25%, #e8eaf0 100%)" }} />
        }
      </div>
      {/* Label + status */}
      <div style={{ padding: "8px 10px 10px" }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#1d2129", marginBottom: 4 }}>{image.label}</div>
        {image.uploaded && <div style={{ fontSize: 10, fontWeight: 700, color: "#6b7280", letterSpacing: "0.04em", textTransform: "uppercase", marginBottom: 4 }}>{t("upload.tag")}</div>}
        <span style={{
          fontSize: 10, fontWeight: 700, letterSpacing: "0.04em",
          color: s.color, background: s.bg,
          padding: "2px 7px", borderRadius: 8,
        }}>
          {t(`vessel.${s.key}`)}
        </span>
        {status !== "new" && (
          <button
            type="button" disabled={disabled}
            onClick={e => { e.stopPropagation(); onViewResults(); }}
            style={{ border: 0, background: "transparent", color: "#2F54EB", fontSize: 12, cursor: disabled ? "default" : "pointer", marginLeft: 8, padding: 0 }}
          >
            {t("vessel.viewResults")}
          </button>
        )}
      </div>
    </div>
  );
}

interface Props {
  project: ProjectInfo;
  selectedStem: string | null;
  onSelect: (stem: string) => void;
  onViewResults: (stem: string) => void;
  disabled?: boolean;
  action?: React.ReactNode;
}

export function DeckSelector({ project, selectedStem, onSelect, onViewResults, disabled, action }: Props) {
  const { t } = useTranslation();
  useReviewStore();
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "#8c8c8c", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          {t("vessel.selectDeck")}
        </div>
        {action}
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {project.images.map(img => (
          <DeckCard
            key={img.stem}
            projectId={project.id}
            image={img}
            selected={img.stem === selectedStem}
            onSelect={() => onSelect(img.stem)}
            onViewResults={() => onViewResults(img.stem)}
            disabled={disabled}
          />
        ))}
      </div>
    </div>
  );
}
