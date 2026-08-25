import React, { useEffect, useRef } from "react";

interface Props {
  answer: string;
  isStreaming: boolean;
}

export default function AnswerCard({ answer, isStreaming }: Props) {
  const contentRef = useRef<HTMLDivElement>(null);

  // Auto-scroll as answer streams in
  useEffect(() => {
    if (contentRef.current && isStreaming) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight;
    }
  }, [answer, isStreaming]);

  if (!answer) return null;

  // Parse answer sections
  const sections = parseAnswer(answer);

  return (
    <section className="card answer-card">
      <div className="card-label">
        ANSWER
        {isStreaming && <span className="streaming-indicator">●</span>}
      </div>
      <div className="card-content answer-text" ref={contentRef}>
        {sections.answer && (
          <div className="answer-section">{sections.answer}</div>
        )}
        {sections.example && (
          <div className="answer-example">
            <div className="example-label">EXAMPLE</div>
            <pre className="example-code">{sections.example}</pre>
          </div>
        )}
        {sections.keyPoint && (
          <div className="answer-keypoint">
            <div className="keypoint-label">KEY POINT</div>
            <div className="keypoint-text">{sections.keyPoint}</div>
          </div>
        )}
        {/* If no sections parsed, show raw text */}
        {!sections.answer && !sections.example && !sections.keyPoint && (
          <div className="answer-section">{answer}</div>
        )}
      </div>
    </section>
  );
}

interface ParsedAnswer {
  answer: string;
  example: string;
  keyPoint: string;
}

function parseAnswer(text: string): ParsedAnswer {
  const result: ParsedAnswer = { answer: "", example: "", keyPoint: "" };

  // Try to parse structured format
  const answerMatch = text.match(/ANSWER:\s*([\s\S]*?)(?=EXAMPLE:|KEY POINT:|$)/i);
  const exampleMatch = text.match(/EXAMPLE:\s*([\s\S]*?)(?=KEY POINT:|$)/i);
  const keyPointMatch = text.match(/KEY POINT:\s*([\s\S]*?)$/i);

  if (answerMatch) result.answer = answerMatch[1].trim();
  if (exampleMatch) result.example = exampleMatch[1].trim();
  if (keyPointMatch) result.keyPoint = keyPointMatch[1].trim();

  return result;
}
