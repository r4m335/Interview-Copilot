import React from "react";
import { QAPair } from "../hooks/useSession";

interface Props {
  history: QAPair[];
}

export default function AnswerHistory({ history }: Props) {
  if (history.length === 0) return null;

  return (
    <section className="history-section">
      <div className="history-label">PREVIOUS</div>
      {history.map((item, index) => (
        <div key={index} className="history-item">
          <div className="history-question">{item.question}</div>
          <div className="history-answer">{item.answer.slice(0, 120)}...</div>
        </div>
      ))}
    </section>
  );
}
