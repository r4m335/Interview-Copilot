import React, { useState } from "react";
import { QAPair } from "../hooks/useSession";

interface Props {
  history: QAPair[];
}

export default function AnswerHistory({ history }: Props) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);

  if (history.length === 0) return null;

  return (
    <section className="history-section">
      <div className="history-label">PREVIOUS</div>
      {history.map((item, index) => {
        const isExpanded = expandedIndex === index;
        return (
          <div 
            key={index} 
            className="history-item" 
            onClick={() => setExpandedIndex(isExpanded ? null : index)}
            style={{ cursor: "pointer" }}
          >
            <div className="history-question">{item.question}</div>
            <div className="history-answer">
              {isExpanded ? item.answer : `${item.answer.slice(0, 120)}...`}
            </div>
          </div>
        );
      })}
    </section>
  );
}
