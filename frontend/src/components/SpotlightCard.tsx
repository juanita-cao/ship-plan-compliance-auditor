import { useTranslation } from "react-i18next";
import { Spin } from "antd";
import { useQuery } from "@tanstack/react-query";
import { get, type ImageResponse } from "../api/client";

interface Props {
  projectId: string;
  imageStem: string;
  selectedCategory: string | null;
  selectedInstanceId: string | null;
  title: string;
  spotlight?: boolean;
  noCard?: boolean;
}

export function ImageCard({ projectId, imageStem, selectedCategory, selectedInstanceId, title, spotlight = false, noCard = false }: Props) {
  const { t } = useTranslation();
  const params = new URLSearchParams();
  if (selectedCategory) params.set("category", selectedCategory);
  if (selectedInstanceId) params.set("instance_id", selectedInstanceId);
  const qs = params.toString() ? `?${params.toString()}` : "";

  const url = spotlight
    ? `/spotlight/${projectId}/${imageStem}${qs}`
    : `/image/${projectId}/${imageStem}`;

  const { data, isLoading, isError } = useQuery<ImageResponse>({
    queryKey: spotlight
      ? ["spotlight", projectId, imageStem, selectedCategory, selectedInstanceId]
      : ["image", projectId, imageStem],
    queryFn: () => get<ImageResponse>(url),
    staleTime: spotlight ? 0 : Infinity,
  });

  if (noCard) {
    return (
      <>
        {isLoading && <Spin />}
        {isError && <div style={{ color: "#f53f3f", fontSize: 12 }}>{t("metrics.imageFailed")}</div>}
        {data && (
          <img
            src={data.data}
            alt={title}
            style={{ maxWidth: "100%", maxHeight: "60vh", width: "auto", height: "auto", display: "block", margin: "0 auto" }}
          />
        )}
      </>
    );
  }

  return (
    <div style={{ background: "#fff", borderRadius: 8, padding: 12, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
      <div style={{ fontWeight: 600, fontSize: 13, color: "#1d2129", marginBottom: 8 }}>{title}</div>
      {isLoading && <div style={{ display: "flex", justifyContent: "center", padding: 32 }}><Spin /></div>}
      {isError && <div style={{ color: "#f53f3f", fontSize: 12 }}>{t("metrics.imageFailed")}</div>}
      {data && (
        <img
          src={data.data}
          alt={title}
          style={{ width: "100%", borderRadius: 4, display: "block" }}
        />
      )}
    </div>
  );
}
