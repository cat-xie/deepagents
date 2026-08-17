import type { InterruptData } from "../types";

interface Props {
  interrupt: InterruptData;
  onApprove: (approved: boolean) => void;
}

export default function ApprovalDialog({ interrupt, onApprove }: Props) {
  return (
    <div className="approval-overlay">
      <div className="approval-dialog">
        <h3>🔔 需要审批</h3>
        <p>Agent 请求执行以下操作，是否批准？</p>

        <div className="approval-actions-list">
          {interrupt.action_requests.map((ar, i) => (
            <div className="approval-action-item" key={i}>
              <div className="tool-card-name">{ar.name}</div>
              <div className="tool-card-args">
                {JSON.stringify(ar.args, null, 2)}
              </div>
            </div>
          ))}
        </div>

        <div className="approval-buttons">
          <button className="btn btn-danger" onClick={() => onApprove(false)}>
            拒绝
          </button>
          <button className="btn btn-primary" onClick={() => onApprove(true)}>
            批准
          </button>
        </div>
      </div>
    </div>
  );
}
