import { useEffect, useState } from "react";

const SERVER_ERROR = "We couldn't reach the extractor. Check that the API is running, then try again.";

const STATUS_TEXT = {
  valid: { title: "Job application", detail: "Missing details are left out." },
  ambiguous: {
    title: "Unclear details found",
    detail: "Unclear and missing details are left out rather than guessed.",
  },
  invalid: {
    title: "Not a job application",
    detail: "This doesn't look like a message from an applicant, so nothing was extracted.",
  },
};

const EXAMPLE_JSON = JSON.stringify(
  {
    input_status: "valid",
    applicant_name: "Ananya Sharma",
    position_applied: "Software Engineer",
    years_of_experience: 3,
    skills: ["Python", "SQL"],
  },
  null,
  2,
);

const JSON_TOKEN =/("(?:\\.|[^"\\])*")(\s*:)?|-?\d+(?:\.\d+)?/g;

function withoutMissingFields(result) {
  return Object.fromEntries(Object.entries(result).filter(([, value]) => value !== null));
}

function countFound(result) {
  return Object.entries(result).filter(
    ([name, value]) => !["input_status", "ambiguity_notes"].includes(name) && value !== null,
  ).length;
}

function highlightJson(json) {
  const parts = [];
  let position = 0;
  for (const match of json.matchAll(JSON_TOKEN)) {
    parts.push(json.slice(position, match.index));
    if (match[2]) {
      parts.push(
        <span className="token-key" key={match.index}>
          {match[1]}
        </span>,
        match[2],
      );
    } else {
      const type = match[1] ? "token-string" : "token-number";
      parts.push(
        <span className={type} key={match.index}>
          {match[0]}
        </span>,
      );
    }
    position = match.index + match[0].length;
  }
  parts.push(json.slice(position));
  return parts;
}

function CopyButton({ value }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button type="button" className="ghost" onClick={copy}>
      {copied ? "Copied" : "Copy JSON"}
    </button>
  );
}

function EmptyState() {
  return (
    <div className="placeholder">
      <p className="placeholder-title">Your results will appear here</p>
      <p>This is an example of what you'll get:</p>
      <pre className="json example" aria-hidden="true">
        <code>{highlightJson(EXAMPLE_JSON)}</code>
      </pre>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="skeleton" role="status">
      <span className="sr-only">Reading the message</span>
      <i />
      <i />
      <i />
      <i />
      <i />
      <i />
    </div>
  );
}

function Results({ result }) {
  const status = STATUS_TEXT[result.input_status];
  const found = countFound(result);
  const json = JSON.stringify(withoutMissingFields(result), null, 2);

  return (
    <div className="results" aria-live="polite">
      <div className={`status ${result.input_status}`}>
        <div>
          <h3>{status.title}</h3>
          <p>{status.detail}</p>
        </div>
        {result.input_status !== "invalid" && (
          <span className="count">
            {found} {found === 1 ? "detail" : "details"} found
          </span>
        )}
      </div>
      <div className="json-header">
        <span>JSON</span>
        <CopyButton value={json} />
      </div>
      <pre className="json">
        <code>{highlightJson(json)}</code>
      </pre>
    </div>
  );
}

export default function App() {
  const [samples, setSamples] = useState([]);
  const [activeSample, setActiveSample] = useState("");
  const [text, setText] = useState("");
  const [result, setResult] = useState(undefined);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch("/api/samples")
      .then((response) => (response.ok ? response.json() : []))
      .then(setSamples)
      .catch(() => setSamples([]));
  }, []);

  function resetOutput() {
    setResult(undefined);
    setError("");
  }

  function chooseSample(sample) {
    setText(sample.text);
    setActiveSample(sample.label);
    resetOutput();
  }

  function clearMessage() {
    setText("");
    setActiveSample("");
    resetOutput();
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    resetOutput();
    try {
      const response = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await response.json().catch(() => ({ detail: SERVER_ERROR }));
      if (!response.ok) {
        throw new Error(data.detail);
      }
      setResult(data);
    } catch (requestError) {
      setError(requestError instanceof TypeError ? SERVER_ERROR : requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-inner">
          <div>
            <p className="eyebrow">AI-powered extraction</p>
            <h1>Job Application Extractor</h1>
            <p className="tagline">Turn any applicant's message into clean, structured JSON in seconds.</p>
          </div>
          <ul className="badges" aria-label="How it works">
            <li>Gemini</li>
            <li>JSON Schema</li>
            <li>No guessing</li>
          </ul>
        </div>
      </header>

      <main className="workspace">
        <form className="panel" onSubmit={handleSubmit}>
          <div className="panel-header">
            <h2>
              <span className="step" aria-hidden="true">
                1
              </span>
              <label htmlFor="message">Paste a message</label>
            </h2>
            {text && (
              <button type="button" className="ghost" onClick={clearMessage}>
                Clear
              </button>
            )}
          </div>

          <textarea
            id="message"
            value={text}
            onChange={(event) => {
              setText(event.target.value);
              setActiveSample("");
            }}
            placeholder="Hi, I'm applying for the Software Engineer role..."
          />

          {samples.length > 0 && (
            <div className="samples">
              <span>Try a sample</span>
              <div className="sample-list">
                {samples.map((sample) => (
                  <button
                    type="button"
                    className="sample"
                    aria-pressed={activeSample === sample.label}
                    key={sample.label}
                    onClick={() => chooseSample(sample)}
                  >
                    {sample.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          <button type="submit" className="primary" disabled={loading || !text.trim()}>
            {loading ? "Reading the message..." : "Extract details →"}
          </button>
        </form>

        <section className="panel output">
          <div className="panel-header">
            <h2>
              <span className="step" aria-hidden="true">
                2
              </span>
              Get your JSON
            </h2>
          </div>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          {loading && <LoadingState />}
          {result && <Results result={result} />}
          {!loading && !result && !error && <EmptyState />}
        </section>
      </main>
    </div>
  );
}
