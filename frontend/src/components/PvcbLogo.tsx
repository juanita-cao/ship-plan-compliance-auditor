interface Props {
  size?: number;
}

// 8-pointed compass rose — classic maritime classification society mark
export function PvcbLogo({ size = 40 }: Props) {
  const G = "#C8A84B"; // gold
  return (
    <svg width={size} height={size} viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      {/* Outer ring */}
      <circle cx="40" cy="40" r="37" stroke={G} strokeWidth="1.5" fill="none" />

      {/*
        8-pointed compass star (16-point polygon):
        Cardinal (N/E/S/W) at r=32, intercardinal (NE/SE/SW/NW) at r=20, inner notch at r=13
      */}
      <polygon
        points="40,8 44,27 57,23 53,36 72,40 53,44 57,57 44,53 40,72 36,53 23,57 27,44 8,40 27,36 23,23 36,27"
        fill={G}
        opacity="0.92"
      />

      {/* Center circle (negative space — punched out via overlay) */}
      <circle cx="40" cy="40" r="5.5" fill="#0a1628" />
      <circle cx="40" cy="40" r="3" fill={G} />
    </svg>
  );
}
