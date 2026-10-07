import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";
import { en } from "./en";
import { zh } from "./zh";
import { enUi } from "./en.ui";
import { zhUi } from "./zh.ui";

export type Lang = "en" | "zh";

function savedLang(): Lang {
  try {
    const v = localStorage.getItem("pvcb_lang");
    if (v === "en" || v === "zh") return v;
  } catch {}
  return "en";
}

export async function createI18n(): Promise<i18n> {
  const instance = i18next.createInstance();
  await instance.use(initReactI18next).init({
    lng: savedLang(),
    fallbackLng: "en",
    resources: { en: { translation: { ...en, ...enUi } }, zh: { translation: { ...zh, ...zhUi } } },
    interpolation: { escapeValue: false },
    returnNull: false,
  });
  return instance;
}

export async function changeLanguage(instance: i18n, lang: Lang): Promise<void> {
  await instance.changeLanguage(lang);
  try { localStorage.setItem("pvcb_lang", lang); } catch {}
}
