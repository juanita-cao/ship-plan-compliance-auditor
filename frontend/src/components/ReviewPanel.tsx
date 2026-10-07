import { CheckCircleOutlined, FlagOutlined, PlusOutlined } from "@ant-design/icons";
import { Button, Form, Input, Modal, Radio, Select, Tag, Tooltip, message } from "antd";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DetectResult } from "../api/client";
import { useAuth } from "../state/authContext";
import { addHistoryEntry, type HistoryEntry } from "../state/reviewStore";
import { rvTransition, type RvState } from "../state/reviewPanelState";
import { ReviewCompleteCard } from "./ReviewCompleteCard";
import { SignOffModal } from "./SignOffModal";

type InstanceStatus = "pending" | "confirmed" | "flagged";

interface AddedInstance {
  category: string;
  locationDesc: string;
}

interface Props {
  result: DetectResult;
  projectLabel: string;
  imageLabel: string;
  categories: { id: string; label: string }[];
}

const VERDICT_COLORS: Record<string, string> = {
  GO: "#52c41a", NO_GO: "#f5222d", CONDITIONAL: "#fa8c16", WARN: "#fa8c16",
};

export function ReviewPanel({ result, projectLabel, imageLabel, categories }: Props) {
  const { auth } = useAuth();
  const { t } = useTranslation();

  const [reviews, setReviews] = useState<Record<string, InstanceStatus>>(
    () => Object.fromEntries(result.instances.map(i => [i.id, "pending" as InstanceStatus]))
  );
  const [added, setAdded] = useState<AddedInstance[]>([]);
  const [addModal, setAddModal] = useState(false);
  const [addForm] = Form.useForm<AddedInstance>();
  const [overrideVerdict, setOverrideVerdict] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [rv, setRv] = useState<RvState>("RV_EDITING");
  const [done, setDone] = useState<HistoryEntry | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const [noteError, setNoteError] = useState(false);

  const confirmedCount = Object.values(reviews).filter(s => s === "confirmed").length;
  const flaggedCount   = Object.values(reviews).filter(s => s === "flagged").length;
  const pendingCount   = Object.values(reviews).filter(s => s === "pending").length;
  const total          = result.instances.length;

  const setStatus = (id: string, status: InstanceStatus) =>
    setReviews(prev => ({ ...prev, [id]: status }));

  const acceptAll = () =>
    setReviews(Object.fromEntries(result.instances.map(i => [i.id, "confirmed"])));

  const finalVerdict = overrideVerdict ?? result.compliance_result?.verdict ?? "N/A";
  const signer = auth.username ?? "demo@pvcb.org";

  const handleSubmit = () => {
    const r = rvTransition(rv, { type: "submitClicked", pending: pendingCount, override: overrideVerdict, note });
    if (r.blocked === "note") setNoteError(true);
    else setNoteError(false);
    setRv(r.next);
  };

  const handleSign = () => {
    const entry: HistoryEntry = {
      id: crypto.randomUUID(),
      projectId: result.project_id,
      projectLabel,
      imageStem: result.image_stem,
      imageLabel,
      verdict: finalVerdict,
      reviewer: signer,
      submittedAt: new Date().toISOString(),
      instanceCount: total + added.length,
      confirmedCount,
      flaggedCount,
      note: note.trim(),
    };
    try {
      addHistoryEntry(entry);
    } catch (e) {
      message.error((e as Error).message);
      setRv(rvTransition("RV_SIGNING", { type: "signFailed" }).next);
      return;
    }
    setDone(entry);
    setRv(rvTransition("RV_SIGNING", { type: "signSucceeded" }).next);
    message.success(t("review.toast"));
  };

  const handleReset = () => {
    setReviews(Object.fromEntries(result.instances.map(i => [i.id, "pending"])));
    setAdded([]);
    setOverrideVerdict(null);
    setNote("");
    setNoteError(false);
  };

  useEffect(() => {
    if (rv === "RV_DONE") cardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [rv]);

  if (rv === "RV_DONE" && done) {
    return <div ref={cardRef}><ReviewCompleteCard entry={done} /></div>;
  }

  const progressPct = total > 0 ? Math.round(((confirmedCount + flaggedCount) / total) * 100) : 0;

  return (
    <div id="human-review" style={{ background: "#fff", borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,.08)", marginTop: 16, overflow: "hidden" }}>
      {/* Header */}
      <div style={{ padding: "14px 20px", borderBottom: "1px solid #f0f0f0", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 16 }}>🔍</span>
          <span style={{ fontWeight: 700, fontSize: 15 }}>{t("review.title")}</span>
          {pendingCount > 0
            ? <Tag color="orange">{t("review.pending", { n: pendingCount })}</Tag>
            : <Tag color="green">{t("review.allReviewed")}</Tag>
          }
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, color: "#8c8c8c" }}>{t("review.progress", { done: confirmedCount + flaggedCount, total })}</span>
          <div style={{ width: 80, height: 4, background: "#f0f0f0", borderRadius: 2 }}>
            <div style={{ width: `${progressPct}%`, height: "100%", background: "#2F54EB", borderRadius: 2, transition: "width 0.3s" }} />
          </div>
        </div>
      </div>

      <div style={{ padding: "16px 20px" }}>
        {/* Instance rows */}
        <div style={{ marginBottom: 16 }}>
          {result.instances.map((inst, idx) => {
            const status = reviews[inst.id];
            return (
              <div key={inst.id} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between",
                padding: "8px 12px", marginBottom: 4, borderRadius: 6,
                background: status === "confirmed" ? "rgba(82,196,26,0.06)" : status === "flagged" ? "rgba(245,34,45,0.06)" : "#fafafa",
                border: `1px solid ${status === "confirmed" ? "rgba(82,196,26,0.25)" : status === "flagged" ? "rgba(245,34,45,0.2)" : "#f0f0f0"}`,
                transition: "background 0.15s",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <span style={{ fontSize: 12, color: "#8c8c8c", flexShrink: 0 }}>#{idx + 1}</span>
                  <div style={{ minWidth: 0 }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }}>
                      {categories.find(c => c.id === inst.category)?.label ?? inst.category}
                    </span>
                    {inst.location_desc && (
                      <span style={{ fontSize: 11, color: "#8c8c8c", marginLeft: 8 }}>{inst.location_desc}</span>
                    )}
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
                  <Tooltip title={t("review.confirmTip")}>
                    <Button
                      size="small" icon={<CheckCircleOutlined />}
                      type={status === "confirmed" ? "primary" : "default"}
                      style={status === "confirmed" ? { background: "#52c41a", borderColor: "#52c41a" } : {}}
                      onClick={() => setStatus(inst.id, status === "confirmed" ? "pending" : "confirmed")}
                    >
                      {t("review.confirm")}
                    </Button>
                  </Tooltip>
                  <Tooltip title={t("review.flagTip")}>
                    <Button
                      size="small" icon={<FlagOutlined />} danger={status === "flagged"}
                      type={status === "flagged" ? "primary" : "default"}
                      onClick={() => setStatus(inst.id, status === "flagged" ? "pending" : "flagged")}
                    >
                      {t("review.flag")}
                    </Button>
                  </Tooltip>
                </div>
              </div>
            );
          })}

          {/* Added instances */}
          {added.map((inst, idx) => (
            <div key={`added-${idx}`} style={{ display: "flex", alignItems: "center", padding: "8px 12px", marginBottom: 4, borderRadius: 6, background: "rgba(47,84,235,0.04)", border: "1px dashed rgba(47,84,235,0.3)" }}>
              <PlusOutlined style={{ color: "#2F54EB", marginRight: 8, fontSize: 11 }} />
              <span style={{ fontSize: 13, fontWeight: 500 }}>{categories.find(c => c.id === inst.category)?.label ?? inst.category}</span>
              <span style={{ fontSize: 11, color: "#8c8c8c", marginLeft: 8 }}>{inst.locationDesc}</span>
              <span style={{ marginLeft: "auto", fontSize: 11, color: "#2F54EB" }}>{t("review.added")}</span>
            </div>
          ))}
        </div>

        {/* Actions row */}
        <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
          <Button size="small" icon={<CheckCircleOutlined />} onClick={acceptAll}>
            {t("review.acceptAll")}
          </Button>
          <Button size="small" icon={<PlusOutlined />} onClick={() => setAddModal(true)}>
            {t("review.addMissing")}
          </Button>
        </div>

        {/* Compliance override */}
        <div style={{ marginBottom: 16, padding: "12px 14px", background: "#fafafa", borderRadius: 6, border: "1px solid #f0f0f0" }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#595959", marginBottom: 8 }}>{t("review.override")}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <Radio.Group
              value={overrideVerdict ?? "__keep"}
              onChange={e => setOverrideVerdict(e.target.value === "__keep" ? null : e.target.value)}
              size="small"
            >
              <Radio value="__keep">
                {t("review.keep")}
                {result.compliance_result && (
                  <span style={{ marginLeft: 6, fontWeight: 700, color: VERDICT_COLORS[result.compliance_result.verdict] ?? "#595959" }}>
                    ({result.compliance_result.verdict})
                  </span>
                )}
              </Radio>
              <Radio value="GO"><span style={{ color: "#52c41a", fontWeight: 600 }}>GO</span></Radio>
              <Radio value="NO_GO"><span style={{ color: "#f5222d", fontWeight: 600 }}>NO_GO</span></Radio>
              <Radio value="CONDITIONAL"><span style={{ color: "#fa8c16", fontWeight: 600 }}>CONDITIONAL</span></Radio>
            </Radio.Group>
          </div>
        </div>

        {/* Note */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#595959", marginBottom: 6 }}>
            {t("review.note")} {overrideVerdict && <span style={{ color: "#f5222d" }}>*</span>}
          </div>
          <Input.TextArea
            value={note}
            onChange={e => { setNote(e.target.value); if (e.target.value.trim()) setNoteError(false); }}
            placeholder={overrideVerdict ? t("review.notePhRequired") : t("review.notePh")}
            rows={2}
            status={noteError ? "error" : undefined}
          />
          {noteError && <div style={{ color: "#f5222d", fontSize: 12, marginTop: 4 }}>{t("review.noteRequired")}</div>}
        </div>

        {/* Submit row */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Button onClick={handleReset}>{t("review.reset")}</Button>
          <Tooltip title={pendingCount === 0 ? "" : pendingCount === 1 ? t("review.submitTipOne") : t("review.submitTipMany", { n: pendingCount })}>
            <span>
              <Button type="primary" onClick={handleSubmit} disabled={pendingCount > 0}>
                {t("review.submit")}
              </Button>
            </span>
          </Tooltip>
        </div>
      </div>

      <SignOffModal
        open={rv === "RV_SIGNING"}
        summary={{
          projectLabel, imageLabel,
          aiVerdict: result.compliance_result?.verdict ?? null,
          finalVerdict, confirmed: confirmedCount, flagged: flaggedCount, added: added.length,
          note: note.trim(), signer,
        }}
        onCancel={() => setRv(rvTransition("RV_SIGNING", { type: "cancelClicked" }).next)}
        onSign={handleSign}
      />

      {/* Add Missing modal */}
      <Modal
        title={t("review.addTitle")}
        open={addModal}
        onCancel={() => { setAddModal(false); addForm.resetFields(); }}
        onOk={() => {
          addForm.validateFields().then(vals => {
            setAdded(prev => [...prev, vals]);
            setAddModal(false);
            addForm.resetFields();
          });
        }}
        okText={t("review.add")}
      >
        <Form form={addForm} layout="vertical">
          <Form.Item name="category" label={t("review.equipType")} rules={[{ required: true }]}>
            <Select placeholder={t("review.selectCategory")} options={categories.map(c => ({ value: c.id, label: c.label }))} />
          </Form.Item>
          <Form.Item name="locationDesc" label={t("review.location")} rules={[{ required: true }]}>
            <Input placeholder={t("review.locationPh")} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
