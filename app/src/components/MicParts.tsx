import { Icon } from "../ui";
import { openMicSettings, type MicAccess } from "../audio/useMic";

export function Meter({ levels, heard }: { levels: number[]; heard: boolean }) {
  return (
    <div className="meter" role="img" aria-label={heard ? "입력 크기: 잘 들려요" : "입력 크기"}>
      {levels.map((lv, i) => (
        <span key={i} className={lv > 0.08 ? "on" : ""} style={{ height: 6 + lv * 34, opacity: lv > 0.08 ? 0.45 + lv * 0.55 : 1 }} />
      ))}
    </div>
  );
}

export function MicDenied({ onRetry }: { onRetry: () => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="callout warn">
        <Icon.warn />
        <span>
          <strong>마이크가 꺼져 있어요.</strong> 시스템 설정 → 개인정보 보호 및 보안 → 마이크에서 ‘socrates’를 켜 주세요.
        </span>
      </div>
      <div className="row">
        <button className="btn btn-primary" onClick={openMicSettings}>시스템 설정 열기</button>
        <button className="btn" onClick={onRetry}>다시 확인</button>
      </div>
    </div>
  );
}

interface SelectProps {
  id: string;
  access: MicAccess;
  devices: MediaDeviceInfo[];
  micId?: string;
  onChoose: (id: string) => void;
}

export function MicSelect({ id, access, devices, micId, onChoose }: SelectProps) {
  return (
    <select id={id} value={micId ?? ""} onChange={(e) => onChoose(e.target.value)} disabled={access !== "ok"}>
      {devices.length === 0 && <option value="">{access === "asking" ? "마이크 허용을 기다리는 중…" : "기본 마이크"}</option>}
      {devices.map((d) => (
        <option key={d.deviceId} value={d.deviceId}>
          {d.label || "마이크"}
        </option>
      ))}
    </select>
  );
}
