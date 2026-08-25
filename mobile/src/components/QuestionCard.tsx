import React from "react";

interface Props {
  question: string;
}

export default function QuestionCard({ question }: Props) {
  if (!question) return null;

  return (
    <section className="card question-card">
      <div className="card-label">QUESTION</div>
      <div className="card-content question-text">{question}</div>
    </section>
  );
}
