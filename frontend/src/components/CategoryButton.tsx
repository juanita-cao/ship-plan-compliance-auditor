import { Button } from "antd";
import type { DetectedInstance } from "../api/client";
import { useAppDispatch, useAppState } from "../state/store";

interface Props {
  categoryId: string;
  label: string;
  color: string;
  count: number;
  instances: DetectedInstance[];
}

export function CategoryButton({ categoryId, label, color, count, instances }: Props) {
  const { selectedCategory, selectedInstanceId } = useAppState();
  const dispatch = useAppDispatch();
  const isActive = selectedCategory === categoryId;

  return (
    <div style={{ marginBottom: 6 }}>
      <Button
        type={isActive ? "primary" : "default"}
        block
        style={isActive ? { backgroundColor: color, borderColor: color } : {}}
        onClick={() => dispatch({ type: "categoryClicked", category: categoryId })}
      >
        <span style={{ marginRight: 6 }}>●</span>
        {label}
        <span style={{ marginLeft: "auto", fontWeight: 600 }}>×{count}</span>
      </Button>
      {isActive && instances.map((inst) => (
        <div
          key={inst.id}
          onClick={() => dispatch({ type: "instanceClicked", instanceId: inst.id })}
          style={{
            padding: "4px 12px",
            cursor: "pointer",
            fontSize: 12,
            color: selectedInstanceId === inst.id ? color : "#666",
            fontWeight: selectedInstanceId === inst.id ? 600 : 400,
            borderLeft: `3px solid ${selectedInstanceId === inst.id ? color : "#eee"}`,
            marginLeft: 8,
            marginTop: 2,
          }}
        >
          {inst.location_desc || inst.nearby_text || inst.id}
        </div>
      ))}
    </div>
  );
}
