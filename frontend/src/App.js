import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import "./App.css";

const API = 'http://localhost:8000/api';

function useSessionId() {
  const [sid, setSid] = useState("");
  useEffect(() => {
    let s = localStorage.getItem("session_id");
    if (!s) {
      s = (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`);
      localStorage.setItem("session_id", s);
    }
    setSid(s);
  }, []);
  return sid;
}

function Step({ title, subtitle, children, actions }) {
  return (
    <div className="bg-white/70 backdrop-blur rounded-xl shadow-xl border border-slate-200 p-6">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-slate-800">{title}</h2>
        {subtitle && <p className="text-slate-500 mt-1 text-sm">{subtitle}</p>}
      </div>
      <div className="mt-2">{children}</div>
      {actions && <div className="mt-6 flex items-center gap-3">{actions}</div>}
    </div>
  );
}

function App() {
  const sessionId = useSessionId();
  const [hello, setHello] = useState("");
  const [uploading, setUploading] = useState(false);
  const [cv, setCv] = useState(null);
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [matchResult, setMatchResult] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [letter, setLetter] = useState("");
  const [tone, setTone] = useState("formal");
  const [template, setTemplate] = useState("classic");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const r = await axios.get(`${API}/`);
        setHello(r.data.message);
      } catch (e) {
        console.error(e);
      }
    };
    load();
  }, []);

  useEffect(() => {
    const fetchJobs = async () => {
      try {
        const r = await axios.get(`${API}/jobs`);
        setJobs(r.data);
      } catch (e) {
        console.error(e);
        setError("Failed to load jobs");
      }
    };
    fetchJobs();
  }, []);

  const onUpload = async (file) => {
    if (!file) return;
    
    const validTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'text/plain',
      '.pdf',
      '.docx',
      '.txt'
    ];
    
    const fileExt = file.name.split('.').pop().toLowerCase();
    const isValidType = validTypes.includes(file.type) || validTypes.includes(`.${fileExt}`);
    
    if (!isValidType) {
      setError("Invalid file type. Please upload PDF, DOCX, or TXT.");
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      setError("File too large. Max 5MB allowed.");
      return;
    }

    setUploading(true);
    setError("");
    
    try {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("session_id", sessionId);
      
      const r = await axios.post(`${API}/cv/upload`, fd, {
        headers: { 
          "Content-Type": "multipart/form-data",
        },
        timeout: 30000
      });
      
      setCv(r.data.cv);
    } catch (e) {
      let errorMsg = "Upload failed";
      if (e.response) {
        if (e.response.status === 422) {
          errorMsg = "The file appears to be image-based. Try a text-based file or ensure OCR is configured.";
        } else {
          errorMsg = e.response.data?.detail || e.response.statusText;
        }
      }
      setError(errorMsg);
    } finally {
      setUploading(false);
    }
  };

  const onMatch = async () => {
    if (!cv?.id || !selectedJob?.id) return;
    setError("");
    try {
      const r = await axios.post(`${API}/match`, { cv_id: cv.id, job_id: selectedJob.id });
      setMatchResult(r.data.result);
    } catch (e) {
      setError("Matching failed");
    }
  };

  const onGenerate = async () => {
    if (!cv?.id || !selectedJob?.id) return;
    setGenerating(true);
    setError("");
    setLetter("");
    try {
      const r = await axios.post(`${API}/cover-letter/generate`, {
        session_id: sessionId,
        cv_id: cv.id,
        job_id: selectedJob.id,
        tone,
        template,
        personal_note: note,
      });
      setLetter(r.data.content);
    } catch (e) {
      const msg = e?.response?.data?.detail || "Generation failed";
      setError(msg);
    } finally {
      setGenerating(false);
    }
  };

  const disabled = useMemo(() => !cv || !selectedJob, [cv, selectedJob]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-sky-50">
      <header className="px-6 py-5 border-b border-slate-200 bg-white/60 backdrop-blur">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-lg bg-sky-600 text-white grid place-items-center font-bold">CV</div>
            <div>
              <h1 className="text-slate-800 font-semibold">CV Matcher</h1>
              <p className="text-slate-500 text-xs">{hello || "Finding your perfect role"}</p>
            </div>
          </div>
          <div className="text-xs text-slate-500">Session: {sessionId?.slice(0,8)}</div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 space-y-6">
        <Step title="1. Upload your CV" subtitle="PDF, DOCX, or TXT">
          <div className="flex items-center gap-4">
            <label className="inline-flex items-center px-4 py-2 rounded-md bg-sky-600 text-white hover:bg-sky-700 cursor-pointer">
              <input type="file" className="hidden" accept=".pdf,.docx,.txt" onChange={(e) => onUpload(e.target.files?.[0])} />
              {uploading ? "Uploading..." : "Choose file"}
            </label>
            {cv && <div className="text-sm text-slate-600">Uploaded: <span className="font-medium">{cv.filename}</span></div>}
          </div>
          {cv && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-700">Detected skills</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {cv.sections?.skills?.slice(0, 25).map((s, idx) => (
                    <span key={idx} className="px-2 py-1 rounded-md bg-slate-100 text-slate-700 text-xs border border-slate-200">{s}</span>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-slate-700">Experience snapshot</h3>
                <ul className="mt-2 list-disc list-inside text-sm text-slate-700 space-y-1 max-h-40 overflow-auto">
                  {(cv.sections?.experience || []).slice(0,5).map((e, i) => <li key={i}>{e}</li>)}
                </ul>
              </div>
            </div>
          )}
        </Step>

        <Step title="2. Pick a job" subtitle="Curated mock openings">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {jobs.map(job => (
              <button key={job.id} onClick={() => setSelectedJob(job)} className={`text-left p-4 rounded-xl border transition shadow-sm hover:shadow-md ${selectedJob?.id===job.id ? 'border-sky-600 ring-2 ring-sky-100' : 'border-slate-200'}`}>
                <div className="text-slate-900 font-semibold">{job.title}</div>
                <div className="text-slate-600 text-sm">{job.company} • {job.location}</div>
                <p className="text-slate-500 text-sm mt-2 line-clamp-3">{job.description}</p>
                <div className="mt-3 flex flex-wrap gap-1">
                  {job.requirements.slice(0,6).map((r, i) => <span key={i} className="text-xs bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md text-slate-700">{r}</span>)}
                </div>
              </button>
            ))}
          </div>
        </Step>

        <Step title="3. Match score" subtitle="See how well your CV fits the role" actions={[
          <button key="match" onClick={onMatch} disabled={disabled} className={`px-4 py-2 rounded-md text-white ${disabled? 'bg-slate-300' : 'bg-emerald-600 hover:bg-emerald-700'}`}>Compute match</button>
        ]}>
          {matchResult ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="col-span-1">
                <div className="text-5xl font-bold text-emerald-700">{Math.round(matchResult.score)}</div>
                <div className="text-slate-500 text-sm">/ 100</div>
                <div className="text-slate-600 text-sm mt-2">Matched skills:</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {matchResult.matched_skills.map((s, i) => <span key={i} className="text-xs bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md text-emerald-800">{s}</span>)}
                </div>
              </div>
              <div className="md:col-span-2">
                <h4 className="text-sm font-semibold text-slate-700">Overlap keywords</h4>
                <div className="mt-2 flex flex-wrap gap-2 max-h-40 overflow-auto">
                  {matchResult.overlap_keywords.map((k, i) => <span key={i} className="text-xs bg-slate-100 border border-slate-200 px-2 py-0.5 rounded-md text-slate-700">{k}</span>)}
                </div>
              </div>
            </div>
          ) : (
            <p className="text-slate-500 text-sm">Run a match to see your score.</p>
          )}
        </Step>

        <Step title="4. Generate cover letter" subtitle="Uses the universal LLM key">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-3">
              <div>
                <label className="text-sm text-slate-600">Tone</label>
                <select value={tone} onChange={e => setTone(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2">
                  <option value="formal">Formal</option>
                  <option value="enthusiastic">Enthusiastic</option>
                  <option value="creative">Creative</option>
                  <option value="concise">Concise</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-slate-600">Template</label>
                <select value={template} onChange={e => setTemplate(e.target.value)} className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2">
                  <option value="classic">Classic</option>
                  <option value="modern">Modern</option>
                  <option value="minimalist">Minimalist</option>
                </select>
              </div>
            </div>
            <div className="md:col-span-2">
              <label className="text-sm text-slate-600">Personal note (optional)</label>
              <textarea value={note} onChange={e => setNote(e.target.value)} rows={4} className="mt-1 w-full border border-slate-300 rounded-md px-3 py-2" placeholder="Anything you want to emphasize" />
              <div className="mt-3">
                <button onClick={onGenerate} disabled={disabled || generating} className={`px-4 py-2 rounded-md text-white ${disabled? 'bg-slate-300' : 'bg-sky-600 hover:bg-sky-700'}`}>{generating ? 'Generating...' : 'Generate'}</button>
              </div>
            </div>
          </div>

          {letter && (
            <div className="mt-4 p-4 rounded-lg border border-slate-200 bg-white">
              <h4 className="text-sm font-semibold text-slate-700">Your cover letter</h4>
              <pre className="whitespace-pre-wrap text-slate-800 text-sm mt-2">{letter}</pre>
            </div>
          )}
        </Step>

        {error && (
          <div className="p-3 rounded-md bg-red-50 border border-red-200 text-sm text-red-700">{error}</div>
        )}
      </main>

      <footer className="text-center text-xs text-slate-500 py-8">Built fast with love</footer>
    </div>
  );
}

export default App;