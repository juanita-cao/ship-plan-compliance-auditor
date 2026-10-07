import { GlobalOutlined } from "@ant-design/icons";
import { Button, Dropdown } from "antd";
import { useTranslation } from "react-i18next";
import { changeLanguage, type Lang } from "../i18n";

export function LanguageSwitch({ onDark = false }: { onDark?: boolean }) {
  const { i18n, t } = useTranslation();
  return (
    <Dropdown
      trigger={["click"]}
      menu={{
        selectedKeys: [i18n.language],
        items: [
          { key: "en", label: "EN" },
          { key: "zh", label: "中文" },
        ],
        onClick: ({ key }) => void changeLanguage(i18n, key as Lang),
      }}
    >
      <Button
        type="text"
        aria-label={t("header.language")}
        icon={<GlobalOutlined />}
        style={onDark ? { color: "#fff" } : undefined}
      >
        {i18n.language === "zh" ? "中文" : "EN"}
      </Button>
    </Dropdown>
  );
}
